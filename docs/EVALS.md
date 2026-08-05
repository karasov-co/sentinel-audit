# SENTINEL — Evaluation Report

**Version:** 1.0 · **Date:** August 2026 · **Author:** Vitalii Karasov

This document reports what SENTINEL's adversarial council actually does on
its seven demo cases: how stable the verdicts are, how often the Judge sides
with Prosecution vs Defense, and how many rapid alerts survive deep review.
It is a prototype evaluation, not a legal benchmark — the Scope & Limits
section states exactly what these numbers do and do not show.

Every number below is measured from the artifacts in `results/` or produced by
a replay harness run against them. Where a measurement could not be made, the
report says so rather than estimating.

## 1. Setup

- 7 recordings, 4 jurisdictions (US ×4, IT, NL, ES), 39 s – 12 m 44 s,
  36 m 11 s of audio total, 199 diarized utterances
- Council: ProsecutionAgent (`openai/gpt-oss-120b`) · DefenseAgent
  (`google/gemma-4-31B-it`) · JudgeAgent (`gemini-3.1-pro-preview`) ·
  VisualContextAgent (`gemini-3.1-pro-preview`), with RouterAgent
  (`google/gemma-4-E4B-it`) and RapidProsecution (`google/gemma-4-26B-A4B-it`)
  on the live path
- Retrieval: `all-MiniLM-L6-v2` + FAISS `IndexFlatIP` over three rule packs —
  US 20 rules, EU 30, IT 55 (IT index = EU + IT)

**Two run families exist for these cases.** The batch council (`pipeline_v2.py`,
archived in `results/council/`) and the live four-layer pipeline
(`pipeline_live.py`, archived in `results/live/`). The four US cases were
processed by both; the three EU cases by the live pipeline only.

### How many times each case was processed

| Layer | What it is | Independent runs measured |
|---|---|---|
| L0 router keyword stage, L1 critical-event fastpath, L2 retrieval | local, no network | **5 fresh runs × 199 utterances = 995 evaluations** |
| L0 router LLM stage, L1 rapid prosecution, L3 Prosecution/Defense, L4 Judge | remote LLM calls | **2 archived runs** (US cases), **1 archived run** (EU cases) |
| L4 Judge, within one session | re-consolidates as evidence accumulates | **16 invocations** across the 7 sessions |

The deterministic layers were genuinely re-executed for this report. The LLM
layers were **not** re-run three times: this checkout has no API keys, and the
source media in `recordings/` is deliberately not committed, so fresh
transcription and fresh council calls are not reproducible here. The stability
evidence for the LLM layers is therefore the comparison of the two archived run
families, plus the within-session Judge snapshots — weaker than a 3× repeat, and
labelled as such throughout.

## 2. Verdict reproducibility

| Case | Dur | LLM runs | Verdict stable? | Severity stable? | Notes |
|---|---|---|---|---|---|
| us_video3 | 0:59 | 2 | **yes** — `mixed` both | **yes** — `LOW` both | Same disposition on the two shared findings (`US-1A-RECORD` mitigated, `US-4A-STOP` dismissed). Prosecution surfaced 4 findings in the batch run vs 2 in live (Jaccard 0.50) |
| us_video1 | 3:53 | 2 | **yes** — `officer_justified` both | **no** — `none` vs `LOW` | Batch Prosecution returned **0 violations** (it fell back to `gemma-4-26B-A4B-it`); live returned 3. Same verdict label from completely different evidence sets (Jaccard 0.00) |
| us_video2_vision | 10:21 | 2 | **yes** — `officer_justified` both | **yes** — `none` both | Both runs found and dismissed `US-5A-MIRANDA`; live added 3 more findings, all dismissed (Jaccard 0.25) |
| us_aggression | 1:25 | 2 | **yes** — `officer_justified` both | **yes** — `none` both | Strongest agreement: same 3 rules, same 3 dismissals. One rule ID drifted — batch cited `US-ARREST-PC`, which does not exist in the pack (live cited the real `US-4A-ARREST-PC`) |
| it_carabinieri_arrest | 6:10 | 1 | not measurable | not measurable | Within-session the verdict moved `officer_at_fault`/medium → `mixed`/low → `mixed`/medium across 3 snapshots |
| nl_politie_inval | 0:39 | 1 | not measurable | not measurable | Single Judge invocation; only 2 utterances of usable audio |
| es_robbery_shootout | 12:44 | 1 | **no** — run failed | n/a | Final Judge call returned invalid JSON → `unclear`/`none`, headline "Judge consolidation error", **0 rulings** on 10 findings. Snapshot 1 had said `officer_justified` |

