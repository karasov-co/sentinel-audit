"""SENTINEL evaluation harness — offline replay of the deterministic layers.

Replays every utterance recorded in results/live/*_session.json through:
  L0  RouterAgent._keyword_classify        (local keyword stage)
  L1  RapidProsecution._build_critical_event_alert  (keyword fastpath)
  L2  RetrievalAgent.search                (MiniLM + FAISS, local)

N independent runs, fresh agent objects each run. Compares:
  - run-to-run bit-exactness
  - agreement with what the production run actually recorded
"""
import json, glob, sys, os, time, pathlib
REPO = pathlib.Path(__file__).resolve().parent.parent
from collections import Counter, defaultdict

os.environ["SENTINEL_QUIET"] = "1"
sys.path.insert(0, str(REPO))

from agents.router_agent import RouterAgent
from agents.rapid_prosecution import RapidProsecutionAgent
from agents.retrieval_agent import RetrievalAgent

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5

sessions = {}
for f in sorted(glob.glob(str(REPO) + "/results/live/*_session.json")):
    name = f.split("/")[-1].replace("_session.json", "")
    sessions[name] = json.load(open(f))

# ---- recorded ground truth -------------------------------------------------
recorded = {}   # case -> {utt_index: {"text","recorded_kind","recorded_cls","rule_id","model"}}
for case, d in sessions.items():
    per = {}
    for e in d["events"]:
        if e["kind"] == "utterance":
            per[e["utt_index"]] = {"text": e["text"], "outcome": None,
                                   "cls": None, "rule_id": None, "model": None}
    for e in d["events"]:
        i = e.get("utt_index")
        if i is None or i not in per:
            continue
        if e["kind"] == "router_skip":
            per[i]["outcome"] = "skip"
            per[i]["cls"] = e.get("classification")
        elif e["kind"] == "rapid_alert":
            per[i]["outcome"] = "alert"
            per[i]["cls"] = e.get("classification")
            per[i]["rule_id"] = e.get("rule_id")
            per[i]["model"] = e.get("model_used")
    recorded[case] = per

# ---- N replay runs ---------------------------------------------------------
runs = []
timings = []
for run_i in range(N):
    t0 = time.perf_counter()
    out = {}
    retr = RetrievalAgent()          # fresh index cache per run
    for case, d in sessions.items():
        region = d["region"]
        router = RouterAgent(region=region)
        rapid = RapidProsecutionAgent(region=region, retrieval=retr)
        for i, rec in sorted(recorded[case].items()):
            text = rec["text"]
            kw = router._keyword_classify(text)
            cls = kw.classification if kw else "__LLM__"
            stage = kw.stage if kw else "llm_required"
            fast = None
            if cls == "critical_event":
                a = rapid._build_critical_event_alert(text)
                fast = (a.rule_id, a.severity, a.subject, round(a.confidence, 4))
            hits = retr.search(text, region=region, top_k=3)
            top3 = tuple((h.rule_id, round(float(h.score), 6)) for h in hits)
            out[(case, i)] = {"cls": cls, "stage": stage, "fast": fast, "top3": top3}
    runs.append(out)
    timings.append(time.perf_counter() - t0)
    print(f"[run {run_i+1}/{N}] {len(out)} utterances in {timings[-1]:.1f}s", file=sys.stderr)

# ---- 1. run-to-run determinism --------------------------------------------
base = runs[0]
mismatch = defaultdict(int)
for r in runs[1:]:
    for k, v in base.items():
        if r[k]["cls"] != v["cls"]:
            mismatch["router_class"] += 1
        if r[k]["fast"] != v["fast"]:
            mismatch["fastpath_alert"] += 1
        if tuple(x[0] for x in r[k]["top3"]) != tuple(x[0] for x in v["top3"]):
            mismatch["retrieval_ids"] += 1
        if r[k]["top3"] != v["top3"]:
            mismatch["retrieval_scores"] += 1

total_utt = len(base)
print("\n" + "=" * 72)
print(f"E1 DETERMINISM — {N} runs x {total_utt} utterances = {N*total_utt} evaluations")
print(f"  wall per run: {min(timings):.1f}-{max(timings):.1f}s")
print(f"  router-class mismatches vs run 1 : {mismatch['router_class']} / {(N-1)*total_utt}")
print(f"  fastpath-alert mismatches        : {mismatch['fastpath_alert']} / {(N-1)*total_utt}")
print(f"  retrieval top-3 ID mismatches    : {mismatch['retrieval_ids']} / {(N-1)*total_utt}")
print(f"  retrieval score mismatches (1e-6): {mismatch['retrieval_scores']} / {(N-1)*total_utt}")

