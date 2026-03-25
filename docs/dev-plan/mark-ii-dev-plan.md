# Fitness Bridge AI — Development Plan

**Project:** Fitness Bridge AI  
**Stack:** Python · Streamlit · LangGraph · Ollama (Qwen2.5:4b) · Strava API · Fitbit API  
**Approach:** Multiagent system with guardrails, three-tier memory, analysis-first design

---

## 1. Guiding Principles

Before anything else, these three rules govern every file in this project:

1. **Algorithms own the analysis. The LLM owns the narration.** No business logic inside agent prompts. Every number, score, flag, and trend is computed in pure Python before the LLM ever sees it.
2. **Cache aggressively at the edges.** API calls are the slowest and most fragile part. Diskcache wraps every external call with a TTL. The agent layer never waits on a network call if cached data is available.
3. **Each agent has one job.** Focused system prompt, focused tools, focused context. The Router decides who handles a query; the specialist handles it completely.

---

## 2. Tech Stack Reference

|Concern|Library|Why|
|---|---|---|
|LLM|`ollama` + `langchain-ollama`|Local, free, Qwen2.5:4b fits in RAM|
|Orchestration|`langgraph`|Stateful agent graphs, conditional routing|
|API caching|`diskcache`|Persistent, zero-config, TTL support|
|API retries|`tenacity`|Exponential backoff on flaky calls|
|Data|`pandas`|Session dataset manipulation|
|Validation|`pydantic`|Guardrail output schemas|
|UI|`streamlit`|Rapid, sufficient for personal tool|
|DB|`sqlite3` (stdlib)|Chat history, semantic memory facts|

---

## 3. Directory Architecture

```
fitness-bridge/
│
├── app.py                          # Streamlit entrypoint
├── config.py                       # All constants and env loading
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── data/
│   └── cache/                      # Diskcache writes here (gitignored)
│
├── src/
│   ├── __init__.py
│   │
│   ├── clients/                    # External API layer
│   │   ├── __init__.py
│   │   ├── strava_client.py
│   │   └── fitbit_client.py
│   │
│   ├── parsers/                    # Raw data → structured data
│   │   ├── __init__.py
│   │   └── hevy_parser.py
│   │
│   ├── analysis/                   # Pure Python algorithms (no LLM)
│   │   ├── __init__.py
│   │   ├── readiness.py
│   │   ├── load.py
│   │   └── dataset.py
│   │
│   ├── memory/                     # Three-tier memory system
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   └── store.py
│   │
│   ├── guardrails/                 # Input and output validation
│   │   ├── __init__.py
│   │   ├── input_guard.py
│   │   └── output_guard.py
│   │
│   ├── agents/                     # LangGraph agent definitions
│   │   ├── __init__.py
│   │   ├── state.py                # Shared AgentState TypedDict
│   │   ├── router.py               # Router agent + routing logic
│   │   ├── readiness_agent.py
│   │   ├── progress_agent.py
│   │   ├── coach_agent.py
│   │   └── tools/                  # LangChain tools per agent
│   │       ├── __init__.py
│   │       ├── readiness_tools.py
│   │       ├── progress_tools.py
│   │       └── coach_tools.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── database.py             # SQLite: chat history + semantic facts
│       └── cache.py                # Diskcache singleton wrapper
│
└── ui/
    ├── __init__.py
    ├── dashboard.py                # Dashboard tab rendering
    └── chat.py                     # Chat tab rendering
```

---

## 4. File-by-File Breakdown

Each entry covers: **purpose**, **what it contains theoretically**, and **pseudocode**.

---

### `config.py`

**Purpose:** Single source of truth for all configuration. Every other file imports from here. No file should call `os.getenv()` directly except this one.

**Contains:**

- Environment variable loading via `python-dotenv`
- API credentials (Strava, Fitbit, Ollama endpoint)
- Tuneable constants: cache TTLs, memory window sizes, readiness thresholds
- Paths: cache directory, SQLite file path

**Pseudocode:**

```
load .env file

STRAVA_CLIENT_ID      = env("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET  = env("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN  = env("STRAVA_REFRESH_TOKEN")
FITBIT_ACCESS_TOKEN   = env("FITBIT_ACCESS_TOKEN")
FITBIT_CLIENT_ID      = env("FITBIT_CLIENT_ID")
FITBIT_CLIENT_SECRET  = env("FITBIT_CLIENT_SECRET")
FITBIT_REFRESH_TOKEN  = env("FITBIT_REFRESH_TOKEN")

OLLAMA_BASE_URL  = env("OLLAMA_BASE_URL", default="http://localhost:11434")
OLLAMA_MODEL     = env("OLLAMA_MODEL", default="qwen2.5:4b")

CACHE_DIR        = "data/cache"
CACHE_TTL_SECS   = 3600          # 1 hour
DB_PATH          = "data/fitness_bridge.db"

SHORT_TERM_WINDOW   = 8           # last N messages kept verbatim
READINESS_HIGH      = 420         # minutes (7h sleep)
READINESS_MODERATE  = 300         # minutes (5h sleep)
LOAD_OVERREACH_PCT  = 150         # % of baseline weekly volume
```

---

### `src/utils/cache.py`

**Purpose:** Wraps diskcache into a single shared instance. Every client and tool that needs caching imports the cache object from here rather than creating its own.

**Contains:**

- A `Cache` singleton initialized with `CACHE_DIR` and default TTL
- A `cached()` decorator factory that wraps any function with TTL-aware caching
- A `invalidate(key)` helper for manual cache busting

**Pseudocode:**

```
import diskcache
from config import CACHE_DIR, CACHE_TTL_SECS

_cache = diskcache.Cache(CACHE_DIR)

function cached(ttl=CACHE_TTL_SECS):
    decorator that:
        generates cache key from function name + arguments
        checks _cache for key
        if hit: return cached value
        if miss: call function, store result with ttl, return result

function invalidate(key):
    delete key from _cache if it exists

function get_cache():
    return _cache    # used by clients directly if needed
```

---

### `src/utils/database.py`

**Purpose:** All SQLite operations. Two concerns: chat history (sessions + messages) and semantic memory (persistent facts extracted from conversations).

**Contains:**

