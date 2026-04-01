# Fitness Bridge AI 🏋️

> **A local-first, multiagent AI fitness coach** that connects your Strava workouts, Fitbit biometrics, and Hevy training logs to give you personalised coaching that is grounded in real data — not generic advice.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-green)](https://github.com/langchain-ai/langgraph)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20%7C%20Qwen2.5-orange)](https://ollama.com)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What it does

Fitness Bridge AI listens to your body and your training history, then answers questions like:

- *"Am I recovered enough to train hard today?"*
- *"How has my bench press been progressing over the last 6 weeks?"*
- *"My ACWR is trending high — what should I change this week?"*

Every answer is backed by numbers computed from your own data. The LLM narrates; the algorithms decide.

---

## Architecture

```
User Query
    │
    ▼
Input Guardrail (keyword + LLM classifier)
    │
    ▼
LangGraph Router (classifies intent)
    │
    ├──► Readiness Agent (sleep · HRV · resting HR)
    ├──► Progress Agent (ACWR · volume · exercise history)
    └──► Coach Agent    (synthesises both streams)
              │
              ▼
         Tool Calls → Analysis Layer (pure Python algorithms)
                              │
                         API Clients (Strava · Fitbit)
                              │
                         diskcache (1h TTL)
    │
    ▼
Output Guardrail (number cross-check)
    │
    ▼
Memory Manager (save turn · summarise · extract facts)
    │
    ▼
Response → Streamlit UI
```

**Core design principles:**
1. **Algorithms own the analysis. LLM owns the narration.** No business logic inside prompts.
2. **Cache aggressively at the edges.** All API calls are wrapped with a 1-hour diskcache TTL.
3. **Each agent has one job.** The Router classifies; specialists handle completely.
4. **Multi-source, single schema.** Strava and Fitbit workouts coexist with a composite key `(source, activity_id)`.

---

## Tech Stack

| Concern | Library |
|---|---|
| LLM | `ollama` + `langchain-ollama` (Qwen3.5:4b, local) |
| Orchestration | `langgraph` — stateful agent graphs |
| API caching | `diskcache` — persistent, TTL-aware |
| API retries | `tenacity` — exponential backoff |
| Data | `pandas` |
| Validation | `pydantic` |
| UI | `streamlit` 1.41.1 — multipage, caching, AppTest |
| DB | `sqlite3` — chat history, semantic memory, workout indexing |
| Testing | `pytest` 9.0.2 + `langsmith` instrumentation |

---

## Data Sources

| Source | What it provides |
|---|---|
| **Strava** | Activity metadata, workout title |
| **Hevy** (via Strava description) | Exercise names, sets, reps, weights |
| **Fitbit Biometrics** | Sleep duration, efficiency, HRV (RMSSD), resting heart rate |
| **Fitbit Activities** (Pixel Watch) | Tracked workouts — Badminton, Walk, Treadmill, Strength Training, Weightlifting, etc. with duration, calories, HR zones, distance |

---

## Memory Architecture (Three Tiers)

| Tier | Storage | Lifetime |
|---|---|---|
| Short-term | SQLite `messages` table, last N turns | Per session |
| Long-term | SQLite `messages` with `role='summary'` | Compressed whenever history > 20 messages |
| Semantic | SQLite `semantic_facts` table | Persistent — injuries, goals, preferences |

---

## Quickstart

### Prerequisites

- Python 3.13
- [Ollama](https://ollama.com/) installed and running
- Strava API credentials
- Fitbit API credentials (Personal app type for HRV access)

### 1. Environment Setup

```bash
# Windows — run the automated setup script
scripts\SETUP.bat

# Or manually:
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API credentials

Run the interactive token setup script — it walks you through Strava and Fitbit OAuth, then writes all tokens directly to `.env`:

```powershell
.\scripts\GET_TOKENS.ps1
```

This opens your browser for each service's OAuth flow and saves your tokens automatically. See [`scripts/README.md`](scripts/README.md) for full details.

### 3. Start Ollama

```bash
ollama pull qwen3.5:4b
ollama serve
```

### 4. Run the app

```bash
streamlit run app.py
```

### 5. Run the test suite

```bash
# Run all phases in order (stops on first failure)
python scripts/run_tests.py

# Or run pytest directly from the root
pytest

# Run a specific phase
pytest tests/phase-tests/test_phase08_ui_dashboard.py -v
```

---

## Strava + Hevy Integration

Hevy exports workout data into the Strava activity **description** field as plain text. Fitness Bridge parses this with `src/parsers/hevy_parser.py` to extract structured sets, reps, and weights without any LLM involvement.

**Enable in Hevy:** Settings → Integrations → Connect Strava → Enable "Share activities"

---

## Readiness Score (0–100)

| Component | Weight | Source |
|---|---|---|
| Sleep duration + efficiency | 0–40 pts | Fitbit Sleep API |
| HRV vs. rolling baseline | 0–40 pts | Fitbit HRV API |
| Resting HR vs. baseline | 0–20 pts | Fitbit Heart Rate API |

---

## Project Structure

```
fitness-bridge/
├── app.py                  # Streamlit entrypoint
├── config.py               # All constants and env loading
├── pytest.ini              # pytest config (testpaths = tests)
├── requirements.txt
├── AGENTS.md               # AI agent instructions
├── README.md
├── scripts/
│   ├── README.md           # Script usage guide
│   ├── SETUP.bat           # One-click environment setup
│   ├── GET_TOKENS.ps1      # First-time Strava + Fitbit OAuth
│   ├── REFRESH_STRAVA.ps1  # Re-authorize Strava
│   ├── REFRESH_FITBIT.ps1  # Re-authorize Fitbit
│   ├── run_tests.py        # Phase-ordered test runner
│   ├── check_app_log.py    # Logger smoke test
│   └── test_log.py         # Logger path checker
├── src/
│   ├── clients/            # Strava + Fitbit API wrappers
│   ├── parsers/            # Hevy plaintext → structured data
│   ├── analysis/           # Pure Python scoring + strength analytics
│   │   ├── strength.py     # 1RM estimation, PR detection, muscle volume
│   │   ├── load.py         # ACWR, deload detection, overreach
│   │   ├── readiness.py    # Readiness scoring
│   │   └── dataset.py      # Multi-source dataset builder
│   ├── memory/             # Three-tier memory system
│   ├── guardrails/         # Input + output validation
│   ├── agents/             # LangGraph router + specialists
│   ├── sync/               # Multi-source sync engine (Strava + Fitbit)
│   └── utils/              # Database, cache, logging, tokens
├── ui/
│   ├── chat.py             # Message rendering + streaming + auto-titling
│   ├── dashboard.py        # Training metrics, heatmap, charts
│   ├── shared.py           # Reusable helpers (format_set, sync)
│   ├── styles.py           # Custom CSS injection
│   └── pages/
│       ├── coach.py        # AI coach + session management
│       ├── history.py      # Workout browser + multi-source filters
│       ├── settings.py     # Credentials, sync controls, token expiry, facts
│       └── diagnostics.py  # Router metrics, sync health, API quota
├── tests/
│   ├── conftest.py         # Fixtures + DB isolation
│   └── phase-tests/        # Phase00–08 pytest suites
└── docs/
    ├── RULES.md            # Developer coding rules
    └── technical_reference.md
```

---

## UI Architecture

### Multipage Navigation

**app.py** wires five pages with shared session state and background sync:

| Page | Purpose | Key Features |
|---|---|---|
| **Dashboard** | Training overview | ⚡ Readiness, 🏋️ Volume, 📊 ACWR, 🗓️ Sessions; time range toggle (7d/14d/30d/90d); calendar heatmap; HR zone + calorie + muscle volume charts |
| **Coach** | AI chat agent | Session picker, streaming responses, message history; rename (✏️) and delete (🗑️) sessions; dynamic auto-titling; routing visibility |
| **History** | Workout browser | Date/title/volume filters, source filter (Strava/Fitbit), muscle-group selector, pagination; source badges (🟠/🔵) |
| **Settings** | Credentials & controls | Manual sync, cache clear, connection status pills; 🔑 Token Expiry panel (live time-to-expiry with green/amber/red status); semantic fact management (view/edit/delete) |
| **Diagnostics** | Observability | Router metrics, Strava API quota usage, sync health for Strava + Fitbit activities |

### Visual Design Principles

- **Custom CSS** injected via `ui/styles.py` — chat bubbles, metric card gradients, status pills, source badges
- **Bordered containers** for metric cards (`st.container(border=True)`) with gradient backgrounds
- **Icons + colour coding** for readiness zones (green=ready, yellow=caution, red=overtrained)
- **Two-column splits** for space efficiency (e.g., last workout: left=exercises, right=summary)
- **Source badges** — 🟠 Strava / 🔵 Fitbit on workouts in History and Dashboard
- **Status pills** in sidebar (styled with CSS instead of emoji dots)
- **Expanders** for collapsible details (workouts, settings)
- **Server-side filtering** for performance (SQL WHERE clauses); client-side for JSON columns

### Database Filtering

`src/utils/database.py` now includes `get_workouts_filtered()` for the History page:

```python
def get_workouts_filtered(
    start_date: str,      # ISO format "2026-03-01"
    end_date: str,        # ISO format "2026-03-31"
    title_query: str,     # Case-insensitive LIKE match
    min_volume: float,    # kg threshold
    max_volume: float,    # kg threshold
    limit: int,           # Page size (default 10)
    offset: int           # Pagination offset
) -> List[dict]:
```

- **Server-side filtering**: Date range, title LIKE, volume thresholds
- **Client-side filtering**: Muscle groups (extracted from JSON)
- **Pagination**: Tracked in `st.session_state.history_page` with filter signature reset

---

## Sync Engine

`src/sync/engine.py` handles background and manual workout ingestion from **two sources**:

### Strava Sync
- **Idempotent upsert**: Workouts matched by `(source='strava', activity_id)`
- **Hevy parsing**: Extracts exercises, sets, volume from activity descriptions
- **Data enrichment**: Attaches readiness score, sleep, HRV for each date

### Fitbit Activity Sync
- Fetches tracked workouts from Pixel Watch 2 via `GET /1/user/-/activities/list.json`
- Maps Fitbit `activityTypeId` codes to categories: `strength`, `cardio`, `sport`, `walking`, `running`, `flexibility`, `other`
- Stores duration, calories, HR zones, distance alongside workout record
- Workouts keyed by `(source='fitbit', activity_id)` — no collision with Strava

### Common
- **Background daemon**: Runs every 2 hours (configurable via `BACKGROUND_SYNC_INTERVAL`); respects sync lock to avoid overlap
- **Cache bypass**: Manual sync clears diskcache to force fresh API data
- **Multi-source schema**: Composite primary key `(source, activity_id)` supports both sources in one table

---

## Token Management

Tokens are managed at three levels:

| Level | What it does |
|---|---|
| **`scripts/GET_TOKENS.ps1`** | First-time OAuth setup for both Strava and Fitbit |
| **`scripts/REFRESH_STRAVA.ps1`** | Re-authorize Strava when persistent 401s appear |
| **`scripts/REFRESH_FITBIT.ps1`** | Re-authorize Fitbit when persistent 401s appear |
| **App auto-refresh** | `StravaClient` and `FitbitClient` check expiry on every request and silently refresh using the stored refresh token |
| **`src/utils/token_writer.py`** | Writes refreshed tokens to both `.env` (persistence) and `os.environ` (live in-process use) |
| **Settings → 🔑 Token Expiry** | Live UI panel showing exact expiry time for both access tokens with colour-coded alerts |

See [`scripts/README.md`](scripts/README.md) for when and why to run each script.

---

## Testing: Phase00–08

**Test Strategy**: Ordered phase execution with test isolation fixtures.

| Phase | Scope | Count |
|---|---|---|
| **00** | Environment (packages, .env, paths) | 3 tests |
| **01** | Foundation (database init, cache) | 3 tests |
| **02** | API clients (Strava, Fitbit) | Manual only* |
| **03** | Hevy parser (structured set extraction) | 4 tests |
| **04** | Analysis algorithms (readiness, ACWR, load) | 7 tests |
| **05** | Sync engine + memory system | 5 tests |
| **06** | Guardrails (input/output validation) | 3 tests |
| **07** | LangGraph agents (router + tools) | 5 tests |
| **08** | UI pages (Streamlit AppTest) | 14 tests |

*Phase 02 requires live credentials; see `test_phase02_clients_and_tokens.py` for manual flow.

**Phase08 UI Tests** use `AppTest` with 10-second timeouts to accommodate LangGraph compilation:

- `test_phase08_ui_dashboard.py` — Empty state, data state, expander presence
- `test_phase08_ui_coach.py` — Page load, session creation, session picker options
- `test_phase08_ui_history.py` — Filter workflows, pagination, expander interaction
- `test_phase08_ui_settings.py` — Sync dispatch, cache clear dispatch
- `test_phase08_ui_diagnostics.py` — Metrics display, reset button dispatch

**Test Fixtures** (conftest.py):

- `fresh_db(tmp_path)` — Ephemeral temp database per test, auto-cleanup
- `workout_factory()` — Seeded workout generator with field overrides
- `workout_batch_factory()` — Creates N workouts spanning multiple dates

All fixtures ensure test isolation; no test pollution across runs.

---

## Analysis Capabilities

### Strength Analytics (`src/analysis/strength.py`)
- **1RM Estimation** — Epley formula (`weight × (1 + reps / 30)`) from Hevy exercise data
- **Personal Record Detection** — Scans all exercises to find max estimated 1RM and max session volume
- **Progressive Overload Tracking** — Compares last 3 vs. first 3 instances of an exercise; classifies as progressing/maintaining/regressing
- **Muscle Group Volume** — Maps exercises to muscle groups and aggregates weekly volume per group

### Load & Recovery (`src/analysis/load.py`)
- **ACWR** — Acute:Chronic Workload Ratio with zone classification
- **Deload Detection** — Flags weeks where volume dropped >30% from the prior week
- **Overreach Detection** — Warns when weekly volume exceeds baseline threshold

---

## Chat Management

- **Dynamic auto-titling**: After the first assistant response, the LLM generates a 3–5 word session title
- **Rename**: ✏️ button next to session picker to rename any session
- **Delete**: 🗑️ button with confirmation dialog — cascade deletes all messages
- **Session picker**: Shows dynamic titles with `format_func`

---

## Future Roadmap

- In-app OAuth re-authorization flow (currently via `scripts/REFRESH_*.ps1`)
- Vector search over session history for semantic queries
- Nutrition integration (MyFitnessPal / Cronometer)
- Training plan generator
- Exercise substitution engine
- Weekly digest / notification system
- Dark/light theme toggle
- Android port — Flutter frontend + FastAPI backend + Gemini Nano

---

## License

MIT
