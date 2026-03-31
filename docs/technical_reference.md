# Technical Documentation — Fitness Bridge AI

This document is the developer reference for the Fitness Bridge AI codebase. It covers architecture decisions, module contracts, data flow, and extension points.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Module Reference](#2-module-reference)
3. [Data Flow: End-to-End Request](#3-data-flow-end-to-end-request)
4. [Memory System](#4-memory-system)
5. [Guardrail System](#5-guardrail-system)
6. [Analysis Algorithms](#6-analysis-algorithms)
7. [UI Layer](#7-ui-layer)
8. [Sync Engine](#8-sync-engine)
9. [API Clients](#9-api-clients)
10. [Agent Layer](#10-agent-layer)
11. [Configuration Reference](#11-configuration-reference)
12. [Testing Guide](#12-testing-guide)

---

## 1. System Overview

Fitness Bridge AI is a **multiagent system** built on [LangGraph](https://github.com/langchain-ai/langgraph) that integrates three data sources — Strava, Fitbit, and Hevy — to deliver personalised fitness coaching via a conversational Streamlit interface.

### Guiding Principles

| # | Principle | Implication |
|---|---|---|
| 1 | Algorithms own analysis, LLM owns narration | No business logic in prompts. All numbers come from Python. |
| 2 | Cache aggressively at the edges | diskcache wraps every API call. LLM calls are not cached. |
| 3 | Each agent has one job | Router routes. Specialists respond. No agent does both. |

---

## 2. Module Reference

### `config.py`

Single source of truth for all configuration. Every file imports from here. No other file calls `os.getenv()` directly.

**Key constants:**

| Constant | Default | Purpose |
|---|---|---|
| `CACHE_DIR` | `data/cache` | diskcache file location |
| `CACHE_TTL_SECS` | `3600` | API call cache lifetime (1 hour) |
| `DB_PATH` | `data/fitness_bridge.db` | SQLite database path |
| `SHORT_TERM_WINDOW` | `8` | Recent messages kept verbatim |
| `OLLAMA_MODEL` | `qwen3.5:4b` | LLM model identifier |
| `BACKGROUND_SYNC_INTERVAL` | `7200` (2h) | Background sync interval in seconds |

---

### `src/utils/cache.py`

Wraps [diskcache](http://www.grantjenks.com/docs/diskcache/) into a single shared instance.

```python
from src.utils.cache import cached, get_cache

@cached(ttl=3600, ignore=('self',))   # ignore='self' needed for class methods
def my_function(arg):
    ...
```

> **`ignore=('self',)`** must be passed when decorating class methods to prevent `self` from being included in the cache key, which would break memoization.

---

### `src/utils/database.py`

All SQLite operations. Four concerns: chat history, semantic memory, workout indexing, and sync metadata.

**Schema (v3 — multi-source):**

```sql
sessions(id TEXT PK, title TEXT, created_at DATETIME)

messages(
    id INTEGER PK AUTOINCREMENT,
    session_id TEXT FK,
    role TEXT,    -- "user" | "assistant" | "summary"
    content TEXT,
    created_at DATETIME
)

semantic_facts(
    id INTEGER PK AUTOINCREMENT,
    key TEXT UNIQUE,
    value TEXT,
    updated_at DATETIME
)

workouts(
    activity_id      TEXT NOT NULL,
    source           TEXT NOT NULL DEFAULT 'strava',   -- 'strava' | 'fitbit'
    workout_type     TEXT,                             -- 'strength' | 'cardio' | 'sport' | 'walking' | etc.
    date             TEXT NOT NULL CHECK (length(date) = 10),
    workout_title    TEXT,
    duration_min     REAL,
    total_volume_kg  REAL,
    exercise_count   INTEGER,
    set_count        INTEGER,
    exercises_raw    TEXT,     -- JSON serialised from Hevy parser
    muscle_groups    TEXT,     -- JSON list
    has_drop_sets    INTEGER,
    has_failure_sets INTEGER,
    sleep_hours      REAL,
    sleep_efficiency REAL,
    hrv_ms           REAL,
    resting_hr       REAL,
    readiness_score  REAL,
    readiness_label  TEXT,
    calories         REAL,     -- Fitbit activity calories
    hr_zones         TEXT,     -- JSON: [{"name":"Fat Burn","minutes":12}, ...]
    distance_km      REAL,     -- Fitbit GPS/step distance
    synced_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source, activity_id)
)

sync_meta(source TEXT PRIMARY KEY, last_synced_at DATETIME)
```

**Indexes:** `idx_workouts_date`, `idx_workouts_source`, `idx_messages_session`

**Key functions:**

- `upsert_workout(row)` — Idempotent write with composite key `(source, activity_id)`; safe to re-run
- `validate_workout_record(row)` — Normalises and validates all fields before upsert; defaults `source` to `'strava'`
- `get_workouts_filtered(start_date, end_date, title_query, min_volume, max_volume, limit, offset)` — Server-side filtering for History page
- `get_workout_dates(n_days)` — Training dates for the last N days (caches with TTL=3600)
- `create_session(title)` / `delete_session(session_id)` / `rename_session(session_id, title)` — Chat session CRUD
- `get_all_facts()` / `upsert_fact(key, value)` / `delete_fact(key)` — Semantic fact management

> `role="summary"` rows are written by `MemoryManager.maybe_summarise()` and excluded from `get_chat_history()`. They are stored in the same table for simplicity.

---

### `src/clients/strava_client.py` and `fitbit_client.py`

Thin HTTP wrappers around the Strava and Fitbit v1 APIs.

- Token refresh is triggered automatically on `__init__` (Strava: checks 401, Fitbit: checks `check_connection()`).
- All fetch methods are decorated with `@cached(ttl=3600, ignore=('self',))` and `@retry(...)`.
- Clients return **raw JSON** — no parsing logic lives here.

**Strava token note:** Strava refresh tokens do not expire, but access tokens live 6 hours. The client refreshes on startup but does not persist the new access token back to `.env`. For long-running sessions, restart the app if you get 401s.

**Strava quota tracking:** A thread-safe tracker counts API calls per 15-min window (limit: 100) and per day (limit: 1000). Warnings are logged at 80% of each limit. Current usage is visible on the Diagnostics page via `get_strava_quota()`.

**Fitbit token note:** Fitbit access tokens expire in 8 hours. Same caveat applies. HRV data requires a **Personal** app type in the Fitbit developer portal.

**Fitbit activity sync:** `get_activities(before_date, limit)` fetches tracked workouts from Pixel Watch 2 via the Activity Log List API. `ACTIVITY_TYPE_MAP` maps Fitbit `activityTypeId` codes to normalised categories (`strength`, `cardio`, `sport`, `walking`, `running`, `flexibility`, `other`).

---

### `src/parsers/hevy_parser.py`

Converts a Strava activity description (Hevy's plaintext export) into structured data.

**Input example:**
```
Bench Press (Barbell)
Set 1: 60 kg x 10
Set 2: 60 kg x 8 [Failure]

Pull Up
Set 1: 12 reps
```

**Output shape:**
```python
[
  {
    "name": "Bench Press (Barbell)",
    "muscle_group": "chest",
    "sets": [
      {"type": "weighted", "set_number": 1, "weight_kg": 60.0, "reps": 10, "tag": None},
      {"type": "weighted", "set_number": 2, "weight_kg": 60.0, "reps": 8, "tag": "Failure"}
    ],
    "total_volume_kg": 1080.0,
    "set_count": 2
  },
  ...
]
```

**Muscle group mapping** is a keyword-in-name lookup (`MUSCLE_MAP` dict). Extend `MUSCLE_MAP` to add new exercises. Unrecognised exercises return `"other"`.

---

### `src/analysis/readiness.py`

Pure Python. No LLM, no network calls.

```
Readiness Score (0–100) = sleep_score (0–40) + hrv_score (0–40) + resting_hr_score (0–20)
```

**HRV scoring** compares today's RMSSD against a hardcoded 45ms baseline. In a future iteration, replace this with a rolling 30-day average stored in `semantic_facts`.

**Return shape of `compute_readiness()`:**
```python
{
    "score": int,
    "label": str,
    "sleep_minutes": int,
    "sleep_hours": float,
    "sleep_efficiency": int,
    "hrv_ms": float | None,
    "resting_hr": int | None,
    "components": {"sleep": int, "hrv": int, "resting_hr": int},
    "recommendation": str
}
```

---

### `src/analysis/load.py`

ACWR (Acute:Chronic Workload Ratio) and deload detection.

```
ACWR = (sum of volume last 7 days) / (sum of volume last 28 days / 4)
```

| Zone | Range | Meaning |
|---|---|---|
| `undertrained` | ACWR < 0.8 | Training volume is too low |
| `optimal` | 0.8 ≤ ACWR ≤ 1.3 | Sweet spot |
| `caution` | 1.3 < ACWR ≤ 1.5 | Monitor closely |
| `overreach_risk` | ACWR > 1.5 | Reduce volume this week |

**Deload detection:** `detect_deload_weeks(df)` identifies weeks where total volume dropped >30% from the prior week. Returns a list of `{week_start, volume, prev_volume, drop_pct}`.

---

### `src/analysis/strength.py` ← NEW

Strength analytics: 1RM estimation, personal records, and muscle group volume tracking.

**1RM Estimation (Epley formula):**
```python
estimate_1rm(weight_kg, reps) → weight * (1 + reps / 30)
```

**Personal Record Detection:** `detect_prs(df)` scans all exercises across workouts and returns per-exercise records:
```python
{
  "Bench Press (Barbell)": {
    "best_1rm": 105.0,
    "best_volume": 3600.0,
    "best_1rm_date": "2026-03-28",
    "best_volume_date": "2026-03-25"
  }
}
```

**Progressive Overload Detection:** `detect_progressive_overload(df, exercise_name)` compares last 3 instances vs. first 3 to classify trend as `progressing` / `maintaining` / `regressing`.

**Muscle Group Volume:** `compute_muscle_group_volume(df)` maps exercises to muscle groups via `EXERCISE_MUSCLE_MAP` and returns `{"chest": 3600.0, "back": 2400.0, ...}`.

---

### `src/analysis/dataset.py`

Joins Strava + Fitbit + Hevy parser into a single per-day `pandas.DataFrame`.

`build_dataset(n_days)` is the main entry point called by agent tools. All tool calls with different `n_days` will create separate cache entries — this is intentional, since each agent needs a different window.

`build_fitbit_session_record(activity, fitbit_client)` handles Fitbit activity data, extracting duration, calories, HR zones, and distance for non-Hevy workouts.

**DataFrame columns:**

| Column | Type | Source |
|---|---|---|
| `date` | str | Strava `start_date_local` or Fitbit `startTime` |
| `workout_title` | str | Strava `name` or Fitbit `activityName` |
| `duration_min` | float | Strava `elapsed_time / 60` or Fitbit `activeDuration` |
| `total_volume_kg` | float | Summed from Hevy parser (0 for Fitbit activities) |
| `exercises_raw` | str (JSON) | Serialised Hevy parser output (null for Fitbit) |
| `muscle_groups` | str (JSON) | List of unique groups |
| `readiness_score` | int | `compute_readiness()` |
| `sleep_hours` | float | Fitbit sleep |
| `hrv_ms` | float | Fitbit HRV |
| `source` | str | `'strava'` or `'fitbit'` |
| `workout_type` | str | Mapped category from `ACTIVITY_TYPE_MAP` |
| `calories` | float | Fitbit activity calories |
| `hr_zones` | str (JSON) | Fitbit HR zone breakdown |
| `distance_km` | float | Fitbit GPS/step distance |

---

## 3. Data Flow: End-to-End Request

```
1. User types query in Streamlit chat
2. InputGuardrail.check(query) → blocked if off-topic or injection attempt
3. MemoryManager.build_context(session_id) → assembles system_context + recent_messages
4. AgentState initialised with messages + context
5. LangGraph.invoke(state) →
     a. router_node classifies intent (readiness / progress / coach / general)
     b. router_node sets `routed_to` (human-readable agent name) in state
     c. Conditional edge routes to correct specialist agent
     d. Specialist agent calls llm.bind_tools(tools).invoke(messages)
     e. LLM generates tool calls
     f. InterceptingToolNode executes tool calls, accumulates results into state["tool_data"]
     g. LLM receives tool results, generates final response
6. OutputGuardrail.validate_response(response, tool_data) → warns if numbers don't match
7. MemoryManager.save_turn() + maybe_summarise() + extract_and_store_facts()
8. Auto-title: If first exchange in session, LLM generates a 3–5 word session title
9. Response rendered in Streamlit with routing caption ("Routed to: Readiness Specialist")
```

---

## 4. Memory System

Three tiers, all backed by SQLite:

| Tier | Class | Read | Write |
|---|---|---|---|
| Short-term | `ShortTermStore` | `get_chat_history(session_id, limit=N)` | `save_message(session_id, role, content)` |
| Long-term | `LongTermStore` | SELECT WHERE role='summary' | INSERT with role='summary' |
| Semantic | `SemanticStore` | `get_all_facts()` | `upsert_fact(key, value)` |

`MemoryManager` is the only class agents interact with. It orchestrates all three stores and exposes three high-level methods:

- `build_context(session_id)` → returns `{"system_context": str, "recent_messages": list}`
- `save_turn(session_id, user_msg, assistant_msg)`
- `maybe_summarise(session_id, llm)` — triggers if `len(full_history) >= 20`
- `extract_and_store_facts(assistant_response, llm)` — runs after every response

---

## 5. Guardrail System

### Input Guardrail (`InputGuardrail`)

Three-stage check (fast → slow):

1. **Injection block** — hardcoded patterns like `"ignore previous"`, `"jailbreak"`
2. **Keyword fast-pass** — if any fitness keyword found → allow immediately
3. **LLM fallback** — only for ambiguous queries; asks the LLM `ALLOWED` / `BLOCKED`

Short queries (≤ 4 words) bypass keyword check and are always allowed.

### Output Guardrail (`OutputGuardrail`)

Extracts all numbers from the response text using regex, then checks that each significant number (> 7.0) appears within 5% tolerance in the `tool_data` dict. **This is a warning, not a blocker** — the response is returned even if a mismatch is found, but the issue is logged.

---

## 6. Analysis Algorithms

### Readiness Scoring

```
sleep_score     ∈ [0, 40]  based on total_minutes_asleep + efficiency_bonus
hrv_score       ∈ [0, 40]  based on hrv_value / baseline ratio
resting_hr_score ∈ [0, 20] based on delta from baseline HR
```

### ACWR (Acute:Chronic Workload Ratio)

```
acute_load  = sum of total_volume_kg for the last 7 days
chronic_load = sum of total_volume_kg for the last 28 days / 4
ACWR = acute_load / chronic_load
```

### Progressive Overload Check

Takes the last 6 appearances of an exercise, splits into two halves, compares average volumes:

```
pct_change = (last_half_avg - first_half_avg) / first_half_avg * 100
```

| Result | Condition |
|---|---|
| `progressing` | pct_change ≥ 5% |
| `maintaining` | -5% ≤ pct_change < 5% |
| `regressing` | pct_change < -5% |

### 1RM Estimation (Epley)

```
estimated_1rm = weight_kg * (1 + reps / 30)
```

Only applies to weighted sets. Bodyweight/duration exercises are skipped.

### Deload Week Detection

```
weekly_volumes = group by ISO week, sum total_volume_kg
drop_pct = (prev_week - current_week) / prev_week * 100
if drop_pct > 30%: flag as deload
```

### Muscle Group Volume

Aggregates `total_volume_kg` per exercise, mapped to muscle groups via `EXERCISE_MUSCLE_MAP` (keyword-in-name lookup). Returns `{"chest": 3600.0, ...}`.

---

## 7. UI Layer

Streamlit multipage navigation with five pages and custom CSS theming. All UI state is persisted in `st.session_state` or database queries. Background sync runs on startup + every 2 hours (configurable).

### `ui/styles.py` (CSS Injection) ← NEW

Central CSS module injected by `app.py` on every page load via `inject_css()`.

**Styled components:**
- Chat message bubbles with rounded corners and spacing
- Metric cards with gradient backgrounds (`#1e293b` → `#0f172a`)
- Connection status pills (green=connected, red=disconnected)
- Source badges (🟠 Strava orange / 🔵 Fitbit blue)
- Sidebar branding
- Button hover effects

### `app.py` (Entrypoint)

- Calls `validate_config()` and displays startup warnings
- Calls `inject_css()` for custom theming
- Calls `run_startup_sync()` (cache resource, runs once per session)
- Calls `start_background_sync()` (daemon thread, configurable interval)
- Initialises `session_id` in state before rendering navigation
- Wires five pages: Dashboard, Coach, History, Settings, Diagnostics

### `ui/dashboard.py` (Training Metrics)

**Layout:**

- Time range toggle (7d / 14d / 30d / 90d) at top — replaces hardcoded 28-day window
- 4-column metric cards: ⚡ Readiness, 🏋️ Volume (7d), 📊 ACWR, 🗓️ Sessions
- Two-column last workout: left=exercise list (using `format_set()` helper), right=summary card with source badge
- Calendar heatmap — GitHub-style contribution grid showing workout days
- Charts section: HR zone time-in-zone, calorie burn trend, muscle group volume breakdown
- Chart framing with `st.container(border=True)`

**Rendering helpers:**

- `_acwr_delta_color(zone)` → Maps zone to Streamlit delta_color (normal/inverse/off)
- `_render_metric_card(label, value, delta, delta_color)` → Bordered metric with delta
- `_render_last_workout_summary(last)` → Right-column summary with duration, volume, intensity
- `_render_calendar_heatmap(workout_dates, n_days)` → HTML heatmap grid
- `_render_hr_zone_chart(workouts)` → Bar chart of time-in-zone from Fitbit data
- `_render_calorie_chart(workouts)` → Line chart of daily calorie burn
- `_render_muscle_volume_chart(workouts)` → Horizontal bar chart per muscle group

**Dependencies:** `format_set()` from `ui/shared.py`; readiness/ACWR from analysis layer.

### `ui/pages/coach.py` (AI Chat)

**Layout:**

- Full-width session selector (no columns)
- Inline session controls: ✏️ Rename and 🗑️ Delete buttons with confirmation dialogs
- Caption below showing active session title
- Divider before chat body
- "+ New Chat" button creates session and reruns page

**Chat management:**
- Rename: text input in popover, calls `rename_session()`
- Delete: confirmation dialog with session title display, calls `delete_session()`, selects most recent remaining session
- Dynamic auto-titling: after first exchange, LLM generates 3–5 word title via `_auto_title_session()`

**Chat rendering:** Uses `ui/chat.py` for streaming message display. Shows routing caption ("Routed to: Readiness Specialist") after responses.

**State:** Session ID persists in `st.session_state`; messages fetched from database.

### `ui/pages/history.py` (Workout Browser)

**Filters (collapsible sidebar):**

- Date range picker (start/end date)
- Title search box (case-insensitive LIKE)
- Volume range sliders (min/max kg)
- Muscle group multiselect (client-side filtering from JSON)
- Source filter (All / Strava / Fitbit)

**Server-side filtering:**

Calls `get_workouts_filtered()` with `st.cache_data(ttl=60)`. WHERE clauses for date, title, volume.

**Client-side filtering:**

After server query, `_filter_by_muscle_groups()` removes workouts not matching selected groups. Source filter also applied client-side.

**Pagination:**

- PAGE_SIZE = 10
- Offset stored in `st.session_state.history_page`
- Filter signature detection resets pagination when filters change (avoids off-by-one)

**Summary metrics:**

- Total count, volume sum, avg readiness, display count

**Workout cards:**

Expanders showing title, date, volume, exercises with source badge (🟠/🔵). Fitbit-only workouts show duration, calories, HR zones, and distance instead of exercise details. Uses `_render_workout_card()` with nested exercise details via `format_set()`.

### `ui/pages/settings.py` (Credentials & Controls)

**Sections:**

- Connection status pills (Strava ✓/✗, Fitbit ✓/✗) via `get_connection_statuses()` — styled with CSS pills
- "Sync Now" button → calls `run_sync_with_lock(force=True)`, clears cache, reruns
- "Clear Cache" button → clears diskcache, reruns
- **Fact Management** section ← NEW: displays all semantic facts in editable data table; supports edit, delete, and manual add
- ℹ️ Help text for token refresh and troubleshooting

### `ui/pages/diagnostics.py` (Observability)

**Router metrics display:**

- Total Routed (counter)
- Heuristic Hits (counter)
- LLM Fallbacks (counter)
- Heuristic Rate % (calculated as heuristic_hits / total_routed)

Calls `get_routing_metrics()` from `src.agents.router` (thread-safe dict access).

**Strava API quota:**

Displays current 15-min and daily API call counts from `get_strava_quota()`. Shows usage as "X / limit" with percentage.

**Sync health:**

Fetches last sync timestamps for Strava, Fitbit (biometrics), and Fitbit Activities from database. Shows in readable format ("2 hours ago").

**Reset button:**

Calls `reset_routing_metrics()`, reruns page. Useful for seeing metrics over a specific period.

### `ui/shared.py` (Reusable Helpers)

**Formatting:**

- `format_set(set_data)` — Renders exercise set based on type (duration/weighted/bodyweight) with optional tags (e.g., "[Failure]")
- `parse_json_list(raw_value)` — Safely deserialises JSON with fallback to empty list

**Sync helpers:**

- `run_sync_with_lock(force)` — Thread-safe sync dispatch; clears cache if force=True
- `start_background_sync()` — Daemon thread, runs every `BACKGROUND_SYNC_INTERVAL` seconds (default 2 hours)
- `run_startup_sync()` — Cache resource, runs once per Streamlit session
- `get_connection_statuses()` — Returns Strava/Fitbit health with error capture

---

## 8. Sync Engine

`src/sync/engine.py` is the source of truth for workout ingestion and upsert from **multiple sources**.

**Key responsibilities:**

1. **Fetch from APIs** → Strava activities + Fitbit biometrics + Fitbit tracked activities
2. **Parse Hevy** → Extract exercises, sets, volumes from Strava activity descriptions
3. **Map Fitbit activities** → Convert `activityTypeId` to category via `ACTIVITY_TYPE_MAP`
4. **Enrich** → Attach readiness scores, sleep, HRV for each date
5. **Upsert** → Write to SQLite with composite key `(source, activity_id)` for conflict resolution
6. **Lock** → Thread-safe via `_sync_lock` to prevent concurrent runs

**Workflow:**

```python
engine.sync(force_api_refresh=False)
  ├── Check lock (skip if sync already running)
  ├── If force_api_refresh: clear diskcache
  ├── _sync_strava():
  │   ├── Fetch Strava activities (1h cache, wrapped)
  │   ├── Fetch Fitbit biometric data (1h cache, wrapped)
  │   ├── For each activity:
  │   │   ├── Parse Hevy description → exercises
  │   │   ├── Lookup Fitbit data for that date
  │   │   ├── Compute readiness score
  │   │   └── Upsert to workouts (source='strava')
  │   └── Update sync_meta last_synced_at
  ├── _sync_fitbit_activities():
  │   ├── Fetch Fitbit activity log (GET /activities/list.json)
  │   ├── For each activity:
  │   │   ├── Map activityTypeId → workout_type category
  │   │   ├── Extract duration, calories, HR zones, distance
  │   │   └── Upsert to workouts (source='fitbit')
  │   └── Update sync_meta last_synced_at (fitbit_activities)
  ├── Release lock
  └── Return sync summary (strava_count, fitbit_count, errors)
```

**Idempotency:**

Repeated calls to `sync()` are safe. Workouts are matched by composite key `(source, activity_id)`; duplicates silently overwrite.

---

## 9. API Clients

### Strava

- Base URL: `https://www.strava.com/api/v3`
- Auth: OAuth2 refresh token flow (POST to `/oauth/token`)
- Key endpoints: `GET /athlete/activities`, `GET /activities/{id}` (for description)
- **Quota tracking**: Thread-safe call counter tracks 15-min (limit: 100) and daily (limit: 1000) windows. Warnings logged at 80% threshold. Current usage exposed via `get_strava_quota()`.

### Fitbit

- Base URL: `https://api.fitbit.com/1`
- Auth: OAuth2 Basic auth refresh token flow
- Key endpoints:
  - `/user/-/sleep/date/{date}.json` — Sleep data
  - `/user/-/hrv/date/{date}.json` — HRV data
  - `/user/-/activities/heart/date/{date}/1d.json` — Resting heart rate
  - `/user/-/activities/list.json?beforeDate={date}&sort=desc&offset=0&limit={n}` — Activity log (Pixel Watch workouts)
- **Requires Personal app type** for HRV access
- **Activity type mapping**: `ACTIVITY_TYPE_MAP` translates `activityTypeId` codes to categories (`strength`, `cardio`, `sport`, `walking`, `running`, `flexibility`, `other`)

---

## 10. Agent Layer (LangGraph Router + Specialists)

### AgentState

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    intent: Optional[IntentType]          # "readiness" | "progress" | "coach" | "general"
    routed_to: Optional[str]              # Human-readable: "Readiness Specialist" | "Progress Analyst" | "Coach"
    tool_iterations: int
    system_context: str
    tool_data: dict
    final_response: Optional[str]
```

### Router

Classifies intent using a two-stage strategy:

1. **Heuristic fast-path** — keyword sets (`_READINESS_HINTS`, `_PROGRESS_HINTS`, `_COACH_HINTS`, `_GENERAL_HINTS`) for deterministic routing
2. **LLM fallback** — zero-shot prompt with `temperature=0` for ambiguous queries

Falls back to `"general"` on any unexpected output. General queries are routed to the Coach agent.

Sets `routed_to` in state (e.g. `"Readiness Specialist"`) for UI visibility. Routing metrics (heuristic hits, LLM fallbacks, total routed) are tracked thread-safely and exposed on the Diagnostics page.

### Readiness Agent

- System prompt: recovery and sleep specialist
- Tools: `get_todays_readiness`, `get_readiness_trend`
- Should only be asked about sleep, HRV, recovery

### Progress Agent

- System prompt: training volume and progression analyst
- Tools: `get_recent_workouts`, `get_weekly_load`, `get_acwr`, `get_exercise_progress`, `get_personal_records`, `get_muscle_group_volume`

### Coach Agent

- System prompt: synthesiser — checks readiness before recommending intensity
- Tools: `get_full_context`, `check_deload_status` (2 tools only — reduced from 9 to avoid small-LLM confusion)
- Includes follow-up question guidance: prompts the LLM to ask for clarification when the query is ambiguous rather than guessing

### `InterceptingToolNode`

A subclass of LangGraph's `ToolNode` that parses tool return values and writes them into `state["tool_data"]`. This is what allows the Output Guardrail to cross-check numbers without requiring agents to manually populate the field.

---

## 11. Configuration Reference

All values in `config.py`. Override by setting in `.env`.

| Variable | Type | Default | Description |
|---|---|---|---|
| `STRAVA_CLIENT_ID` | str | — | Strava OAuth app client ID |
| `STRAVA_CLIENT_SECRET` | str | — | Strava OAuth app secret |
| `STRAVA_REFRESH_TOKEN` | str | — | Strava OAuth refresh token |
| `FITBIT_CLIENT_ID` | str | — | Fitbit developer app ID |
| `FITBIT_CLIENT_SECRET` | str | — | Fitbit developer app secret |
| `FITBIT_ACCESS_TOKEN` | str | — | Fitbit current access token |
| `FITBIT_REFRESH_TOKEN` | str | — | Fitbit refresh token |
| `OLLAMA_BASE_URL` | str | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | str | `qwen3.5:4b` | Model name to use |
| `CACHE_DIR` | str | `data/cache` | diskcache directory |
| `CACHE_TTL_SECS` | int | `3600` | API cache TTL in seconds |
| `DB_PATH` | str | `data/fitness_bridge.db` | SQLite file path |
| `SHORT_TERM_WINDOW` | int | `8` | Recent messages in context |
| `BACKGROUND_SYNC_INTERVAL` | int | `7200` | Background sync interval in seconds |

**Startup validation:** `validate_config()` checks all required credentials at startup and returns a list of warnings for missing values. Warnings are displayed in the Streamlit UI.

---

## 12. Testing Guide

### Running all tests

**Ordered mode (stops on first failure):**
```bash
python run_tests.py
```

**Pytest directly:**
```bash
pytest
```

### Running specific phases

```bash
pytest tests/phase-tests/test_phase00_environment.py   # Environment + packages
pytest tests/phase-tests/test_phase01_foundation.py    # DB + cache
pytest tests/phase-tests/test_phase03_parsers.py       # Hevy parser
pytest tests/phase-tests/test_phase04_analysis.py      # Readiness + ACWR + load
pytest tests/phase-tests/test_phase05_sync_engine.py   # Sync + memory
pytest tests/phase-tests/test_phase06_memory_guardrails.py  # Guardrails
pytest tests/phase-tests/test_phase07_agents.py        # LangGraph agents
pytest tests/phase-tests/test_phase08_ui_*.py -v       # UI page tests
```

### Phase00–08 Test Structure

| Phase | Scope | Pattern | Count |
|---|---|---|---|
| **00** | Environment (packages, .env, paths, file structure) | Assertions on sys checks | 3 tests |
| **01** | Database init, cache lifecycle, file operations | tmp_path + fresh_db fixture | 3 tests |
| **02** | Strava + Fitbit API clients (token refresh, retries) | Manual only* | — |
| **03** | Hevy plaintext parser (set extraction, muscle mapping) | Parameterised inputs | 4 tests |
| **04** | Analysis algorithms (readiness, ACWR, load, progressive overload) | Pure Python assertions | 7 tests |
| **05** | Sync engine upsert, memory (short/long/semantic), guardrails | tmp_path + monkeypatch | 5 tests |
| **06** | Input/output guardrails (safety checks, edge cases) | Mock LLM calls | 3 tests |
| **07** | LangGraph router, agent tools, state binding | Router mock, tool invocation | 5 tests |
| **08** | UI pages (dashboard, coach, history, settings, diagnostics) | Streamlit AppTest, 10s timeout | 14 tests |

*Phase 02 requires live credentials; see `test_phase02_clients_and_tokens.py` comments for manual setup.

### Phase08 UI Testing (AppTest)

**Framework:** Streamlit `AppTest` with 10-second default timeout (accommodates LangGraph graph compilation).

**Test files:**

- `test_phase08_ui_dashboard.py` — Empty state (no workouts), data state (with workouts), chart expanders rendered
- `test_phase08_ui_coach.py` — Page loads, session creation flow, session picker shows correct options
- `test_phase08_ui_history.py` — Empty state, title filtering, pagination offset increments, filter signature reset
- `test_phase08_ui_settings.py` — Page loads, sync button dispatch (mocked), cache clear dispatch (mocked)
- `test_phase08_ui_diagnostics.py` — Metrics display (Total, Heuristic, Fallbacks), reset button dispatch

**Fixtures (conftest.py):**

- `fresh_db(tmp_path, monkeypatch)` — Creates ephemeral SQLite database, patches `config.DB_PATH`, clears diskcache per test
- `workout_factory()` — Returns callable to create seeded workouts with field overrides
- `workout_batch_factory(workout_factory)` — Returns callable to create N workouts spanning multiple dates

**Test isolation:**

All tests run with isolated databases. No test pollution. Each test starts clean.

### Test isolation strategy

Phase 00, 01, 05, 07 use `tmp_path` + `monkeypatch` to create ephemeral SQLite databases per test, ensuring no state leaks.

Phase 04 (algorithms) and Phase 03 (parser) use pure Python with no I/O; no isolation needed.

Phase 02 (API clients) requires live credentials. Manual testing is recommended. There are no automated Phase 02 tests to avoid CI dependency on real API tokens.

### Adding more tests

All test files follow the same pattern:

1. Import `sys`, `pathlib`, and set `BASE_DIR` at top
2. `sys.path.insert(0, str(BASE_DIR))` for relative imports
3. Tests are grouped into classes prefixed `Test`
4. Fixtures live in `conftest.py` for sharing; test-local fixtures in the same file
5. Use `@pytest.mark.skip(reason="...")` for manual tests (Phase 02, credential-dependent)
6. Use `fresh_db` fixture for any database-touching test

### Running with LangSmith Instrumentation

Optional: Enable LangSmith tracing by setting `LANGSMITH_API_KEY` in `.env`.

```bash
export LANGSMITH_API_KEY=<your-key>
pytest tests/phase-tests/test_phase07_agents.py -v
# Traces appear in https://smith.langchain.com
```
