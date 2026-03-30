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

---

## Tech Stack

| Concern | Library |
|---|---|
| LLM | `ollama` + `langchain-ollama` (Qwen2.5:4b, local) |
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
| **Fitbit** | Sleep duration, efficiency, HRV (RMSSD), resting heart rate |

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

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your API tokens
```

### 3. Start Ollama

```bash
ollama pull qwen2.5:4b
ollama serve
```

### 4. Run the app

```bash
streamlit run app.py
```

### 5. Run the test suite

```bash
# Run all phases in order (stops on first failure)
python run_tests.py

# Or run pytest directly
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
├── app.py                  # Streamlit entrypoint, multipage navigation
├── config.py               # All constants and env loading
├── requirements.txt
├── scripts/
│   └── SETUP.bat           # One-click environment setup
├── src/
│   ├── clients/            # Strava + Fitbit API wrappers
│   ├── parsers/            # Hevy plaintext → structured data
│   ├── analysis/           # Pure Python scoring algorithms
│   ├── memory/             # Three-tier memory system
│   ├── guardrails/         # Input + output validation
│   ├── agents/             # LangGraph router + specialists
│   ├── sync/               # Background sync engine + ingestion
│   └── utils/              # Database, cache, logging, tokens
├── ui/
│   ├── chat.py             # Message rendering + streaming
│   ├── dashboard.py        # Training metrics & visual design
│   ├── shared.py           # Reusable helpers (format_set, sync)
│   └── pages/
│       ├── coach.py        # AI coach session selector
│       ├── history.py      # Workout browser + filters
│       ├── settings.py     # Credentials & sync controls
│       └── diagnostics.py  # Router metrics & sync health
├── tests/
│   ├── conftest.py         # Fixtures + DB isolation
│   └── phase-tests/        # Phase00–08 pytest suites
└── docs/                   # Technical documentation
```

---

## UI Architecture

### Multipage Navigation

**app.py** wires five pages with shared session state and background sync:

| Page | Purpose | Key Features |
|---|---|---|
| **Dashboard** | Training overview | ⚡ Readiness, 🏋️ Volume, 📊 ACWR, 🗓️ Sessions; last workout split view |
| **Coach** | AI chat agent | Session picker, streaming responses, message history |
| **History** | Workout browser | Date/title/volume filters, muscle-group selector, pagination, exercise details |
| **Settings** | Credentials & controls | Manual sync, cache clear, connection status lights |
| **Diagnostics** | Observability | Router metrics (heuristic hit rate), last sync timestamps, reset button |

### Visual Design Principles

- **Bordered containers** for metric cards (`st.container(border=True)`)
- **Icons + colour coding** for readiness zones (green=ready, yellow=caution, red=overtrained)
- **Two-column splits** for space efficiency (e.g., last workout: left=exercises, right=summary)
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

`src/sync/engine.py` handles background and manual workout ingestion:

- **Idempotent upsert**: Workouts matched by Strava activity ID; duplicates are safe
- **Hevy parsing**: Extracts exercises, sets, volume from task descriptions
- **Data enrichment**: Attaches readiness score, sleep, HRV for each date
- **Background daemon**: Runs every 2 hours; respects sync lock to avoid overlap
- **Cache bypass**: Manual sync clears diskcache to force fresh API data

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

## Future Roadmap

- OAuth UI flow for token refresh (currently manual via `.env`)
- Vector search over session history for semantic queries
- Nutrition integration (MyFitnessPal / Cronometer)
- Android port — Flutter frontend + FastAPI backend + Gemini Nano

---

## License

MIT