- Schema: `sessions`, `messages`, `semantic_facts` tables
- CRUD functions for sessions and messages (carried over, refactored)
- CRUD functions for semantic facts: `upsert_fact()`, `get_all_facts()`, `delete_fact()`

**Pseudocode:**

```
SCHEMA:

  sessions(id TEXT PK, title TEXT, created_at DATETIME)

  messages(
    id        INTEGER PK AUTOINCREMENT,
    session_id TEXT FK → sessions,
    role      TEXT,      -- "user" | "assistant"
    content   TEXT,
    created_at DATETIME
  )

  semantic_facts(
    id       INTEGER PK AUTOINCREMENT,
    key      TEXT UNIQUE,   -- e.g. "user_goal", "shoulder_issue"
    value    TEXT,
    updated_at DATETIME
  )

function init_db():
    connect to DB_PATH
    CREATE TABLE IF NOT EXISTS all three tables
    close

function create_session(title):
    insert new row into sessions with uuid
    return session_id

function get_sessions():
    SELECT all from sessions ORDER BY created_at DESC

function save_message(session_id, role, content):
    INSERT into messages

function get_chat_history(session_id, limit=SHORT_TERM_WINDOW):
    SELECT last `limit` messages for session_id ORDER BY created_at ASC
    return list of {role, content} dicts

function get_full_history(session_id):
    SELECT all messages for session_id (used for summarisation)

function upsert_fact(key, value):
    INSERT OR REPLACE into semantic_facts

function get_all_facts():
    SELECT all from semantic_facts
    return dict of {key: value}

function delete_fact(key):
    DELETE from semantic_facts WHERE key = key
```

---

### `src/clients/strava_client.py`

**Purpose:** All Strava API communication. Handles OAuth token refresh automatically. Returns raw JSON; no parsing logic lives here.

**Contains:**

- Token refresh logic (Strava tokens expire every 6 hours)
- `get_activities(n)` — fetch last N activities
- `get_activity_detail(activity_id)` — full detail including description
- Connection check method
- All methods wrapped with `@cached()` and `@retry()`

**Pseudocode:**

```
class StravaClient:

    __init__():
        self.base_url = "https://www.strava.com/api/v3"
        self.access_token = None
        self._refresh_access_token()

    _refresh_access_token():
        POST to "https://www.strava.com/oauth/token" with:
            client_id, client_secret, refresh_token, grant_type="refresh_token"
        if success:
            self.access_token = response["access_token"]
            store new refresh_token back to .env or config
        else:
            raise AuthError("Strava token refresh failed")

    _headers():
        return {"Authorization": f"Bearer {self.access_token}"}

    @cached(ttl=3600)
    @retry(wait_exponential, stop_after_attempt=3)
    get_activities(per_page=10, page=1):
        GET /athlete/activities?per_page=per_page&page=page
        return response.json()

    @cached(ttl=3600)
    @retry(wait_exponential, stop_after_attempt=3)
    get_activity_detail(activity_id):
        GET /activities/{activity_id}
        return response.json()   -- includes "description" field

    check_connection():
        GET /athlete
        return status_code == 200
```

---

### `src/clients/fitbit_client.py`

**Purpose:** All Fitbit API communication. Handles OAuth token refresh. Fetches sleep, HRV, and heart rate data.

**Contains:**

- Token refresh (Fitbit tokens expire every 8 hours)
- `get_sleep(date_str)` — full sleep summary including stages
- `get_hrv(date_str)` — HRV daily summary (available on Personal app type)
- `get_resting_hr(date_str)` — resting heart rate
- Connection check
- All methods wrapped with `@cached()` and `@retry()`

**Pseudocode:**

```
class FitbitClient:

    __init__():
        self.base_url = "https://api.fitbit.com/1"
        self.access_token = FITBIT_ACCESS_TOKEN
        -- attempt a connection check; if 401, refresh token

    _refresh_access_token():
        POST to "https://api.fitbit.com/oauth2/token" with:
            grant_type="refresh_token", refresh_token=FITBIT_REFRESH_TOKEN
            Authorization: Basic base64(client_id:client_secret)
        if success:
            self.access_token = response["access_token"]
        else:
            raise AuthError("Fitbit token refresh failed")

    _headers():
        return {"Authorization": f"Bearer {self.access_token}"}

    @cached(ttl=3600)
    @retry(wait_exponential, stop_after_attempt=3)
    get_sleep(date_str):           -- "YYYY-MM-DD"
        GET /user/-/sleep/date/{date_str}.json
        return response.json()

    @cached(ttl=3600)
    @retry(wait_exponential, stop_after_attempt=3)
    get_hrv(date_str):
        GET /user/-/hrv/date/{date_str}.json
        return response.json()

    @cached(ttl=3600)
    @retry(wait_exponential, stop_after_attempt=3)
    get_resting_hr(date_str):
        GET /user/-/activities/heart/date/{date_str}/1d.json
        extract restingHeartRate from response
        return int or None

    check_connection():
        GET /user/-/profile.json
        return status_code == 200
```

---

### `src/parsers/hevy_parser.py`

