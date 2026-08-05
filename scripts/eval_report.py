"""Final number extraction for docs/EVALS.md — correct event semantics."""
import json, glob, sys, os, pathlib
REPO = pathlib.Path(__file__).resolve().parent.parent
from collections import Counter, defaultdict
os.environ["SENTINEL_QUIET"] = "1"
sys.path.insert(0, str(REPO))
from agents.router_agent import RouterAgent
from agents.rapid_prosecution import RapidProsecutionAgent
from agents.retrieval_agent import RetrievalAgent

S = {}
for f in sorted(glob.glob(str(REPO) + "/results/live/*_session.json")):
    S[f.split("/")[-1].replace("_session.json", "")] = json.load(open(f))

print("== A. ROUTER OUTCOME BREAKDOWN (recorded production run) ==")
tot = Counter()
rows = {}
for c, d in S.items():
    n_utt = sum(1 for e in d["events"] if e["kind"] == "utterance")
    none_skip = sum(1 for e in d["events"] if e["kind"] == "router_skip" and e.get("classification") == "none")
    pros_none = sum(1 for e in d["events"] if e["kind"] == "router_skip" and e.get("reason") == "prosecution_no_alert")
    alerts = sum(1 for e in d["events"] if e["kind"] == "rapid_alert")
    kwfast = sum(1 for a in d["rapid_alerts"] if a["model_used"] == "keyword_fastpath")
    llmal = alerts - kwfast
    rows[c] = dict(utt=n_utt, router_none=none_skip, reached_L1=pros_none + alerts,
                   L1_declined=pros_none, alerts=alerts, kwfast=kwfast, llm_alert=llmal)
    for k, v in rows[c].items():
        tot[k] += v
    print(f" {c:24s} utt={n_utt:3d} router_none={none_skip:3d} reached_L1={pros_none+alerts:3d} "
          f"L1_declined={pros_none:3d} alerts={alerts:3d} (kw={kwfast} llm={llmal})")
print(" TOTAL", dict(tot))

print("\n== B. LOCAL KEYWORD STAGE vs RECORDED ROUTER ==")
retr = RetrievalAgent()
agree = Counter()
unrepro = []
for c, d in S.items():
    router = RouterAgent(region=d["region"])
    rapid = RapidProsecutionAgent(region=d["region"], retrieval=retr)
    txt = {e["utt_index"]: e["text"] for e in d["events"] if e["kind"] == "utterance"}
    rec = {}
    for e in d["events"]:
        i = e.get("utt_index")
        if i is None:
            continue
        if e["kind"] == "router_skip":
            rec[i] = ("skip", e.get("classification"), None, None)
        elif e["kind"] == "rapid_alert":
            rec[i] = ("alert", e.get("classification"), e.get("rule_id"), e.get("model_used"))
    for i, (kind, rcls, rid, model) in sorted(rec.items()):
        kw = router._keyword_classify(txt[i])
        lcls = kw.classification if kw else "LLM"
        if lcls == "LLM":
            agree["needs_llm_router"] += 1
        elif lcls == rcls:
            agree["exact_class_match"] += 1
        else:
            agree["class_differs"] += 1
        if model == "keyword_fastpath":
            if lcls == "critical_event":
                a = rapid._build_critical_event_alert(txt[i])
                agree["fastpath_reproduced" if a.rule_id == rid else "fastpath_diff_rule"] += 1
            else:
                agree["fastpath_needs_llm_router"] += 1
                unrepro.append((c, i, rid, txt[i][:70]))
print(" ", dict(agree))
print(f"  fastpath alerts the local keyword bank cannot route: {len(unrepro)}")
print("   by case:", dict(Counter(x[0] for x in unrepro)), " by rule:", dict(Counter(x[2] for x in unrepro)))

print("\n== C. FUNNEL ==")
F = {}
for c, d in S.items():
    r = len(d["rapid_alerts"]); dv = len(d["deep_violations"])
    rl = d["final_verdict"].get("rulings", [])
    disp = Counter(x.get("verdict") for x in rl)
    survived = disp.get("violation_upheld", 0) + disp.get("violation_mitigated", 0)
    F[c] = (r, dv, len(rl), disp.get("violation_dismissed", 0), disp.get("violation_mitigated", 0),
            disp.get("violation_upheld", 0), survived)
    print(f" {c:24s} L1={r:3d} L3={dv:2d} ruled={len(rl):2d} dismissed={disp.get('violation_dismissed',0):2d} "
          f"mitigated={disp.get('violation_mitigated',0)} upheld={disp.get('violation_upheld',0)} survived={survived}")
