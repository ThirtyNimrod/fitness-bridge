# 001 — Local Workout Cache & DB-Driven Queries

**Date:** 2026-03-25  
**Status:** Draft  
**Scope:** Data persistence layer, sync engine, agent refactor

---

## Problem Statement

The app currently calls the Strava and Fitbit APIs **live on every user query and every dashboard render**. This causes:

1. **Fragility** — any network hiccup (like the `ConnectionResetError 10054` we're seeing) makes the AI return nothing usable.
2. **Latency** — each query waits for 3-10 API round trips before the agent can even start.
3. **Waste** — workout data that existed yesterday is re-fetched identically today.
4. **No offline resilience** — if Strava goes down, the app is blind.

---

## Goal

> Fetch from APIs only when necessary (new data exists or tokens just refreshed).  
> All AI queries and dashboard renders read from a **local SQLite cache**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  App startup / Manual Sync trigger                  │
│                                                     │
│  SyncEngine.sync()                                  │
│    ├── Strava: fetch activities since last_synced   │
│    ├── Fitbit: fetch sleep/HRV/HR for each new date │
│    ├── Join → build_session_record()                │
│    └── Upsert into SQLite `workouts` table          │
└──────────────────────┬──────────────────────────────┘
                       │ (one-time per session, or on demand)
                       ▼
┌─────────────────────────────────────────────────────┐
│  SQLite DB  (data/fitness_bridge.db)                │
│                                                     │
│  workouts table                                     │
│    activity_id (PK), date, workout_title,           │
│    duration_min, total_volume_kg, exercise_count,   │
│    set_count, exercises_raw, muscle_groups,         │
│    has_drop_sets, has_failure_sets,                 │
│    sleep_hours, sleep_efficiency,                   │
│    hrv_ms, resting_hr,                              │
│    readiness_score, readiness_label,                │
│    synced_at                                        │
│                                                     │
│  sync_meta table                                    │
│    source (strava/fitbit), last_synced_at           │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐     ┌──────────────────────────┐
│  AI Agent Tools  │     │  Dashboard               │
│  (read DB only)  │     │  (read DB only)           │
└──────────────────┘     └──────────────────────────┘
```

---

## New / Modified Files

| File | Change | Purpose |
|---|---|---|
| `src/utils/database.py` | **MODIFY** | Add `workouts` + `sync_meta` tables and CRUD helpers |
| `src/sync/engine.py` | **NEW** | `SyncEngine` class — delta sync logic |
| `src/sync/__init__.py` | **NEW** | Package marker |
| `src/utils/token_writer.py` | **NEW** | Write refreshed Fitbit/Strava tokens back to `.env` |
| `src/analysis/dataset.py` | **MODIFY** | Replace live API calls with DB reads |
| `app.py` | **MODIFY** | Startup sync + 2-hour background thread + sidebar UI |
| `ui/dashboard.py` | **MODIFY** | Read from DB instead of calling `build_dataset()` live |
| `scripts/manage.ps1` | **NEW** | Single script to `run`, `stop`, `restart` the app |

---

## Pseudocode

### 1. `database.py` — new table schema

```python
# In init_db(), add alongside existing tables:

cursor.execute('''
    CREATE TABLE IF NOT EXISTS workouts (
        activity_id     TEXT PRIMARY KEY,
        date            TEXT NOT NULL,
        workout_title   TEXT,
        duration_min    REAL,
        total_volume_kg REAL,
        exercise_count  INTEGER,
        set_count       INTEGER,
        exercises_raw   TEXT,   -- JSON string
        muscle_groups   TEXT,   -- JSON string
        has_drop_sets   INTEGER,
        has_failure_sets INTEGER,
        sleep_hours     REAL,
        sleep_efficiency REAL,
        hrv_ms          REAL,
        resting_hr      REAL,
        readiness_score REAL,
        readiness_label TEXT,
        synced_at       DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS sync_meta (
        source          TEXT PRIMARY KEY,   -- 'strava' | 'fitbit'
        last_synced_at  DATETIME
    )
''')

# New helpers:
def upsert_workout(record: dict): ...
def get_workouts(n_days=30) -> list[dict]: ...
def get_workout_by_date(date_str: str) -> dict | None: ...
def get_last_synced(source: str) -> datetime | None: ...
def set_last_synced(source: str): ...
```

---

### 2. `src/sync/engine.py` — NEW

```python
class SyncEngine:
    def __init__(self):
        self.strava = StravaClient()
        self.fitbit = FitbitClient()

    def sync(self, force=False) -> dict:
        """
        Delta sync: only fetch activities newer than last_synced_at.
        Returns {"synced": N, "errors": M, "last_synced_at": datetime}
        """
        last_synced = get_last_synced("strava")   # None on first run
        activities  = self.strava.get_activities(per_page=50)

        new_activities = [
            a for a in activities
            if force or not last_synced
            or parse_datetime(a["start_date_local"]) > last_synced
        ]

        for activity in new_activities:
            date    = activity["start_date_local"][:10]
            detail  = safe_fetch(self.strava.get_activity_detail, activity["id"])
            sleep   = safe_fetch(self.fitbit.get_sleep, date)
            hrv     = safe_fetch(self.fitbit.get_hrv, date)
            rhr     = safe_fetch(self.fitbit.get_resting_hr, date)

            exercises = parse_description((detail or activity).get("description", ""))
            readiness = compute_readiness(sleep, hrv, rhr)
            record    = build_session_record(detail or activity, exercises, readiness)
            upsert_workout(record)

        set_last_synced("strava")
        return {"synced": len(new_activities), "last_synced_at": datetime.now()}
```

---

### 3. `src/utils/token_writer.py` — NEW

```python
"""
Writes refreshed API tokens back to .env so they survive restarts.
Called by the client classes after a successful token refresh.
"""

def write_token_to_env(key: str, value: str):
    """
    Reads .env, replaces the line KEY=... with KEY=new_value, writes back.
    Thread-safe via a file lock.
    """
    env_path = find_dotenv()   # from python-dotenv
    lines = open(env_path).readlines()
    updated = []
    for line in lines:
        if line.startswith(f"{key}="):
            updated.append(f"{key}={value}\n")
        else:
            updated.append(line)
    open(env_path, "w").writelines(updated)
    app_logger.info(f"Token updated in .env: {key}")
```

Then in `fitbit_client.py` after a successful refresh:
```python
from src.utils.token_writer import write_token_to_env

# Inside _refresh_access_token(), after getting new tokens:
self.access_token  = json_data["access_token"]
self.refresh_token = json_data["refresh_token"]
write_token_to_env("FITBIT_ACCESS_TOKEN",  self.access_token)
write_token_to_env("FITBIT_REFRESH_TOKEN", self.refresh_token)
```

---

### 4. `dataset.py` — refactored

```python
# BEFORE: live API calls on every query
# AFTER: instant DB reads

def build_dataset(n_days=30) -> pd.DataFrame:
    rows = get_workouts(n_days=n_days)
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def get_session_for_date(date_str) -> dict | None:
    return get_workout_by_date(date_str)
```

---

### 5. `app.py` — sync wiring

```python
from src.sync.engine import SyncEngine
import threading, time

# ── Background 2-hour auto-sync ──────────────────────
def _background_sync_loop():
    while True:
        time.sleep(2 * 60 * 60)   # 2 hours
        try:
            SyncEngine().sync()
        except Exception as e:
            app_logger.warning(f"Background sync failed: {e}")

@st.cache_resource
def start_background_sync():
    t = threading.Thread(target=_background_sync_loop, daemon=True)
    t.start()

# ── Startup sync (once per Streamlit session) ─────────
@st.cache_resource
def run_startup_sync():
    try:
        result = SyncEngine().sync()
        app_logger.info(f"Startup sync: {result['synced']} new workouts")
    except Exception as e:
        app_logger.warning(f"Startup sync failed: {e}")

run_startup_sync()
start_background_sync()

# ── Sidebar UI ────────────────────────────────────────
with st.sidebar:
    ...
    st.divider()

    last_sync = get_last_synced("strava")

    if st.button("🔄 Sync Workouts", use_container_width=True):
        with st.spinner("Syncing..."):
            try:
                result = SyncEngine().sync(force=True)
                st.success(f"Synced {result['synced']} workouts.")
            except Exception as e:
                st.warning("Sync failed — showing last cached data.")

    if last_sync:
        st.caption(f"Last synced: {last_sync.strftime('%d %b %Y, %H:%M')}")
    else:
        st.caption("Never synced — click Sync Workouts.")
```

---

### 6. `scripts/manage.ps1` — NEW

```powershell
# Usage:
#   .\scripts\manage.ps1 run
#   .\scripts\manage.ps1 stop
#   .\scripts\manage.ps1 restart

param([string]$Command = "run")

$PidFile = Join-Path $PSScriptRoot "..\run.pid"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Start-App {
    $proc = Start-Process ".venv\Scripts\streamlit.exe" `
        -ArgumentList "run app.py" `
        -WorkingDirectory $ProjectRoot `
        -PassThru -NoNewWindow
    $proc.Id | Set-Content $PidFile
    Write-Host "✅ App started (PID $($proc.Id))"
}

function Stop-App {
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile
        Write-Host "🛑 App stopped (PID $pid)"
    } else {
        Write-Host "⚠️  No PID file found — app may not be running."
    }
}

switch ($Command) {
    "run"     { Start-App }
    "stop"    { Stop-App }
    "restart" { Stop-App; Start-App }
    default   { Write-Host "Usage: manage.ps1 [run|stop|restart]" }
}
```

> **On Ctrl+C**: Ctrl+C sends SIGINT to Streamlit, which exits cleanly by itself. The `manage.ps1 stop` command is what guarantees token cleanup and PID file removal. For guaranteed shutdown behaviour, always use `manage.ps1 stop` rather than Ctrl+C.

---

## Implementation Order

1. `database.py` — add `workouts` + `sync_meta` tables and helpers
2. `src/utils/token_writer.py` — write refreshed tokens to `.env`
3. `src/clients/fitbit_client.py` + `strava_client.py` — call token_writer after refresh
4. `src/sync/engine.py` — implement `SyncEngine`
5. `dataset.py` — replace live calls with DB reads
6. `app.py` — startup sync, background thread, sidebar UI
7. `scripts/manage.ps1` — management script
8. **Tests** — `test_sync.py` (upsert idempotency, delta logic), `test_token_writer.py`

---

## Design Decisions (Resolved)

| Question | Decision |
|---|---|
| Auto-sync frequency | Startup + every 2 hours (background daemon thread) + manual "Sync Workouts" button |
| Sync failure behaviour | Serve stale DB data, show warning + "Last synced: DATE TIME" caption below sync button |
| Token refresh persistence | Write back to `.env` via `token_writer.py` after every successful refresh |
| App lifecycle management | `scripts/manage.ps1 [run\|stop\|restart]` — PID-file based; Ctrl+C alone is not guaranteed to clean up |


---

## Pseudocode

### 1. `database.py` — new table schema

```python
# In init_db(), add alongside existing tables:

cursor.execute('''
    CREATE TABLE IF NOT EXISTS workouts (
        activity_id     TEXT PRIMARY KEY,
        date            TEXT NOT NULL,
        workout_title   TEXT,
        duration_min    REAL,
        total_volume_kg REAL,
        exercise_count  INTEGER,
        set_count       INTEGER,
        exercises_raw   TEXT,   -- JSON string
        muscle_groups   TEXT,   -- JSON string
        has_drop_sets   INTEGER,
        has_failure_sets INTEGER,
        sleep_hours     REAL,
        sleep_efficiency REAL,
        hrv_ms          REAL,
        resting_hr      REAL,
        readiness_score REAL,
        readiness_label TEXT,
        synced_at       DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS sync_meta (
        source          TEXT PRIMARY KEY,   -- 'strava' | 'fitbit'
        last_synced_at  DATETIME
    )
''')

# New helpers to add:

def upsert_workout(record: dict):
    """Insert or update a workout row keyed on activity_id."""
    ...

def get_workouts(n_days=30) -> list[dict]:
    """Return workouts from the last N days, newest first."""
    ...

def get_workout_by_date(date_str: str) -> dict | None:
    """Return single workout row for a specific date."""
    ...

def get_last_synced(source: str) -> datetime | None:
    """Return last sync timestamp for a given source."""
    ...

def set_last_synced(source: str):
    """Update sync timestamp to now."""
    ...
```

---

### 2. `src/sync/engine.py` — NEW

```python
class SyncEngine:
    def __init__(self):
        self.strava = StravaClient()
        self.fitbit = FitbitClient()

    def sync(self, force=False):
        """
        Delta sync: only fetch activities newer than last_synced_at.
        If force=True, re-fetches all N days regardless.
        """
        last_synced = get_last_synced("strava")  # None on first run

        # Fetch from Strava
        activities = self.strava.get_activities(per_page=50)

        new_activities = []
        for activity in activities:
            date = activity["start_date_local"][:10]

            # Skip if we already have this and it's not forced
            if not force and last_synced:
                activity_dt = parse_datetime(activity["start_date_local"])
                if activity_dt <= last_synced:
                    continue  # already synced

            new_activities.append((activity, date))

        app_logger.info(f"Sync: {len(new_activities)} new activities to process")

        for activity, date in new_activities:
            # Fetch Fitbit for this date
            sleep_data = safe_fetch(self.fitbit.get_sleep, date)
            hrv_data   = safe_fetch(self.fitbit.get_hrv, date)
            resting_hr = safe_fetch(self.fitbit.get_resting_hr, date)

            # Fetch Strava detail (for Hevy description)
            detail      = safe_fetch(self.strava.get_activity_detail, activity["id"])
            description = detail.get("description", "") if detail else ""

            # Build the unified record
            exercises = parse_description(description)
            readiness = compute_readiness(sleep_data, hrv_data, resting_hr)
            record    = build_session_record(detail or activity, exercises, readiness)

            # Persist to DB
            upsert_workout(record)

        set_last_synced("strava")
        app_logger.info("Sync complete.")

def safe_fetch(fn, *args):
    """Call fn(*args), return None on any exception."""
    try:
        return fn(*args)
    except Exception as e:
        app_logger.warning(f"safe_fetch failed for {fn.__name__}: {e}")
        return None
```

---

### 3. `src/analysis/dataset.py` — refactored

```python
# BEFORE (current):
def build_dataset(n_days=30):
    strava_client = StravaClient()       # ← API call every time
    fitbit_client = FitbitClient()       # ← API call every time
    activities = strava_client.get_activities(per_page=n_days)  # ← API call
    for activity in activities:
        sleep_data = fitbit_client.get_sleep(date_str)  # ← API call per row
        ...

# AFTER (proposed):
def build_dataset(n_days=30):
    rows = get_workouts(n_days=n_days)  # ← local DB read, instant
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)

def get_session_for_date(date_str):
    return get_workout_by_date(date_str)  # ← local DB read, instant
```

---

### 4. `app.py` — add sync on startup

```python
# After init_db(), add:
from src.sync.engine import SyncEngine

@st.cache_resource
def run_initial_sync():
    """Run once per Streamlit session. Syncs new data from APIs to DB."""
    engine = SyncEngine()
    engine.sync()          # delta sync — skips already-cached data
    return True

# In main body, after init_db():
with st.spinner("Syncing latest workouts..."):
    run_initial_sync()
```

Also add a **manual "Sync Now" button** in the sidebar:
```python
if st.sidebar.button("🔄 Sync Workouts"):
    engine = SyncEngine()
    engine.sync(force=True)   # force re-fetch all
    st.sidebar.success("Sync complete!")
```

---

### 5. Strava + Fitbit data correlation

Currently `build_session_record()` already joins them by date — this stays unchanged.
The sync engine calls it once per activity during the sync window, and the result
is persisted. After sync, all data is in one row per workout:

```
workouts row for 2026-03-23:
  workout_title    = "Upper Body Push"
  total_volume_kg  = 4820
  exercises_raw    = '[{"name":"Bench Press", ...}]'
  sleep_hours      = 7.2      ← Fitbit
  hrv_ms           = 48.3     ← Fitbit
  readiness_score  = 72       ← computed
```

The agent tools (`src/agents/tools/`) should be updated to query this table
directly via `get_workouts()` / `get_workout_by_date()` instead of calling
`build_dataset()`.

---

## Implementation Order

1. **`database.py`** — add `workouts` + `sync_meta` tables and helpers
2. **`src/sync/engine.py`** — implement `SyncEngine`
3. **`dataset.py`** — replace live calls with DB reads
4. **`app.py`** — wire in startup sync + sidebar button
5. **Agent tools** — point at DB helpers; remove any direct `build_dataset()` calls
6. **Tests** — add `test_sync.py` to verify upsert idempotency and delta logic

---

## Open Decisions

| Question | Options |
|---|---|
| How often to auto-sync? | On startup only vs. every N minutes via background thread |
| What if sync fails completely (no internet)? | Serve stale DB data with a warning banner |
| Fitbit token refresh persistence | Write new tokens back to `.env` after refresh (known gap from session notes) |
