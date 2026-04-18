# Fitness Bridge AI 🏋️

> **A local-first, multiagent AI fitness coach** that connects your Strava workouts, Fitbit biometrics, and Hevy training logs to give you personalised coaching that is grounded in real data — not generic advice.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-green)](https://github.com/langchain-ai/langgraph)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20%7C%20Qwen2.5-orange)](https://ollama.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js-black)](https://nextjs.org)
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
┌─────────────────────────────────────────────────────────┐
│  Next.js Frontend (localhost:3000)                       │
│  Dashboard · AI Coach · History · Settings               │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────┐
│  FastAPI Backend (localhost:8000)                        │
│  /api/workouts · /api/chat · /api/sync · /api/tokens    │
├─────────────────────────────────────────────────────────┤
│  LangGraph Router (classifies intent)                   │
│   ├──► Readiness Agent (sleep · HRV · resting HR)       │
│   ├──► Progress Agent  (ACWR · volume · history)        │
│   └──► Coach Agent     (synthesises both streams)       │
│              │                                          │
│         Tool Calls → Analysis Layer (pure Python)       │
│              │                                          │
│         API Clients (Strava · Fitbit) + diskcache       │
├─────────────────────────────────────────────────────────┤
│  Token Vault (SQLite) · Memory Manager · Guardrails     │
└─────────────────────────────────────────────────────────┘
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
| Backend | `fastapi` + `uvicorn` — REST API, background tasks |
| Frontend | `next.js` + `framer-motion` — responsive SPA with animations |
| LLM | `ollama` + `langchain-ollama` (Qwen3.5:4b, local) |
| Orchestration | `langgraph` — stateful agent graphs |
| API caching | `diskcache` — persistent, TTL-aware |
| API retries | `tenacity` — exponential backoff |
| Data | `pandas` |
| Validation | `pydantic` |
| DB | `sqlite3` — chat history, semantic memory, workout indexing, **token vault** |
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
- Node.js 18+ (for the frontend)
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

# Frontend setup
cd frontend && npm install && cd ..
```

### 2. Configure API credentials

Run the Python token setup utility. It opens your browser for OAuth and saves tokens directly to the **SQLite database vault**:

```bash
python scripts/setup_tokens.py
```

Alternatively, for advanced troubleshooting: `.\scripts\setup_tokens.py` automatically captures redirects.

### 3. Start Ollama

```bash
ollama pull qwen3.5:4b
ollama serve
```

### 4. Run the app

```bash
# Terminal 1 — Backend (FastAPI)
python main.py

# Terminal 2 — Frontend (Next.js)
cd frontend && npm run dev
```

Backend: http://localhost:8000 · Frontend: http://localhost:3000

### 5. Run the test suite

```bash
# Run all phases in order (stops on first failure)
python scripts/run_tests.py

# Or run pytest directly from the root
pytest

# Run a specific phase
pytest tests/phase-tests/test_phase04_analysis.py -v
```

---

## Documentation

For deep dives into the system, see the modular guides in the `docs/` directory:

- [**System Architecture**](docs/architecture.md) — Multiagent design, data flow, and memory system.
- [**Setup Guide**](docs/setup.md) — Prerequisites, API configuration, and token acquisition.
- [**Running the App**](docs/running.md) — How to start the FastAPI backend and Next.js frontend.
- [**Testing Guide**](docs/testing.md) — Phase-based testing, AppTest framework, and instrumentation.
- [**API & Module Reference**](docs/api_reference.md) — Algorithms, sync engine details, and schema definitions.


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
├── main.py                 # FastAPI backend entrypoint
├── config.py               # All constants and env loading
├── requirements.txt
├── AGENTS.md               # AI agent instructions
├── frontend/               # Next.js frontend (monorepo)
│   ├── app/
│   │   ├── layout.js       # Root layout with sidebar nav
│   │   ├── page.js         # Dashboard (animated, Framer Motion)
│   │   ├── globals.css     # Design system (dark mode)
│   │   ├── coach/page.js   # AI Coach page
│   │   ├── history/page.js # History page
│   │   └── settings/page.js# Settings page
│   └── package.json
├── scripts/
│   ├── setup_tokens.py     # Python OAuth setup → saves to DB vault
│   ├── run_tests.py        # Phase-ordered test runner
│   └── clear_chats.py      # Database cleanup utility
├── src/
│   ├── clients/            # Strava + Fitbit API wrappers (DB-backed tokens)
│   ├── parsers/            # Hevy plaintext → structured data
│   ├── analysis/           # Pure Python scoring + strength analytics
│   ├── memory/             # Three-tier memory system
│   ├── guardrails/         # Input + output validation
│   ├── agents/             # LangGraph router + specialists
│   ├── sync/               # Multi-source sync engine (Strava + Fitbit)
│   └── utils/              # Database, cache, logging, formatting
├── tests/
│   ├── conftest.py         # Fixtures + DB isolation
│   └── phase-tests/        # Phase00–07 pytest suites
└── docs/
    ├── RULES.md            # Developer coding rules
    ├── architecture.md     # NEW: System design
    ├── setup.md            # NEW: Installation & API config
    ├── running.md          # NEW: Start instructions
    ├── testing.md          # NEW: Test guide
    └── api_reference.md    # NEW: Module documentation
```

---

## UI Architecture

### Next.js Frontend (Primary)

**`main.py`** (FastAPI) serves the backend; **`frontend/`** (Next.js) provides the responsive UI:

| Page | Purpose | Key Features |
|---|---|---|
| **Dashboard** | Training overview | Animated stat cards, workout table, sync button; Framer Motion staggered animations; token status badges |
| **Coach** | AI chat agent | (In progress) Streaming chat interface |
| **History** | Workout browser | (In progress) Filterable workout list |
| **Settings** | Credentials & controls | Token vault status, API connection management |

### Visual Design Principles

- **Dark mode design system** with CSS custom properties (`globals.css`)
- **Framer Motion** for spring animations, staggered reveals, hover effects, and micro-interactions
- **Responsive grid layout** with fixed sidebar navigation
- **Source badges** — colour-coded Strava / Fitbit tags on workout rows
- **Server-side filtering** via FastAPI endpoints; client-side for JSON columns

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

Tokens are stored in a **SQLite database vault** (`api_tokens` table) instead of `.env` files. This solves the "rotating token" problem documented in `docs/learnings/fitbit_api.md` — tokens survive process restarts and are atomically updated.

| Level | What it does |
|---|---|
| **`scripts/setup_tokens.py`** | Python OAuth setup — saves tokens directly to DB vault |
| **App auto-refresh** | `StravaClient` and `FitbitClient` check expiry on every request, refresh using the vault, and immediately persist new tokens |
| **`GET /api/tokens/status`** | API endpoint showing vault token presence per provider |

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

- Full AI Coach chat interface in Next.js
- Complete History page with advanced filtering
- In-app OAuth re-authorization flow
- Vector search over session history for semantic queries
- Nutrition integration (MyFitnessPal / Cronometer)
- Training plan generator
- Exercise substitution engine
- Weekly digest / notification system
- Light theme toggle
- Android port — React Native + FastAPI backend + Gemini Nano
- Upstash Redis for serverless deployment

---

## License

MIT