tt = [sum(x[i] for x in F.values()) for i in range(7)]
print(f" TOTAL L1={tt[0]} L3={tt[1]} ruled={tt[2]} dismissed={tt[3]} mitigated={tt[4]} upheld={tt[5]} survived={tt[6]}")

print("\n== D. JUDGE BALANCE incl. batch-council runs ==")
allrul = Counter()
for c, d in S.items():
    allrul += Counter(x.get("verdict") for x in d["final_verdict"].get("rulings", []))
print("  live pipeline:", dict(allrul))
cb = Counter()
for f in ["video3_borderline", "video1_violation", "video2_violation", "us_citizen_aggression"]:
    C = json.load(open(REPO / "results" / "council" / f"{f}_council.json"))
    cb += Counter(x.get("verdict") for x in C["verdict"].get("rulings", []))
print("  batch council:", dict(cb))
comb = allrul + cb
tot_r = sum(comb.values())
print(f"  COMBINED: {dict(comb)} total={tot_r}")
print(f"  -> Judge sided with Defense (dismissed): {comb['violation_dismissed']}/{tot_r} "
      f"= {100*comb['violation_dismissed']/tot_r:.0f}%")
print(f"  -> Mixed (mitigated): {comb['violation_mitigated']}/{tot_r} = {100*comb['violation_mitigated']/tot_r:.0f}%")
print(f"  -> Prosecution (upheld): {comb['violation_upheld']}/{tot_r} = {100*comb['violation_upheld']/tot_r:.0f}%")

print("\n== E. RULE-ID VALIDITY CHECK (every cited ID vs the rule packs) ==")
packs = {}
for r in ("us", "eu", "it"):
    packs[r] = {x["id"] for x in json.load(open(REPO / "case_law" / f"police_{r}.json"))["rules"]}
packs["it"] |= packs["eu"]
CRIT = {"CRIT-ARMED-SUBJECT", "CRIT-FORCE-TASER", "CRIT-OFFICER-DISTRESS",
        "CRIT-FORCE-LETHAL", "CRIT-FINAL-WARNING", "CRIT-GENERIC"}
bad = []
n_cited = 0
for c, d in S.items():
    reg = d["region"]
    valid = packs[reg] | CRIT
    for src, items in (("L1", d["rapid_alerts"]), ("L3", d["deep_violations"]),
                       ("L4", d["final_verdict"].get("rulings", []))):
        for x in items:
            rid = x.get("rule_id"); n_cited += 1
            if rid not in valid:
                bad.append((c, src, rid))
for f, reg in [("video3_borderline", "us"), ("video1_violation", "us"),
               ("video2_violation", "us"), ("us_citizen_aggression", "us")]:
    C = json.load(open(REPO / "results" / "council" / f"{f}_council.json"))
    for src, items in (("L3", C["prosecution"].get("violations", [])),
                       ("L4", C["verdict"].get("rulings", []))):
        for x in items:
            rid = x.get("rule_id"); n_cited += 1
            if rid not in packs[reg] | CRIT:
                bad.append((f, src, rid))
print(f"  citations checked: {n_cited}; off-pack: {len(bad)} -> {bad}")

print("\n== F. LATENCY ==")
kw = [a["atom_ms"] for d in S.values() for a in d["rapid_alerts"] if a["model_used"] == "keyword_fastpath"]
llm = [a["atom_ms"] for d in S.values() for a in d["rapid_alerts"] if a["model_used"] != "keyword_fastpath"]
print(f"  keyword fastpath atom_ms: n={len(kw)} min={min(kw)} med={sorted(kw)[len(kw)//2]} max={max(kw)}")
print(f"  LLM path atom_ms       : n={len(llm)} {sorted(llm)}")
jw = [s["wall_ms"] for d in S.values() for s in d["verdict_timeline"]]
print(f"  judge wall_ms: n={len(jw)} min={min(jw)} med={sorted(jw)[len(jw)//2]} max={max(jw)}")
vis = [d["visual_context"]["latency_ms"] for d in S.values() if d.get("visual_context")]
print(f"  vision latency_ms: {sorted(vis)}")