# ---- 2. local vs LLM split -------------------------------------------------
stage_c = Counter(v["stage"] for v in base.values())
cls_c = Counter(v["cls"] for v in base.values())
print("\nE2 LOCAL-vs-LLM SPLIT (stage-1 keyword router)")
for k, v in stage_c.most_common():
    print(f"  {k:16s} {v:4d}  ({100*v/total_utt:.1f}%)")
print(f"  classifications: {dict(cls_c)}")
local = total_utt - stage_c.get("llm_required", 0)
print(f"  => {local}/{total_utt} ({100*local/total_utt:.1f}%) decided locally, bit-exact reproducible")

per_case_split = {}
for case in sessions:
    ks = [v for (c, i), v in base.items() if c == case]
    loc = sum(1 for v in ks if v["stage"] != "llm_required")
    per_case_split[case] = (loc, len(ks))
print("  per case (local/total):", {k: f"{a}/{b}" for k, (a, b) in per_case_split.items()})

# ---- 3. agreement with the recorded production run -------------------------
agree = Counter()
fast_rule_match = Counter()
crit_generic_cases = []
for case, per in recorded.items():
    for i, rec in per.items():
        v = base[(case, i)]
        if rec["outcome"] == "skip":
            if v["cls"] == "none":
                agree["skip_reproduced"] += 1
            elif v["cls"] == "__LLM__":
                agree["skip_needed_llm"] += 1
            else:
                agree["skip_diverged"] += 1
        elif rec["outcome"] == "alert":
            if rec["model"] == "keyword_fastpath":
                if v["cls"] == "critical_event":
                    agree["fastpath_route_reproduced"] += 1
                    if v["fast"] and v["fast"][0] == rec["rule_id"]:
                        fast_rule_match["same_rule"] += 1
                    else:
                        fast_rule_match["diff_rule"] += 1
                elif v["cls"] == "__LLM__":
                    agree["fastpath_route_via_llm"] += 1
                    crit_generic_cases.append((case, i, rec["rule_id"], rec["text"][:60]))
                else:
                    agree["fastpath_route_diverged"] += 1
                    crit_generic_cases.append((case, i, rec["rule_id"], rec["text"][:60]))
            else:
                agree["llm_alert"] += 1
print("\nE3 AGREEMENT WITH RECORDED PRODUCTION RUN")
for k, v in agree.most_common():
    print(f"  {k:28s} {v}")
print(f"  fastpath rule match: {dict(fast_rule_match)}")
print(f"\n  keyword-fastpath alerts whose route the LOCAL bank cannot reproduce: {len(crit_generic_cases)}")
by_case = Counter(c for c, _, _, _ in crit_generic_cases)
by_rule = Counter(r for _, _, r, _ in crit_generic_cases)
print(f"    by case: {dict(by_case)}")
print(f"    by rule: {dict(by_rule)}")
for c, i, r, t in crit_generic_cases[:6]:
    print(f"    - {c}[{i}] {r}: {t!r}")

# ---- 4. retrieval threshold sensitivity ------------------------------------
print("\nE4 RETRIEVAL SENSITIVITY (top-1 cosine over every utterance)")
retr = RetrievalAgent()
buckets = Counter()
per_case_top1 = defaultdict(list)
for (case, i), v in base.items():
    if not v["top3"]:
        continue
    s = v["top3"][0][1]
    per_case_top1[case].append(s)
    buckets[">=0.55 (mandatory-emit threshold)" if s >= 0.55 else
            ">=0.50 (escalation-upgrade threshold)" if s >= 0.50 else "<0.50"] += 1
for k, v in buckets.most_common():
    print(f"  {k:42s} {v:4d}  ({100*v/total_utt:.1f}%)")
for case, xs in sorted(per_case_top1.items()):
    xs2 = sorted(xs)
    print(f"  {case:24s} n={len(xs):3d} median={xs2[len(xs2)//2]:.3f} max={xs2[-1]:.3f} "
          f">=0.55: {sum(1 for s in xs if s>=0.55)}")

# ---- 5. index facts --------------------------------------------------------
print("\nE5 RULE PACKS")
for r in ("us", "eu", "it"):
    idx, meta = __import__("agents.retrieval_agent", fromlist=["x"]).load_index_for_region(r)
    subj = Counter(m["subject"] for m in meta)
    print(f"  {r}: {len(meta)} rules, {idx.ntotal} vectors, subjects={dict(subj)}")

json.dump({"determinism": dict(mismatch), "n_runs": N, "n_utt": total_utt,
           "stage": dict(stage_c), "agreement": dict(agree),
           "fast_rule_match": dict(fast_rule_match),
           "unreproducible_fastpath": crit_generic_cases,
           "buckets": dict(buckets),
           "per_case_split": per_case_split,
           "timings": timings},
          open(REPO / "results" / "replay_results.json", "w"), indent=1)
print("\nsaved replay_results.json")