**Purpose:** Converts a raw Strava activity description (which is Hevy's plain-text workout dump) into structured exercise data. This is pure string parsing — no API calls, no LLM.

**Contains:**

- `parse_description(text)` — main entry point, returns a list of exercise dicts
- `parse_set_line(line)` — parses a single "Set N: X kg x Y [Tag]" line
- `classify_set_type(line)` — detects duration, weighted, bodyweight, or tagged sets
- `calculate_exercise_volume(exercise_dict)` — total volume for one exercise
- `tag_muscle_group(exercise_name)` — maps exercise name to muscle group

**Pseudocode:**

```
MUSCLE_MAP = {
    "push up": "chest", "bench press": "chest", "incline bench": "chest",
    "pull up": "back",  "lat pulldown": "back", "row": "back",
    "squat": "legs",    "deadlift": "legs",     "leg press": "legs",
    "bicep curl": "biceps", "triceps extension": "triceps",
    "shoulder press": "shoulders", "lateral raise": "shoulders",
    "stretching": "mobility",
    ... (expand as needed)
}

function parse_description(text):
    if text is empty or None: return []

    split text by double newline → exercise_blocks
    exercises = []

    for block in exercise_blocks:
        lines = block.strip().split("\n")
        if len(lines) == 0: continue

        exercise_name = lines[0].strip()
        sets = []

        for line in lines[1:]:
            if line starts with "Set":
                parsed_set = parse_set_line(line)
                if parsed_set: sets.append(parsed_set)

        muscle_group = tag_muscle_group(exercise_name)
        volume = calculate_exercise_volume(sets)

        exercises.append({
            "name": exercise_name,
            "muscle_group": muscle_group,
            "sets": sets,
            "total_volume_kg": volume,
            "set_count": len(sets)
        })

    return exercises


function parse_set_line(line):
    -- Example inputs:
    -- "Set 1: 25 kg x 12"
    -- "Set 2: 15 kg x 5 [Drop]"
    -- "Set 3: 10 reps"
    -- "Set 1: 7min 55s"

    extract set_number from "Set N:"
    remainder = everything after the colon, stripped

    if "min" in remainder or "s" in remainder:
        return {type: "duration", set_number: N, duration_str: remainder}

    elif "kg x" in remainder:
        extract weight and reps using split
        tag = extract [Tag] if present, else None
        return {
            type: "weighted",
            set_number: N,
            weight_kg: float,
            reps: int,
            tag: tag    -- "Drop", "Failure", or None
        }

    elif "reps" in remainder:
        extract reps
        return {type: "bodyweight", set_number: N, reps: int}

    return None


function calculate_exercise_volume(sets):
    total = 0
    for s in sets:
        if s.type == "weighted":
            total += s.weight_kg * s.reps
    return round(total, 2)


function tag_muscle_group(name):
    name_lower = name.lower()
    for keyword, group in MUSCLE_MAP.items():
        if keyword in name_lower:
            return group
    return "other"
```

---

### `src/analysis/readiness.py`

**Purpose:** Computes a readiness score and status from Fitbit data. Pure Python, no LLM dependency. Returns a structured dict the agent tools can pass directly to the LLM.

**Contains:**

- `compute_readiness(sleep_data, hrv_data, resting_hr)` — main function
- `score_sleep(sleep_data)` — returns 0–40 points
- `score_hrv(hrv_data)` — returns 0–40 points
- `score_resting_hr(resting_hr, baseline_hr)` — returns 0–20 points
- `get_readiness_label(score)` — maps score to human label

**Pseudocode:**

```
function compute_readiness(sleep_data, hrv_data, resting_hr):
    sleep_score = score_sleep(sleep_data)
    hrv_score   = score_hrv(hrv_data)
    hr_score    = score_resting_hr(resting_hr, baseline_hr=get_baseline_hr())

    total = sleep_score + hrv_score + hr_score   -- max 100

    return {
        "score": total,
        "label": get_readiness_label(total),
        "sleep_minutes": extracted from sleep_data,
        "sleep_hours": rounded,
        "sleep_efficiency": from sleep_data summary,
        "hrv_ms": from hrv_data,
        "resting_hr": resting_hr,
        "components": {
            "sleep": sleep_score,
            "hrv": hrv_score,
            "resting_hr": hr_score
        },
        "recommendation": derive_recommendation(total)
    }


function score_sleep(sleep_data):
    total_minutes = sleep_data.summary.totalMinutesAsleep
    efficiency    = sleep_data.summary.efficiency  -- 0-100

    if total_minutes >= 480: time_score = 40
    elif total_minutes >= 420: time_score = 35
    elif total_minutes >= 360: time_score = 25
    elif total_minutes >= 300: time_score = 15
    else: time_score = 5

    efficiency_bonus = (efficiency / 100) * 10
    return min(40, time_score + efficiency_bonus)


function score_hrv(hrv_data):
    -- HRV scoring relative to personal baseline (stored in semantic facts)
    hrv_value = extract daily HRV from hrv_data
    baseline  = get_hrv_baseline()   -- from semantic facts or rolling 30-day avg

    if hrv_value is None: return 20  -- neutral if no data

    ratio = hrv_value / baseline
    if ratio >= 1.10: return 40      -- elevated above baseline
    elif ratio >= 0.95: return 35    -- within normal range
    elif ratio >= 0.80: return 20    -- mildly suppressed
    elif ratio >= 0.65: return 10    -- notably suppressed
    else: return 0                   -- severely suppressed


function score_resting_hr(resting_hr, baseline_hr):
    if resting_hr is None: return 10  -- neutral

    delta = resting_hr - baseline_hr
    if delta <= -2: return 20         -- below baseline: well recovered
    elif delta <= 2: return 17        -- at baseline: normal
    elif delta <= 5: return 10        -- mildly elevated
    elif delta <= 8: return 5         -- notably elevated
    else: return 0                    -- significantly elevated


function get_readiness_label(score):
    if score >= 75: return "High readiness — train hard"
    elif score >= 50: return "Moderate readiness — train normally"
    elif score >= 30: return "Low readiness — consider deload"
    else: return "Poor readiness — rest or active recovery only"


function derive_recommendation(score):
    if score >= 75: return "Good day for a heavy session or a PR attempt."
    elif score >= 50: return "Normal training. Avoid maximal efforts."
    elif score >= 30: return "Reduce intensity by 20-30%. Prioritize form."
    else: return "Full rest or light mobility work only."
```

---

### `src/analysis/load.py`

**Purpose:** Tracks training load over time. Computes acute (7-day) vs chronic (28-day) load ratio, weekly volume, and detects overreaching signals. All math, no LLM.

**Contains:**

- `compute_weekly_load(sessions_df)` — volume for current week
- `compute_acwr(sessions_df)` — Acute:Chronic Workload Ratio
- `detect_overreach(sessions_df)` — flags if load is spiking dangerously
- `progressive_overload_check(sessions_df, exercise_name)` — are you getting stronger?

**Pseudocode:**

```
function compute_weekly_load(sessions_df):
    -- sessions_df has columns: date, total_volume_kg, duration_min
    this_week = filter rows where date >= 7 days ago
    return {
        "total_volume_kg": sum(this_week.total_volume_kg),
        "total_duration_min": sum(this_week.duration_min),
        "session_count": len(this_week),
        "avg_volume_per_session": mean
    }


function compute_acwr(sessions_df):
    -- ACWR = Acute Load (7d) / Chronic Load (28d)
    -- ACWR between 0.8 and 1.3 is the "sweet spot"

    today = current date
    acute_load   = sum of volume for last 7 days
    chronic_load = sum of volume for last 28 days / 4  -- weekly average

    if chronic_load == 0: return None   -- not enough history

    ratio = acute_load / chronic_load
    return {
        "acute_load": acute_load,
        "chronic_load": chronic_load,
        "ratio": round(ratio, 2),
        "zone": classify_acwr_zone(ratio)
    }


function classify_acwr_zone(ratio):
    if ratio < 0.8:  return "undertrained"
    elif ratio <= 1.3: return "optimal"
    elif ratio <= 1.5: return "caution"
    else: return "overreach_risk"


function detect_overreach(sessions_df):
    acwr = compute_acwr(sessions_df)
    if acwr is None: return False, "Insufficient history"

    if acwr.ratio > 1.5:
        return True, f"ACWR is {acwr.ratio} — training load spiked significantly this week"
    return False, "Load looks manageable"


function progressive_overload_check(sessions_df, exercise_name):
    -- filter all sessions containing exercise_name
    -- sort by date, take last 6 appearances
    -- check if average weight and/or reps has increased

    appearances = filter and explode exercises from sessions
    last_6 = last 6 rows matching exercise_name

    if len(last_6) < 2: return "Insufficient history for this exercise"

    first_avg_volume = mean(last_6[:3].volume_per_set)
    last_avg_volume  = mean(last_6[-3:].volume_per_set)

    pct_change = (last_avg_volume - first_avg_volume) / first_avg_volume * 100

    if pct_change >= 5: trend = "progressing"
    elif pct_change >= -5: trend = "maintaining"
    else: trend = "regressing"

    return {
        "exercise": exercise_name,
        "trend": trend,
        "pct_change": round(pct_change, 1),
        "recent_avg_volume": last_avg_volume
    }
```

---

### `src/analysis/dataset.py`

**Purpose:** Joins Strava + Fitbit data into a single per-day session record. This is the master dataset that all agents query. Think of it as a personal fitness database built fresh from the APIs.

**Contains:**

- `build_session_record(strava_activity, fitbit_day)` — builds one row
- `build_dataset(n_days)` — builds the full DataFrame for the last N days
- `get_session_for_date(date_str)` — returns a single day's record

**Pseudocode:**

```
function build_dataset(n_days=30):
    strava_client = StravaClient()
    fitbit_client = FitbitClient()

    activities = strava_client.get_activities(per_page=n_days)
    dataset = []

    for activity in activities:
        date_str = extract date from activity.start_date

        -- fetch Fitbit data for the same day
        sleep_data  = fitbit_client.get_sleep(date_str)
        hrv_data    = fitbit_client.get_hrv(date_str)
        resting_hr  = fitbit_client.get_resting_hr(date_str)

        -- get full activity with description
        detail = strava_client.get_activity_detail(activity.id)

        -- parse the Hevy description
        exercises = hevy_parser.parse_description(detail.description)

        -- compute readiness for that day
        readiness = compute_readiness(sleep_data, hrv_data, resting_hr)

        row = build_session_record(detail, exercises, readiness)
        dataset.append(row)

    return pandas.DataFrame(dataset)


function build_session_record(activity, exercises, readiness):
    return {
        "date":              activity.start_date_local[:10],
        "activity_id":       activity.id,
        "workout_title":     activity.name,
        "duration_min":      activity.elapsed_time / 60,
        "total_volume_kg":   sum(e.total_volume_kg for e in exercises),
        "exercise_count":    len(exercises),
        "set_count":         sum(e.set_count for e in exercises),
        "exercises_raw":     json.dumps(exercises),   -- full parsed detail
        "muscle_groups":     unique list of muscle groups hit,
        "has_drop_sets":     any set with tag=="Drop",
        "has_failure_sets":  any set with tag=="Failure",
        "sleep_hours":       readiness.sleep_hours,
        "sleep_efficiency":  readiness.sleep_efficiency,
        "hrv_ms":            readiness.hrv_ms,
        "resting_hr":        readiness.resting_hr,
        "readiness_score":   readiness.score,
        "readiness_label":   readiness.label
    }


function get_session_for_date(date_str):
    df = build_dataset(n_days=60)
    matches = df[df.date == date_str]
    if matches.empty: return None
    return matches.iloc[0].to_dict()
```

---

### `src/memory/store.py`

**Purpose:** Low-level memory operations. Separates the three memory types: short-term (raw messages), long-term (compressed summaries), and semantic (persistent facts).

**Contains:**

- `ShortTermStore` — wraps `get_chat_history()` with the window limit
- `LongTermStore` — stores/retrieves the running conversation summary
- `SemanticStore` — wraps the `semantic_facts` SQLite table

**Pseudocode:**

```
class ShortTermStore:
    get(session_id):
        return database.get_chat_history(session_id, limit=SHORT_TERM_WINDOW)
        -- returns last N messages verbatim as {role, content} dicts

    save(session_id, role, content):
        database.save_message(session_id, role, content)


class LongTermStore:
    -- stored as a special row in messages with role="summary"

    get(session_id):
        query messages for session_id WHERE role == "summary"
        return most recent summary content, or None if none exists

    save(session_id, summary_text):
        upsert a row with role="summary", content=summary_text


class SemanticStore:
    get_all():
        return database.get_all_facts()
        -- e.g. {"user_goal": "hypertrophy", "shoulder_issue": "left shoulder pain"}

    upsert(key, value):
        database.upsert_fact(key, value)

    delete(key):
        database.delete_fact(key)

    format_for_context():
        facts = self.get_all()
        if not facts: return ""
        lines = [f"- {k}: {v}" for k, v in facts.items()]
        return "Known facts about the user:\n" + "\n".join(lines)
```

---

### `src/memory/manager.py`

**Purpose:** Orchestrates all three memory tiers. The agent layer only talks to this — it never touches stores directly. Also responsible for triggering summary generation when history is too long.

**Contains:**

- `MemoryManager` class
- `build_context(session_id)` — assembles the full memory context string
- `save_turn(session_id, user_msg, assistant_msg)` — saves both sides of a turn
- `maybe_summarise(session_id, llm)` — generates a new summary if history is long
- `extract_and_store_facts(assistant_response, llm)` — pulls semantic facts from response

**Pseudocode:**

```
class MemoryManager:

    __init__():
        self.short_term = ShortTermStore()
        self.long_term  = LongTermStore()
        self.semantic   = SemanticStore()

    build_context(session_id):
        -- Assemble everything the agent needs before its first LLM call

        parts = []

        semantic_context = self.semantic.format_for_context()
        if semantic_context:
            parts.append(semantic_context)

        summary = self.long_term.get(session_id)
        if summary:
            parts.append(f"Conversation summary so far:\n{summary}")

        recent = self.short_term.get(session_id)
        -- return parts as system context string + recent as message history

        return {
            "system_context": "\n\n".join(parts),
            "recent_messages": recent
        }

    save_turn(session_id, user_msg, assistant_msg):
        self.short_term.save(session_id, "user", user_msg)
        self.short_term.save(session_id, "assistant", assistant_msg)

    maybe_summarise(session_id, llm):
        full_history = database.get_full_history(session_id)

        if len(full_history) < 20: return   -- not worth summarising yet

        existing_summary = self.long_term.get(session_id)

        prompt = f"""
        You are summarising a fitness coaching conversation.
        Existing summary: {existing_summary or 'None'}
        New messages: {format last 10 messages}
        Write a concise updated summary capturing key insights, goals, and patterns discussed.
        """

        new_summary = llm.invoke(prompt)
        self.long_term.save(session_id, new_summary)

    extract_and_store_facts(assistant_response, llm):
        -- Look for extractable facts in the response
        -- Run a lightweight extraction prompt

        prompt = f"""
        Given this fitness coaching response:
        {assistant_response}

        Extract any persistent facts about the user (injuries, goals, preferences, baselines).
        Return as JSON: {{"key": "value"}} or empty {{}} if none.
        """

        result = llm.invoke(prompt)
        facts = parse JSON from result

        for key, value in facts.items():
            self.semantic.upsert(key, value)
```

---

### `src/guardrails/input_guard.py`

**Purpose:** Filters user queries before the agent pipeline fires. Cheap and fast — uses a simple keyword/heuristic check first, falls back to a lightweight LLM classification only for ambiguous cases.

**Contains:**

- `InputGuardrail` class
- `check(query)` — returns `(is_allowed: bool, reason: str)`
- `quick_filter(query)` — keyword-based fast path
- `llm_classify(query, llm)` — LLM fallback for ambiguous queries

**Pseudocode:**

```
ALLOWED_KEYWORDS = [
    "workout", "training", "exercise", "sleep", "recovery", "fatigue",
    "readiness", "progress", "volume", "reps", "sets", "weight",
    "hrv", "heart rate", "muscle", "strength", "cardio", "nutrition",
    "session", "routine", "week", "month", "yesterday", "today",
    "strava", "fitbit", "hevy"
]

BLOCKED_PATTERNS = [
    "how to hack", "ignore previous", "jailbreak", "pretend you are"
]

class InputGuardrail:

    check(query, llm=None):

        -- Step 1: block injection attempts immediately
        for pattern in BLOCKED_PATTERNS:
            if pattern in query.lower():
                return False, "Blocked: policy violation"

        -- Step 2: fast keyword pass
        result = self.quick_filter(query)
        if result is not None:
            return result

        -- Step 3: LLM fallback only if needed
        if llm:
            return self.llm_classify(query, llm)

        -- Default allow if no LLM available and no clear block signal
        return True, "Allowed"

    quick_filter(query):
        lower = query.lower()

        for keyword in ALLOWED_KEYWORDS:
            if keyword in lower:
                return True, "Allowed"

        -- Very short queries are likely greetings or clarifications
        if len(query.split()) <= 4:
            return True, "Allowed (short query)"

        return None   -- ambiguous, needs LLM classification

    llm_classify(query, llm):
        prompt = f"""
        You are a classifier for a personal fitness coaching app.
        The app only handles: workout analysis, recovery, sleep, training load, progress.

        Query: "{query}"

        Is this query related to fitness, health, training, or recovery?
        Reply with only: ALLOWED or BLOCKED
        """
        result = llm.invoke(prompt).strip().upper()
        if "ALLOWED" in result:
            return True, "Allowed"
        return False, "Not related to fitness"
```

---

### `src/guardrails/output_guard.py`

**Purpose:** Validates agent responses before they reach the user. Checks for hallucinated numbers against the actual data that was fetched. Uses Pydantic for structural validation of tool outputs.

**Contains:**

- `OutputGuardrail` class
- `validate_response(response_text, tool_data)` — main check
- `check_numbers(response_text, tool_data)` — extracts and cross-checks numbers
- Pydantic schemas for structured tool outputs

**Pseudocode:**

```
from pydantic import BaseModel

class ReadinessOutput(BaseModel):
    score: int                  -- 0-100
    label: str
    sleep_hours: float
    recommendation: str

class ProgressOutput(BaseModel):
    period_days: int
    total_volume_kg: float
    session_count: int
    trend: str


class OutputGuardrail:

    validate_response(response_text, tool_data):
        -- tool_data is the raw dict returned by the analysis functions
        -- Check that numbers mentioned in response_text appear in tool_data

        issues = self.check_numbers(response_text, tool_data)

        if issues:
            return False, f"Potential data mismatch: {issues}"
        return True, "OK"

    check_numbers(response_text, tool_data):
        -- Extract all numbers from response_text using regex
        -- Extract all numbers from tool_data (flatten)
        -- Flag any response number not within 5% of any tool_data number

        response_numbers = extract floats and ints from response_text
        data_numbers     = flatten all numeric values from tool_data dict

        issues = []
        for num in response_numbers:
            if num not within 5% of any value in data_numbers:
                -- Only flag if the number looks significant (> 1.0)
                if num > 1.0:
                    issues.append(f"{num} not found in source data")

        return issues
```

---

### `src/agents/state.py`

**Purpose:** Defines the shared `AgentState` TypedDict used across all LangGraph graphs. Single file so all agents import from one place.

**Contains:**

- `AgentState` TypedDict
- `IntentType` Literal for routing

**Pseudocode:**

```
from typing import TypedDict, Annotated, List, Literal, Optional
from langchain_core.messages import BaseMessage

IntentType = Literal["readiness", "progress", "coach", "general"]

class AgentState(TypedDict):
    messages:        List[BaseMessage]     -- full message history for this turn
    session_id:      str                   -- links to SQLite session
    intent:          Optional[IntentType]  -- set by router, consumed by specialists
    system_context:  str                   -- memory context injected before first call
    tool_data:       dict                  -- raw analysis outputs (for guardrail)
    final_response:  Optional[str]         -- set by specialist, read by output guard
```

---

### `src/agents/router.py`

**Purpose:** The first agent in every request. Reads the user query, classifies intent, and returns the routing decision. Does not generate a user-visible response.

**Contains:**

- LLM initialisation (shared Ollama/Qwen2.5 instance)
- `router_node(state)` — LangGraph node function
- `route_to_agent(state)` — conditional edge function
- `build_graph()` — compiles the outer LangGraph that wraps all agents

**Pseudocode:**

```
llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

ROUTER_PROMPT = """
You are a routing classifier for a fitness coaching app.
Classify the user's intent into exactly one category:

- readiness: questions about today's recovery, sleep quality, whether to train
- progress: questions about past workouts, volume trends, exercise history
- coach: requests for coaching advice, what to change, how to improve
- general: greetings, clarifications, anything else

User query: {query}

Respond with only the category name. Nothing else.
"""

function router_node(state: AgentState):
    query = state["messages"][-1].content
    intent_str = llm.invoke(ROUTER_PROMPT.format(query=query)).content.strip().lower()

    -- validate the response is one of the four options
    if intent_str not in ["readiness", "progress", "coach", "general"]:
        intent_str = "general"

    return {"intent": intent_str}


function route_to_agent(state: AgentState):
    intent = state.get("intent", "general")
    mapping = {
        "readiness": "readiness_agent",
        "progress":  "progress_agent",
        "coach":     "coach_agent",
        "general":   "coach_agent"   -- coach handles fallback
    }
    return mapping[intent]


function build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router",           router_node)
    graph.add_node("readiness_agent",  readiness_agent_node)
    graph.add_node("progress_agent",   progress_agent_node)
    graph.add_node("coach_agent",      coach_agent_node)
    graph.add_node("tools",            ToolNode(all_tools))

    graph.set_entry_point("router")
    graph.add_conditional_edges("router", route_to_agent, {
        "readiness_agent": "readiness_agent",
        "progress_agent":  "progress_agent",
        "coach_agent":     "coach_agent"
    })

    -- Each specialist loops through tools and back to itself
    for agent in ["readiness_agent", "progress_agent", "coach_agent"]:
        graph.add_conditional_edges(agent, route_tools, {
            "tools": "tools",
            END: END
        })
        graph.add_edge("tools", agent)

    return graph.compile()
```

---

### `src/agents/readiness_agent.py`

**Purpose:** Specialist for all recovery and readiness queries. Only has access to Fitbit-facing tools and the readiness algorithm. Focused system prompt.

**Contains:**

- `READINESS_SYSTEM_PROMPT` — focused on recovery, sleep, HRV
- `readiness_agent_node(state)` — LangGraph node
- Imports `readiness_tools` from tools layer

**Pseudocode:**

```
READINESS_SYSTEM_PROMPT = """
You are a recovery specialist coach. You analyse biological data to assess
how ready the athlete is to train.

You have access to:
- Today's readiness score (computed from sleep, HRV, resting heart rate)
- Historical readiness trends

Your job:
1. Fetch the readiness data using your tools.
2. State the readiness score and label clearly.
3. Explain the main driver (was it sleep? HRV? heart rate?).
4. Give one clear recommendation for today.

Be concise. One paragraph. No bullet points unless listing multiple issues.
Never invent numbers not in the tool output.
"""

function readiness_agent_node(state: AgentState):
    messages = state["messages"]
    system_context = state.get("system_context", "")

    -- Prepend system prompt + memory context
    system_msg = SystemMessage(content=READINESS_SYSTEM_PROMPT + "\n\n" + system_context)
    full_messages = [system_msg] + messages

    -- LLM with tools bound
    llm_with_tools = llm.bind_tools(readiness_tools)
    response = llm_with_tools.invoke(full_messages)

    return {
        "messages": [response],
        "tool_data": state.get("tool_data", {})
    }
```

---

### `src/agents/progress_agent.py`

**Purpose:** Specialist for workout history, volume trends, and exercise progress queries. Only has access to Strava-facing tools and the load/progress algorithms.

**Contains:**

- `PROGRESS_SYSTEM_PROMPT`
- `progress_agent_node(state)`
- Imports `progress_tools`

**Pseudocode:**

```
PROGRESS_SYSTEM_PROMPT = """
You are a training progress analyst. You review workout history and load data.

You have access to:
- Recent workout sessions from Strava (parsed from Hevy)
- Weekly load and ACWR calculations
- Per-exercise progressive overload trends

Your job:
1. Fetch the relevant workout data using your tools.
2. Identify the key pattern in the data (trend, stagnation, spike).
3. State volume numbers accurately — never approximate.
4. Highlight one thing going well and one thing to watch.

Be specific. Reference actual exercises and actual numbers.
Never invent sets, reps, or weights not in the tool output.
"""

function progress_agent_node(state: AgentState):
    -- same pattern as readiness_agent_node
    -- bind progress_tools to llm
    -- prepend system prompt + memory context
    -- invoke and return
```

---

### `src/agents/coach_agent.py`

**Purpose:** The synthesiser. Has access to both readiness and progress tools. Answers "what should I do?" questions by pulling both data streams and forming a recommendation. Also handles general queries.

**Contains:**

- `COACH_SYSTEM_PROMPT`
- `coach_agent_node(state)`
- Imports both `readiness_tools` and `progress_tools`

**Pseudocode:**

```
COACH_SYSTEM_PROMPT = """
You are an elite strength and conditioning coach with access to complete
biometric and training data.

You have access to:
- Today's readiness (sleep, HRV, resting HR)
- Recent training load and ACWR
- Exercise history and progressive overload data
- Known facts about the athlete

Your job:
1. Check readiness FIRST before any intensity recommendation.
2. Cross-reference load data with recovery state.
3. Give a specific, data-driven coaching recommendation.
4. Explain WHY — reference the actual numbers that drove the recommendation.

Example reasoning: "Your ACWR is 1.6 and your readiness score is 28 —
this is a clear signal to cut volume this week, not increase it."

Be direct. Be specific. Do not hedge or give generic advice.
"""

function coach_agent_node(state: AgentState):
    -- same pattern as other agents
    -- bind readiness_tools + progress_tools to llm
    -- prepend system prompt + memory context
    -- invoke and return
```

---

### `src/agents/tools/readiness_tools.py`

**Purpose:** LangChain tools available to the Readiness and Coach agents. These are thin wrappers around the analysis layer — they call the algorithms, not re-implement them.

**Contains:**

- `get_todays_readiness` tool
- `get_readiness_trend` tool (last 7 days)

**Pseudocode:**

```
@tool
def get_todays_readiness():
    """
    Fetches today's readiness score computed from Fitbit sleep,
    HRV, and resting heart rate data. Returns score 0-100,
    label, component breakdown, and a recommendation.
    """
    today = date.today().isoformat()
    fitbit = FitbitClient()

    sleep_data = fitbit.get_sleep(today)
    hrv_data   = fitbit.get_hrv(today)
    resting_hr = fitbit.get_resting_hr(today)

    result = compute_readiness(sleep_data, hrv_data, resting_hr)
    return json.dumps(result)


@tool
def get_readiness_trend(days: int = 7):
    """
    Returns readiness scores for the last N days.
    Useful for identifying a recovery pattern over time.
    """
    fitbit = FitbitClient()
    trend = []

    for i in range(days):
        date_str = (date.today() - timedelta(days=i)).isoformat()
        sleep    = fitbit.get_sleep(date_str)
        hrv      = fitbit.get_hrv(date_str)
        rhr      = fitbit.get_resting_hr(date_str)
        readiness = compute_readiness(sleep, hrv, rhr)
        trend.append({"date": date_str, "score": readiness["score"], "label": readiness["label"]})

    return json.dumps(list(reversed(trend)))
```

---

### `src/agents/tools/progress_tools.py`

**Purpose:** LangChain tools available to the Progress and Coach agents. Wrap the load and dataset analysis functions.

**Contains:**

- `get_recent_workouts` tool
- `get_weekly_load` tool
- `get_acwr` tool
- `get_exercise_progress` tool

**Pseudocode:**

```
@tool
def get_recent_workouts(limit: int = 5):
    """
    Returns the last N workout sessions with parsed exercise details,
    volume, set count, and readiness on that day.
    """
    df = build_dataset(n_days=30)
    recent = df.head(limit)
    return recent.to_json(orient="records")


@tool
def get_weekly_load():
    """
    Returns this week's total training volume, session count,
    and comparison to the previous week.
    """
    df = build_dataset(n_days=28)
    current = compute_weekly_load(df)
    return json.dumps(current)


@tool
def get_acwr():
    """
    Returns the Acute:Chronic Workload Ratio.
    Values between 0.8 and 1.3 are optimal.
    Above 1.5 is overreach risk.
    """
    df = build_dataset(n_days=35)
    result = compute_acwr(df)
    return json.dumps(result)


@tool
def get_exercise_progress(exercise_name: str):
    """
    Returns progressive overload trend for a specific exercise
    over the last 6 sessions it appeared in.
    """
    df = build_dataset(n_days=60)
    result = progressive_overload_check(df, exercise_name)
    return json.dumps(result)
```

---

### `src/agents/tools/coach_tools.py`

**Purpose:** Composite tools only used by the Coach agent. Combines both data streams into a single richer context object, reducing the number of tool calls the Coach needs to make.

**Contains:**

- `get_full_context` tool — readiness + load in one call

**Pseudocode:**

```
@tool
def get_full_context():
    """
    Returns a combined view of today's readiness and this week's
    training load. Use this for holistic coaching recommendations.
    """
    today    = date.today().isoformat()
    fitbit   = FitbitClient()
    df       = build_dataset(n_days=35)

    readiness = compute_readiness(
        fitbit.get_sleep(today),
        fitbit.get_hrv(today),
        fitbit.get_resting_hr(today)
    )
    weekly  = compute_weekly_load(df)
    acwr    = compute_acwr(df)
    overreach, overreach_msg = detect_overreach(df)

    return json.dumps({
        "readiness": readiness,
        "weekly_load": weekly,
        "acwr": acwr,
        "overreach_flag": overreach,
        "overreach_message": overreach_msg
    })
```

---

### `ui/dashboard.py`

**Purpose:** Renders the Dashboard tab in Streamlit. Pulls from the session dataset and displays charts. No LLM involved here — pure data visualisation.

**Contains:**

- `render_dashboard()` — called from `app.py`
- Readiness trend chart (last 7 days)
- Weekly volume bar chart (last 4 weeks)
- ACWR gauge/indicator
- Most recent workout summary card

**Pseudocode:**

```
function render_dashboard():
    st.header("Your Training Overview")

    df = build_dataset(n_days=28)

    if df.empty:
        st.info("No workout data found. Connect your Strava account.")
        return

    -- Row 1: Key metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        today_readiness = get_todays_readiness()
        st.metric("Today's Readiness", today_readiness.score, today_readiness.label)
    with col2:
        weekly = compute_weekly_load(df)
        st.metric("This Week's Volume", f"{weekly.total_volume_kg:,.0f} kg")
    with col3:
        acwr = compute_acwr(df)
        if acwr:
            st.metric("ACWR", acwr.ratio, acwr.zone)

    st.divider()

    -- Row 2: Charts
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Readiness — last 7 days")
        readiness_df = df[["date", "readiness_score"]].tail(7)
        st.line_chart(readiness_df.set_index("date"))

    with col_right:
        st.subheader("Weekly volume")
        weekly_df = aggregate df by ISO week, sum total_volume_kg
        st.bar_chart(weekly_df)

    st.divider()

    -- Row 3: Last workout detail
    st.subheader("Last workout")
    last = df.iloc[0]
    st.write(f"**{last.workout_title}** — {last.date}")
    st.write(f"{last.exercise_count} exercises · {last.set_count} sets · {last.total_volume_kg:,.0f} kg total")

    exercises = json.loads(last.exercises_raw)
    for ex in exercises:
        with st.expander(ex["name"]):
            for s in ex["sets"]:
                st.write(format_set(s))
```

---

### `ui/chat.py`

**Purpose:** Renders the Chat tab. Handles input, runs the guardrail check, invokes the agent graph, and displays the response.

**Contains:**

- `render_chat(session_id)` — called from `app.py`
- `run_agent(query, session_id)` — runs full pipeline: guard → memory → graph → guard → save
- Message display loop

**Pseudocode:**

```
function render_chat(session_id):
    history = memory_manager.short_term.get(session_id)

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your training..."):
        -- Display user message immediately
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.text("Thinking...")

            response = run_agent(prompt, session_id)
            placeholder.markdown(response)


function run_agent(query, session_id):

    -- Step 1: Input guardrail
    allowed, reason = input_guardrail.check(query, llm=llm)
    if not allowed:
        return f"I can only help with fitness and training questions. ({reason})"

    -- Step 2: Build memory context
    context = memory_manager.build_context(session_id)

    -- Step 3: Build initial state
    lc_messages = convert context.recent_messages to LangChain message objects
    lc_messages.append(HumanMessage(content=query))

    initial_state = AgentState(
        messages=lc_messages,
        session_id=session_id,
        intent=None,
        system_context=context.system_context,
        tool_data={},
        final_response=None
    )

    -- Step 4: Run agent graph
    result = compiled_graph.invoke(initial_state)
    response_text = result["messages"][-1].content

    -- Step 5: Output guardrail
    valid, issue = output_guardrail.validate_response(response_text, result.get("tool_data", {}))
    if not valid:
        -- Log the issue but still return response (flag, don't block)
        print(f"[GUARDRAIL WARNING] {issue}")

    -- Step 6: Save turn + extract facts
    memory_manager.save_turn(session_id, query, response_text)
    memory_manager.maybe_summarise(session_id, llm)
    memory_manager.extract_and_store_facts(response_text, llm)

    return response_text
```

---

### `app.py`

**Purpose:** The Streamlit entrypoint. Sets up the page, sidebar, session state, and routes between tabs. Minimal logic — delegates to `ui/dashboard.py` and `ui/chat.py`.

**Pseudocode:**

```
load_dotenv()
init_db()

st.set_page_config(title="Fitness Bridge AI", layout="wide")

-- Sidebar: connections + session management
with st.sidebar:
    st.header("Connections")
    show Strava connection status (StravaClient().check_connection())
    show Fitbit connection status (FitbitClient().check_connection())

    st.divider()

    st.header("Sessions")
    if st.button("New Chat"):
        st.session_state.session_id = create_session()
        st.rerun()

    sessions = get_sessions()
    selected = st.selectbox("Past chats", sessions, format_func=lambda s: s.title)
    st.session_state.session_id = selected.id

-- Main area: tabs
tab_dash, tab_chat = st.tabs(["Dashboard", "Chat"])

with tab_dash:
    render_dashboard()

with tab_chat:
    if "session_id" not in st.session_state:
        st.session_state.session_id = create_session()
    render_chat(st.session_state.session_id)
```

---

## 5. Build Order (Phases)

Build in this exact sequence. Each phase produces something runnable before the next begins.

```
Phase 1 — Foundation (no LLM needed)
  ├── config.py
  ├── src/utils/cache.py
  ├── src/utils/database.py
  └── CHECKPOINT: db initialises, cache singleton works

Phase 2 — Data layer
  ├── src/clients/strava_client.py
  ├── src/clients/fitbit_client.py
  └── CHECKPOINT: both clients fetch real data, cache is warm on second call

Phase 3 — Parser
  ├── src/parsers/hevy_parser.py
  └── CHECKPOINT: paste a raw Strava description, get back structured exercises

Phase 4 — Analysis layer
  ├── src/analysis/readiness.py
  ├── src/analysis/load.py
  ├── src/analysis/dataset.py
  └── CHECKPOINT: build_dataset() returns a real DataFrame with your last 10 sessions

Phase 5 — Memory + Guardrails
  ├── src/memory/store.py
  ├── src/memory/manager.py
  ├── src/guardrails/input_guard.py
  ├── src/guardrails/output_guard.py
  └── CHECKPOINT: guardrail blocks an off-topic query; memory context builds correctly

Phase 6 — Agent layer
  ├── src/agents/state.py
  ├── src/agents/tools/ (all three)
  ├── src/agents/router.py
  ├── src/agents/readiness_agent.py
  ├── src/agents/progress_agent.py
  ├── src/agents/coach_agent.py
  └── CHECKPOINT: invoke the graph with a test query, get a real response

Phase 7 — UI
  ├── ui/dashboard.py
  ├── ui/chat.py
  ├── app.py
  └── CHECKPOINT: full Streamlit app running end-to-end
```

---

## 6. Environment Setup

### `.env.example`

```
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_REFRESH_TOKEN=
FITBIT_CLIENT_ID=
FITBIT_CLIENT_SECRET=
FITBIT_ACCESS_TOKEN=
FITBIT_REFRESH_TOKEN=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:4b
```

### `requirements.txt`

```
streamlit
langchain
langchain-ollama
langgraph
pandas
diskcache
tenacity
pydantic
requests
python-dotenv
```

### Ollama setup (one-time)

```bash
ollama pull qwen2.5:4b
ollama serve
```

---

## 7. Key Design Decisions — Rationale Summary

|Decision|Rationale|
|---|---|
|Analysis in pure Python, not in LLM prompts|Testable, deterministic, model-agnostic|
|Three memory tiers|SQLite history alone breaks at scale; summary + facts solve it|
|Input guardrail before agent load|Zero token cost for off-topic queries|
|Output guardrail is a warning, not a blocker|Better UX than silence; issue is logged for debugging|
|One Ollama instance shared across agents|Predictable memory, simpler config|
|Diskcache at client level, not tool level|Tools are called per-query; clients are called across queries|
|Agents import tools, not clients directly|Clean dependency graph; tools own the client instantiation|
|Dashboard is LLM-free|Charts don't need narration; saves inference time|

---

## 8. Future Considerations (post-MVP)

- **OAuth flow UI** for Strava/Fitbit token refresh (currently manual via .env)
- **Vector search over session history** — semantic queries like "when did I last do legs after poor sleep?"
- **Nutrition integration** — MyFitnessPal or Cronometer API if token becomes available
- **Android port** — Flutter frontend + this backend running as a FastAPI server, on-device Gemini Nano for narration
- **BigQuery export** — dump the session dataset periodically for long-term analytics

---

_End of Development Plan_