**Deterministic layers: 0 drift.** Across 5 fresh runs of all 199 utterances
(796 paired comparisons per check), the router keyword stage, the critical-event
fastpath and FAISS retrieval produced **identical output every time** — 0
classification mismatches, 0 fastpath mismatches, 0 top-3 rule-ID mismatches,
0 score mismatches at 1e-6. Replay cost: ~1.0 s per full pass over all 7 cases
after model load.

**Is the pipeline deterministic?** Partly, and the split is measurable.
The local keyword router resolves **93 of 199 utterances (46.7%)** on its own —
those decisions are bit-exact forever. The remaining **106 (53.3%)** escalate to
the LLM router, and everything downstream of them is sampled. Of the 38 rapid
alerts in the archives, 35 came from the keyword fastpath (reproducible: all 15
that the local bank can still route came back with the identical rule ID) and
only 3 came from an LLM.

So the variance is concentrated in three places, in descending order of impact:

1. **The Prosecution stage, via model fallback.** The largest divergence
   observed is not sampling noise — it is `video1_violation`, where the primary
   model was unavailable and the run silently fell back to a smaller model that
   returned 0 violations where the other run returned 3. The fallback is a
   bigger reproducibility risk than temperature.
2. **Judge JSON parsing.** 1 of 7 cases (es_robbery_shootout) lost its entire
   verdict to an unparseable response — a hard failure, not a variation.
   The retry path recovered nothing.
3. **Sampling temperature and evidence order.** Prosecution finds overlapping
   but non-identical violation sets between runs (Jaccard 0.00–0.50 on the
   four repeated cases), while the final verdict label survived in 4 of 4.
   Retrieval order contributes nothing — it is provably fixed.

The Vision pass is a fourth candidate but is untested for stability: it ran once
per case, on 3 of 7 cases, at 24.6 s–39.8 s per pass.

## 3. Alert funnel (false-positive behaviour)

Layer 1 is deliberately over-sensitive; the council's job is to kill noise.

Upstream of L1, the router discards **140 of 199 utterances (70.4%)** as `none`;
59 reach rapid prosecution and 21 of those are declined there.

| Case | Rapid alerts (L1) | Deep violations (L3) | Ruled on (L4) | Upheld in verdict (L4) |
|---|---|---|---|---|
| es_robbery_shootout | 23 | 8 | 0 | **0** — Judge crashed, nothing adjudicated |
| us_video1 | 12 | 3 | 5 | **0** — all dismissed |
| us_aggression | 1 | 3 | 3 | **0** — all dismissed |
| us_video2_vision | 1 | 4 | 4 | **0** — all dismissed |
| it_carabinieri_arrest | 1 | 7 | 8 | **4** (1 upheld MEDIUM, 3 reduced to LOW) |
| us_video3 | 0 | 2 | 2 | **1** (reduced to LOW) |
| nl_politie_inval | 0 | 3 | 3 | **0** — all dismissed |

**Funnel across all cases: 38 rapid alerts → 30 deep findings → 25 adjudicated →
5 survived (1 upheld, 4 mitigated).**

Read honestly, that is an **87% kill rate** from L1 to a surviving finding, and
the council is doing most of that work at L4 rather than L3 — L3 barely reduces
the count (38 → 30), while L4 dismisses 20 of the 25 findings it rules on. Two
caveats on the numbers:

- The 5 survivors are concentrated in 2 cases. Five of seven cases end with
  zero surviving findings.
