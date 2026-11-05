# SENTINEL

**Adversarial AI Court for Police Bodycam**

[sentinel-audit.co](https://sentinel-audit.co) · Milan AI Week 2026

🌐 [Live demo](https://sentinel-audit.co/) · 📄 [Slides](https://storage.googleapis.com/lablab-static-eu/presentations/submissions/octgaogix566cpvjlul7vs5w/octgaogix566cpvjlul7vs5w-1779198324896_msejh8vwzkjwydufthllxv2t.pdf)

🏆 Prize winner, AI Agent Olympics, Milan AI Week 2026 (2,382 participants, 726 teams · 3rd place, Featherless AI track)

## 30-second tour

The fastest way to understand SENTINEL is to watch the adversarial loop in action:

→ **[Open the us_video3 demo](https://sentinel-audit.co/demo/us_video3?autoplay=instant&speed=10)**: a US bodycam case where Prosecution flagged a HIGH-severity Fourth Amendment seizure, Defense rebutted it, and the Judge reduced the verdict to LOW after weighing both arguments.

→ **[Browse all 7 cases](https://sentinel-audit.co/demo)**: four jurisdictions (US / Italy / Netherlands / Spain), all landing on the officer-justified side after adversarial review.

## Why this exists

Tens of millions of police interactions are recorded on bodycams every year across the US, EU, and Italy. Less than 1% are ever audited. When a complaint arrives months later, the officer's written report is the de-facto ground truth.

SENTINEL is the audit layer that should have always existed: an adversarial multi-agent court that processes every recording, cites the exact utterance and the exact bodycam frame, and produces a defensible verdict in minutes.

## Bidirectional by design

The Defense agent has equal weight to the Prosecution. Across our **seven demo cases in four jurisdictions**, every verdict lands on the officer-justified side after adversarial review: six are fully `officer_justified`, and the seventh (`us_video3`) is `mixed / LOW` after the Defense dismissed a Prosecution claim that had been flagged HIGH. This includes a US case where narcotics found in the vehicle established probable cause for a search the Prosecution had flagged as a Fourth Amendment violation, and a Dutch tactical entry where Vision evidence justified the use of force.

SENTINEL is an audit layer that protects honest officers from false complaints and citizens from real misconduct. Both sides need it. The Judge's reasoning is fully drillable on every ruling.

## Architecture

```
┌──────────────────────────────────────────────┐
│   LAYER 1 — RAPID ALERTS  (per utterance)    │
│   Featherless · keyword fastpath · ~5ms      │
│   Live alerts surface in UI in under 2s      │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│   LAYER 2 — VISUAL CONTEXT                   │
│   Gemini 3.1 Pro · multimodal, on GCS URI    │
│   restraints, weapons drawn, force,          │
│   subject compliance — all timestamped       │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│   LAYER 3 — DEEP SCAN  (60s cadence)         │
│     ProsecutionAgent  (gpt-oss-120b)         │
│     DefenseAgent      (gemma-3-26B)          │
│   different model families, by design        │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│   LAYER 4 — VERDICT                          │
│   JudgeAgent  (Gemini 3.1 Pro)               │
│   per-rule rulings + reasoning + severity    │
└──────────────────────────────────────────────┘
```

Every agent writes to a unified `Trace`. Every verdict is fully drillable down to the exact utterance index and timestamp it cites.

## What makes a verdict defensible

Every ruling SENTINEL produces is drillable to the source:

- **Verdict** → cites specific **rule IDs** (e.g. `US-4A-SEIZURE`, `US-1A-RECORD-POLICE`)
- **Rule ID** → cites the **Judge's reasoning paragraph**
- **Reasoning** → cites specific **utterance indices** with **timestamps** (e.g. utterance #15 at t=15s)
- **Utterance** → links to the **diarized transcript** (S1 said exactly this at this second)
- **When video is available** → also cites **VisualContextAgent frames** with timestamps

No black box. Every claim sourced to the recording. Reproducible. Discoverable in court.

## The Speechmatics layer

SENTINEL is built around `Speechmatics realtime WebSocket streaming` as its core capability. Within 500ms of each finalized utterance, the Router Agent triages it against region-specific case law. Detected violations (by officers `or` by citizens) trigger live alerts in the UI in under 2 seconds. It works as a live compliance layer for the highest-stakes recorded interactions in society.

**TranscriptionAgent, Speechmatics (multi-feature pipeline):**

1. **Realtime WebSocket streaming + partials** → drives live UI updates instantly
2. **Speaker diarization (S1, S2, ...)** → council agents see exactly who said what
3. **Real-time translation (IT/NL → EN)** → normalizes EU/Italy jurisdictions into English
4. **Sentiment per utterance** → fed into Prosecution prompt as evidence of tone (aggressive / tense / neutral)
5. **Topic detection** → Router uses topics to dynamically pick the active rule pack
6. **Summarization** → generates the 2-sentence case card in the dashboard

All six features are wired into `agents/transcription_agent.py` and surface downstream: `prosecution_agent.py` literally cites `sentiment` per utterance when building its legal argument.

## The Gemini layer

The `JudgeAgent` runs on `Gemini 3.1 Pro` via Vertex AI. It reads the full prosecution report, every defense rebuttal, and the visual context, then issues per-rule rulings with weighted reasoning.

The **VisualContextAgent** also runs on Gemini 3.1 Pro, analyzing the bodycam MP4 directly (uploaded to GCS, referenced by URI). It returns timestamped key moments ("handcuffs visible at t=30s, Miranda read at t=155s, officer turns away at t=58s"), which are injected into all three text agents' prompts. The Judge can cite specific visual evidence alongside specific utterances, making every verdict defensible to a lawyer at the level of "at this exact second, the officer did this exact thing."

## The Featherless layer

`ProsecutionAgent` runs on `gpt-oss-120b` and `DefenseAgent` on `gemma-3-26B`, both hosted on Featherless. The dual-provider design is deliberate: prosecution and defense come from different model families so neither side dominates. Rapid Layer 1 also runs on Featherless for sub-2s turnaround.

## Deployment

The public demo is a **static Next.js build on Vercel**. Every session replays client-side from pre-computed JSON, with no backend, no server and no running cost. The demo cannot go down because there is nothing to keep running.

The FastAPI service (Speechmatics RT session manager, FAISS retrieval indexes, council orchestration) is only needed to audit a **fresh** recording. It runs on any VPS or container host with `uvicorn main:app`, in whichever region the customer's data residency requires.

## Live demo cases

| Session | Region | Verdict | Severity | Story |
| --- | --- | --- | --- | --- |
| **`us_video3`** | **US** | **mixed** | **LOW** | **Citizen filming in public park; Prosecution flagged HIGH 4A seizure, Defense rebutted, Judge reduced to LOW** |
| `us_aggression` | US | officer_justified | none | Suspect flees vape shop; Pennsylvania v. Mimms and fleeing-suspect doctrine dismiss all charges |
| `us_video1` | US | officer_justified | none | Sudden knife encounter; less-lethal force proportionate under Graham v. Connor |
| `us_video2_vision` | US | officer_justified | none | Warrantless search vindicated after vehicle console reveals hidden narcotics |
| `it_carabinieri_arrest` | IT | mixed | medium | Night apprehension under Codice di Procedura Penale and de-escalation protocols |
| `nl_politie_inval` | NL | officer_justified | none | Tactical room-clearing entry; Vision extracts hidden handgun threat, ECHR life protections held |
| `es_robbery_shootout` | ES | unclear | none | Armed robbery tactical engagement; 23 rapid alerts, 8 deep findings, but the Judge consolidation returned invalid JSON and adjudicated none of them. See [EVALS §2](docs/EVALS.md#2-verdict-reproducibility) |

Pre-computed sessions live in `results/live/*_session.json` and are mirrored into `web/public/samples/` for the static demo.

## Evaluation

[**docs/EVALS.md**](docs/EVALS.md) reports what the council actually does on these seven cases: verdict reproducibility, the alert funnel, how often the Judge sides with each side, and three ways to fool the system today.

Headline numbers: the deterministic layers show **0 drift across 5 runs × 199 utterances**; the funnel runs **38 rapid alerts → 30 deep findings → 5 surviving**; and the Judge sides with the Defense on **27 of 33 contested findings (82%)**. So far "neither side dominates" is a design intent; the numbers don't show it yet. The report also documents a Judge failure on 1 of 7 cases, a hallucinated rule ID, and a keyword bank that caught **0 of 22** paraphrased critical-event probes.

Every figure is reproducible from committed artifacts with no API keys: `python scripts/replay_eval.py 5`.

> **Note on recordings:** This repository contains **no source bodycam footage**. The `recordings/` directory is not committed and is excluded by `.gitignore`. The pre-computed `results/live/*_session.json` files replay any demo end-to-end without it. To run a fresh audit, supply your own recording.

## Quick start

```bash
# 1. Install
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in keys

# 2. Authenticate Google Cloud (Gemini Judge + Vision)
gcloud auth application-default login
gcloud config set project $GCP_PROJECT_ID

# 3. Build retrieval indexes (one-time, ~30s)
python -m tools.build_indexes

# 4. Run a full audit on a recording
python pipeline_v2.py path/to/your_recording.mp4 us

# 5. Precompute a live session (with Vision)
python -m tools.precompute_live \
  --transcript results/council/your_recording_council.json \
  --session-id us_custom --region us \
  --audio-file path/to/your_recording.mp4

# 6. Serve & stream
uvicorn main:app --host 0.0.0.0 --port 8000
curl -N "http://localhost:8000/api/live/replay/us_custom?real_time=true&speed=4.0"
```

Frontend:

```bash
cd web && npm install && npm run dev
```

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/audit/upload` | Upload audio/video for batch council |
| POST | `/api/audit/{job_id}/council/run` | Run council on uploaded job |
| GET | `/api/audit/{job_id}` | Job status + full council report |
| GET | `/api/live/sessions` | List precomputed live sessions |
| GET | `/api/live/replay/{session_id}` | SSE stream of session events |

SSE event kinds: `session_start`, `utterance`, `rapid_alert`, `deep_scan_started`, `deep_scan_completed`, `visual_context_ready`, `verdict_update`, `final_verdict`, `session_end`.

## Rule packs

✅ **US Police**: 4th/5th/6th Amendment, Graham v. Connor, Miranda v. Arizona, Terry v. Ohio, Illinois v. Wardlow, Pennsylvania v. Mimms

✅ **EU Police**: ECHR Articles 2, 3, 5, 8; EU procedural directives (used for NL Politie, ES Policía Nacional, and other EU jurisdictions)

✅ **Italy Police**: Codice di Procedura Penale, Legge 121/1981 (Carabinieri-specific)

Adding a new jurisdiction is one JSON file in `case_law/police_<code>.json` plus a rebuild of the FAISS indexes (`python -m tools.build_indexes`).

## Designed for regulated deployment

- **Data residency**: the audit service is self-hosted. Deploy it in the region your regulator requires; no data leaves the customer's tenancy.
- **Human in the loop**: Every ruling is a recommendation for an oversight officer to sign off on.
- **Full auditability**: every agent writes to a unified `Trace`. Reproducible. Discoverable in court.
- **Bias by construction**: Defense and Prosecution run on different model families (gemma vs gpt-oss) so neither side dominates the reasoning. So far this is a design intent: on the seven demo cases the Judge sides with the Defense on 82% of contested findings ([EVALS §4](docs/EVALS.md#4-adversarial-balance)).

## The engine beyond police

The same adversarial-council architecture powers a `corporate_security` vertical (EU GDPR / labor law), which shows the design carries over to other domains. Healthcare, insurance, HR, and procurement compliance workflows are downstream. See `prompts_corporate.py`.

## Tech stack

**Frontend**: Next.js 16, Tailwind v4, shadcn/ui
**Backend**: FastAPI, SQLModel, SSE-Starlette
**Speech**: Speechmatics RT + Batch (diarization, translation, sentiment, topics, summary)
**LLMs**: Featherless (gpt-oss-120b Prosecution, gemma-4-31B Defense, gemma-4-26B rapid, gemma-4-E4B router), Google Gemini 3.1 Pro (Judge, Vision)
**Retrieval**: FAISS + sentence-transformers over rule-pack JSON
**Vision**: Gemini 3.1 Pro on GCS-backed video URIs
**Deploy**: Vercel (static demo, no backend required) · any VPS for the audit service

## Cost per recording

On a 5–10 minute bodycam recording:

| Component | Cost |
| --- | --- |
| Vision (Gemini 3.1 Pro, single pass) | ~$0.05–0.10 |
| Judge consolidation (Gemini 3.1 Pro) | ~$0.02–0.05 |
| Prosecution + Defense (Featherless) | ~$0.01–0.03 |
| Speechmatics RT + Batch | included in plan |

**~$0.10–0.20 per recording.** Cheap enough to audit every interaction.

## Limitations & validation status

SENTINEL is a working prototype validated on seven demo cases across four
jurisdictions. It has not yet undergone independent legal review, a formal
accuracy study, or production deployment with a police oversight body.
"Defensible" here means every ruling is traceable to its evidence. No verdict has been
admitted in court so far. A structured evaluation (reproducibility
runs, inter-model agreement, false-positive analysis, expert comparison) is
published in [docs/EVALS.md](docs/EVALS.md) and expands with each iteration.

## License

[MIT](LICENSE)

## Author

**Vitalii Karasov** designs and ships AI systems for document-heavy operations, and measures them before they go live. Client work: [drawing intake, New York](https://karasov.co/case-studies/architectural-drawing-intake-new-york) (54 of 56 sheets filed with no person; [how it was measured](https://karasov.co/case-studies/drawing-intake-evaluation)) and [ATAMAN Studio, Los Angeles](https://karasov.co/case-studies/ataman-studio) (10,000+ production runs).

[karasov.co](https://karasov.co) · [LinkedIn](https://www.linkedin.com/in/vitaliikarasov/) · [Telegram](https://t.me/karvitalii)
