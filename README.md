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
| UI | `streamlit` |
| DB | `sqlite3` — chat history + semantic memory |

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
pytest
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
├── requirements.txt
├── scripts/
│   └── SETUP.bat           # One-click environment setup
├── src/
│   ├── clients/            # Strava + Fitbit API wrappers
│   ├── parsers/            # Hevy plaintext → structured data
│   ├── analysis/           # Pure Python scoring algorithms
│   ├── memory/             # Three-tier memory system
│   ├── guardrails/         # Input + output validation
│   └── agents/             # LangGraph agents + tools
├── ui/
│   ├── dashboard.py        # Training overview tab
│   └── chat.py             # AI coach chat tab
├── tests/                  # pytest test suite
└── docs/                   # Technical documentation
```

---

## Future Roadmap

- OAuth UI flow for token refresh (currently manual via `.env`)
- Vector search over session history for semantic queries
- Nutrition integration (MyFitnessPal / Cronometer)
- Android port — Flutter frontend + FastAPI backend + Gemini Nano

---

## License

MIT