- `us_video1` shows 3 deep violations but 5 rulings: the Judge also adjudicated
  two operational `CRIT-*` fastpath alerts that were never L3 findings, and
  dismissed both. The funnel is not strictly monotone.
- es_robbery_shootout's 23 → 0 is **not** a filtering success. The alerts were
  never adjudicated; the Judge failed. The README previously described this case
  as noise being filtered to zero violations — the artifact does not support that.

## 4. Adversarial balance

Every finding that reaches the Judge is contested — Defense filed a rebuttal on
all 30 deep findings, 20 arguing `rebut` (dismiss outright) and 10 `mitigate`
(reduce severity). Counting the Judge's disposition per contested finding,
across both run families:

| Case | Contested findings ruled | Judge → Prosecution (upheld) | Judge → Defense (dismissed) | Mixed (mitigated) |
|---|---|---|---|---|
| it_carabinieri_arrest (live) | 8 | 1 | 4 | 3 |
| us_video1 (live) | 5 | 0 | 5 | 0 |
| us_video2_vision (live) | 4 | 0 | 4 | 0 |
| us_aggression (live) | 3 | 0 | 3 | 0 |
| nl_politie_inval (live) | 3 | 0 | 3 | 0 |
| us_video3 (live) | 2 | 0 | 1 | 1 |
| es_robbery_shootout (live) | 0 | — | — | — |
| us_video3 (batch) | 4 | 0 | 3 | 1 |
| us_aggression (batch) | 3 | 0 | 3 | 0 |
| us_video2_vision (batch) | 1 | 0 | 1 | 0 |
| us_video1 (batch) | 0 | — | — | — |
| **Total** | **33** | **1 (3%)** | **27 (82%)** | **5 (15%)** |

**Does one side dominate? Yes — decisively, and not in the direction the design
intended.** The different-model-family split (gemma Defense vs gpt-oss
Prosecution) is there so neither side wins by default, but on this sample the
Judge accepts the Defense's rebuttal 82% of the time and upholds Prosecution
outright **once in 33 rulings**. Every one of the 6 non-dismissals comes from
just 3 cases.

Three readings are consistent with this data and this evaluation cannot
distinguish between them:

1. The cases really are mostly lawful conduct — plausible, since 5 of 7 are
   ordinary arrests and tactical engagements, and the L1 layer is designed to
   over-fire.
2. The Judge prompt is calibrated toward exoneration — the Prosecution prompt
   contains explicit "you must emit" triggers and inference-from-absence
   instructions, so it produces speculative findings that a careful Judge should
   dismiss. The high dismissal rate may be the correct response to a deliberately
   noisy accuser.
3. Gemini-as-Judge systematically favours the more conservative argument
   regardless of merit.

Distinguishing these requires labelled ground truth, which this evaluation does
not have. Until then, **"neither side dominates" is a design claim, not a
measured result**, and the README's "bias by construction" line should be read
as an architectural intent rather than a validated property.

## 5. Red-team notes — three ways to fool SENTINEL today

