# SOC Alert Automation System

[![Tests](https://github.com/sumitjha7727/AutoSOC/actions/workflows/tests.yml/badge.svg)](https://github.com/sumitjha7727/AutoSOC/actions/workflows/tests.yml)

A Python/Flask multi-agent system that automates Level-1 SOC alert triage: it takes a
security alert, gathers evidence from (mocked) IP reputation, geolocation, log, and
user-baseline sources, runs a rule-based risk-scoring engine to reach a verdict, simulates
contacting the affected user, auto-escalates confirmed threats, and streams the whole
process live to a web dashboard over Socket.IO.

Runs entirely offline — every external data source (IP reputation, geolocation, SIEM logs,
user directory, stakeholder email) is mocked from local JSON files, so there's no API cost
and no network dependency.

---

## Architecture

```
Dashboard (Flask + Socket.IO)
        |
        v
OrchestratorAgent -- coordinates the pipeline and records timing/health stats
        |
        +--> EvidenceGathererAgent   pulls IP reputation, geolocation, log, and user-baseline
        |                            evidence for the alert (from data/mock_*.json)
        |
        +--> InvestigationAgent      simulates contacting the affected user based on the
        |                            evidence collected (mock stakeholder response)
        |
        +--> VerdictAnalyzerAgent    scores the evidence 0-10 across four weighted factors,
        |                            produces a verdict + confidence + reasoning, and
        |                            auto-escalates on a TRUE_POSITIVE verdict
        |
        +--> HealthMonitorAgent      tracks per-agent call counts, timing, and errors
        |
        v
   SQLite (investigations, evidence, timeline_events, verdicts, escalations, reviews, resolved)
```

The investigation record is created synchronously (so the dashboard gets an ID immediately),
then the rest of the pipeline runs in a background task, streaming a `investigation_progress`
Socket.IO event after every step and `investigation_complete` at the end — the dashboard
updates live rather than blocking on one request. Every investigation writes a full evidence
trail and timeline to SQLite either way, visible via the `/api/*` endpoints.

A `TRUE_POSITIVE` verdict is auto-escalated immediately (idempotent — an investigation can
only be escalated once, whether that happens automatically or via the dashboard's manual
"Escalate" button, which stays available for analyst judgment calls on non-`TRUE_POSITIVE`
verdicts).

## Verdict scoring

`VerdictAnalyzerAgent` computes a 0-10 risk score from four independently-scored factors:

| Factor | Range | Basis |
|---|---|---|
| IP reputation | 0-3 | reputation score from `mock_ip_verdicts.json` |
| Geolocation | 0-2 | login location vs. the user's baseline (`never_accessed_from_countries` / `typical_login_locations`) |
| Log analysis | 0-3 | count of suspicious event types in the (alert-type-specific) mock log pattern |
| User baseline | 0-2 | whether the user is known, and whether their department is sensitive (IT/Security) |

Confidence is derived from how far the risk score sits from the decision boundary. Verdict:
`TRUE_POSITIVE` if risk >= `verdict.high_risk_score` (config.yaml, default 7.0) **and**
confidence >= `verdict.confidence_threshold` (default 0.75); `FALSE_POSITIVE` if risk <
`verdict.medium_risk_score` (default 4.0); otherwise `INCONCLUSIVE`. Every verdict comes with
a human-readable `reasoning` string explaining each factor's contribution.

This is a deterministic heuristic, not a machine-learning model — the point is a transparent,
explainable scoring pipeline in the style of a SOAR playbook, not statistical inference.

## Sample alerts and actual output

Verified by running the pipeline against every entry in `data/mock_alerts.json`:

| Alert | Type / Severity | User | Verdict | Risk | Confidence | Escalated |
|---|---|---|---|---|---|---|
| ALT-20260909-001 | Suspicious login from new location / HIGH | john.doe | TRUE_POSITIVE | 7.0/10 | 75% | Auto |
| ALT-20260909-002 | Malware detected / CRITICAL | jane.smith | TRUE_POSITIVE | 7.0/10 | 75% | Auto |
| ALT-20260909-003 | Unusual network traffic / MEDIUM | mike.johnson | INCONCLUSIVE | 4.0/10 | 75% | - |
| ALT-20260909-004 | Privilege escalation attempt / HIGH | admin | INCONCLUSIVE | 6.0/10 | 58% | - |
| ALT-20260909-005 | Normal activity / LOW | sarah.wilson | FALSE_POSITIVE | 0.0/10 | 95% | - |
| ALT-20260909-006 | Brute force attack / HIGH | robert.chen | TRUE_POSITIVE | 8.0/10 | 92% | Auto |
| ALT-20260909-007 | DNS tunneling / C2 beaconing / HIGH | priya.nair | INCONCLUSIVE | 5.0/10 | 58% | - |
| ALT-20260909-008 | Ransomware activity / CRITICAL | emma.davis | TRUE_POSITIVE | 8.0/10 | 92% | Auto |
| ALT-20260909-009 | Phishing link clicked / MEDIUM | james.wilson | INCONCLUSIVE | 5.0/10 | 58% | - |
| ALT-20260909-010 | Port scan detected / LOW | kevin.park | FALSE_POSITIVE | 3.0/10 | 92% | - |

Note DNS tunneling and phishing both land on `INCONCLUSIVE` rather than an automatic
`TRUE_POSITIVE`/`FALSE_POSITIVE` — that's intentional: both are classic "needs a human"
cases in real SOC work (legitimate DoH/CDN traffic can look like tunneling; a clicked link
isn't proof credentials were actually entered), and the scoring reflects that ambiguity
instead of forcing a confident call either way.

## Project layout

```
agents/                  5 agents: orchestrator, evidence_gatherer, verdict_analyzer,
                          investigation, health_monitor
config/settings.py        YAML config loader (config.yaml)
utils/database.py         SQLite access layer (7 tables, connection-safe)
utils/logging_config.py   Shared logging setup (console + logs/soc_automation.log),
                           used by both main.py and web/app.py
data/                     mock_alerts.json, mock_ip_verdicts.json, mock_user_baseline.json
                           (10 alerts spanning 10 attack/benign scenario types)
web/app.py                Flask app + REST API + Socket.IO
web/templates/, static/   Dashboard UI (vanilla JS, no build step)
test_*.py                 One test script per agent + test_complete_system.py (end-to-end)
main.py                   Standalone config/DB sanity-check entry point (the dashboard is
                           started via web/app.py, not main.py)
docker/                   Dockerfile + docker-compose.yml
```

## Quick start

```bash
cd "D:\Claude Cowork\SOC"
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python -m flask --app web.app run
```

Open http://127.0.0.1:5000, pick an alert from the dropdown, and click **Start Investigation** —
the agent pipeline runs in the background and streams live progress to the page, ending with
the verdict, full evidence trail, and timeline.

### Dashboard tabs

- **Dashboard** — pick an alert, start an investigation, watch it stream live, see the result.
- **Investigations** — full history, searchable by ID; click **View** on any row to reopen its
  details modal (evidence, reasoning, timeline, and the Escalate / Mark Resolved / Request
  Review actions).
- **Escalations** — every escalated incident, automatic or manual, with verdict/risk/confidence.
- **Resolved** — every incident marked resolved, with the verdict/alert type it was resolved from.
- **Reviews** — every incident flagged for manual review, same context.
- **Metrics** — live counts: total alerts, true/false positives, inconclusive, escalations.

## Running the tests

```bash
python test_complete_system.py      # full pipeline, all 10 alerts, DB verification
python test_evidence_gatherer.py
python test_verdict_analyzer.py
python test_investigation_agent.py
python test_health_monitor.py
python test_orchestrator.py
```

All six currently pass end-to-end against the real agent implementations (no mocked
singletons or stubbed assertions).

## REST API

```
GET  /health                        Health check (used by Docker/orchestration)
GET  /                              Dashboard page
GET  /api/alerts                    List available mock alerts
POST /api/start-investigation       Create an investigation and run the pipeline in the
                                     background; returns {investigation_id, status} immediately
GET  /api/investigations            List all investigations
GET  /api/investigation-details/<id> Investigation + evidence + timeline
POST /api/escalate-incident         Escalate an investigation (409 if already escalated)
POST /api/mark-resolved             Mark an investigation resolved
GET  /api/resolved                  List resolved incidents (with verdict/risk context)
POST /api/request-review            Request manual review
GET  /api/reviews                   List review requests (with verdict/risk context)
GET  /api/escalations               List escalations
GET  /api/metrics                   Dashboard metric counters
```

Socket.IO events: `investigation_started` (fired the moment the record is created),
`investigation_progress` (one per pipeline step, streamed live), `investigation_complete`
(final verdict), `incident_escalated`, `incident_resolved`, `review_requested`.

## Docker

```bash
docker build -f docker/Dockerfile -t soc-automation:1.0 .
cd docker && docker-compose up -d
```

See `docker/DOCKER_INSTRUCTIONS.md` for details.

## Known limitations (by design — this is a mock-data demo)

- All external data (IP reputation, geolocation, logs, user directory, stakeholder responses)
  is mocked from local JSON/lookup tables, not live APIs.
- No authentication — not intended to be exposed beyond localhost.
- Verdict scoring is a hand-tuned heuristic, not a trained model.
- SQLite, single-process — fine for a demo, not for concurrent production load.

## Roadmap ideas

- Swap mock evidence sources for real integrations (VirusTotal, a SIEM, an IdP) behind the
  same `EvidenceGathererAgent` interface.
- Add auth (OAuth2/JWT) and CSRF protection before exposing beyond localhost.
- Migrate the test scripts to a proper `pytest` suite (CI already runs them as-is on every push).
- Persist investigations to Postgres for multi-instance deployment.