**1. Paraphrase past the critical-event keyword bank.**
The L1 fastpath that produces sub-millisecond alerts for weapons, taser
deployment, shots fired and officer-down is literal substring matching. I wrote
22 plausible bodycam phrasings for the five categories it claims to cover and
replayed them through the real router: **0 of 22 were caught** (0/15 English,
0/7 Spanish/Dutch/Italian). Worse, **11 of the 22 were classified `none` locally
and never reach any LLM at all** — including `"Shots! Shots!"`,
`"Man down, man down"`, `"I fired two rounds"` and `"Voy a disparar"`. The cause
is the ≤4-word heuristic in [router_agent.py:259-261](../agents/router_agent.py#L259-L261),
which hard-drops any short utterance with no keyword hit; it silently discards
**53 of the 199 real utterances (26.6%)** in the demo set. Radio-terse speech —
exactly the register in which critical events are announced — is the worst case
for this rule.

**2. Rule-pack gaps, and citations outside the pack.**
Only three packs exist. `nl_politie_inval` and `es_robbery_shootout` both run
under the generic 30-rule EU pack, so a Dutch or Spanish interaction is audited
against ECHR articles with no national police statute in the index — nothing in
the output flags that the applicable domestic law was never consulted. The
retrieval layer also has no abstention: it always returns a top-3, so an
off-domain query still yields confident-looking citations. Rule-ID validity was
checked directly — of 109 citations across all runs, **2 pointed at a rule that
does not exist in any pack** (`US-ARREST-PC`, hallucinated by the batch
Prosecution and then carried into a Judge ruling verbatim). The rapid layer
rejects invented rule IDs; the batch council does not.

**3. Feed it speech that is not the interaction.**
SENTINEL has no notion of who is speaking or whether the audio is the event.
`es_robbery_shootout` demonstrates this end-to-end in production: the input is a
Spanish-language third-person *recap* of a 2022 Salisbury, North Carolina
shooting (`"11 heridas en su cuerpo. Seis balas atravesaron su cuerpo"`), not
bodycam audio. The pipeline processed 93 narration utterances, fired 23 critical
alerts — **20 of them the `CRIT-GENERIC` fallback, meaning the LLM router called
them critical and the keyword bank could not say why** — and produced 8 deep
findings including a `critical` ECHR Article 2 right-to-life violation against
officers, for a **US incident audited under the EU rule pack**. A narrator
describing violence is indistinguishable from officers committing it. The same
gap is reachable deliberately: because the Prosecution prompt infers violations
from the *absence* of procedural language in prior context, a speaker who simply
narrates `"I already read you your rights"` suppresses the mandatory Miranda
trigger, and nothing in the pipeline can verify that from audio.

## 6. Scope & limits

- 7 hand-picked cases; not a representative sample of bodycam footage. One of
  the 7 is not bodycam footage at all (see red-team note 3)
- The LLM layers were **not** re-run for this report — no API keys and no source
  media in this checkout. Reproducibility for those layers rests on 2 archived
  runs (US) / 1 (EU), which is not a substitute for a 3× repeat under identical
  configuration
- Only the deterministic layers (L0 keyword, L1 fastpath, L2 retrieval) were
  genuinely re-executed: 5 runs × 199 utterances, 0 drift
- No comparison against human expert reviewers yet, and no labelled ground truth,
  so the 82% Defense rate cannot be scored as correct or incorrect
- No independent legal validation; verdicts are recommendations for a human
  reviewer, not decisions
- 1 of 7 cases produced no verdict at all due to a Judge JSON failure, and that
  failure was not caught by any automated check before this evaluation
- Latency figures are single-observation: keyword fastpath 0–2133 ms end-to-end
  per alert (median 1377 ms, including the router LLM call that precedes it),
  LLM rapid path 4497/4681/5991 ms, Judge consolidation 3.0–40.7 s
  (median 18.0 s), Vision 24.6–39.8 s

**Next milestones**

1. Make the LLM layers re-runnable in CI on 3 seeds per case, and publish the
   verdict-stability matrix that this report could only approximate
2. Expert-comparison study on 20 cases with two independent reviewers, to convert
   the 82% Defense rate into a precision/recall figure
3. Adversarial audio red-team: extend the 22-probe paraphrase set to ~200 probes
   per jurisdiction and measure end-to-end (router LLM included), not just the
   keyword bank
4. Per-jurisdiction accuracy breakdown, blocked until NL and ES have their own
   rule packs instead of the generic EU fallback
5. Fail loudly: treat a Judge parse failure and a Prosecution model fallback as
   pipeline errors rather than silent degradations

---

### Reproducing the deterministic measurements

The replay harness reads only committed artifacts — no API keys, no media:

```bash
pip install sentence-transformers faiss-cpu numpy

python scripts/replay_eval.py 5    # §2 — 5 runs × 199 utterances, drift check
python scripts/eval_report.py      # §3, §4 — funnel, judge balance, rule-ID validity
python scripts/redteam_probe.py    # §5.1 — 22-probe paraphrase evasion set
```

Source data: `results/live/*_session.json` (7 live sessions, full event logs),
`results/council/*_council.json` (batch council runs), `case_law/police_*.json`
(rule packs).
