# 004 — Mark II Enhancement: Multi-Source Sync, Chat Management, Theming, Analysis Depth

**Date:** 2026-03-31  
**Status:** Draft  
**Scope:** Fitbit activity sync, chat delete/rename/auto-title, CSS theming, analysis enhancements, fact management UI, dashboard improvements, agent intelligence, developer experience
**Dev Plan:** `docs/dev-plan/mark-ii-enhancement-dev-plan_20260331.md`

---

## Problem Statement

Fitness Bridge is single-source (Strava-only for workouts), has no chat management, uses vanilla Streamlit styling, and the analysis layer lacks metrics needed for meaningfully smarter coaching. This implementation plan covers the eight phases defined in the enhancement dev plan.

---

## Goal

> Execute the enhancement roadmap across eight independently shippable phases, each with clear file changes, data-shape expectations, and verification steps.

---

## Files To Add Or Modify

| File | Change | Phase | Purpose |
|---|---|---|---|
| `src/clients/fitbit_client.py` | MODIFY | 1 | Add `get_activities()`, `get_activity_detail()`, activity type mapping |
| `src/utils/database.py` | MODIFY | 1, 2, 8 | Schema v3, composite PK, `delete_session()`, `rename_session()`, indexes, sync_log |
| `src/sync/engine.py` | MODIFY | 1, 8 | Fitbit activity sync path, sync audit logging |
| `src/analysis/dataset.py` | MODIFY | 1 | `build_fitbit_session_record()` |
| `src/analysis/load.py` | MODIFY | 4 | Muscle-group volume, deload detection |
| `src/analysis/strength.py` | NEW | 4 | 1RM estimation, PR detection, progressive overload |
| `ui/pages/history.py` | MODIFY | 1 | Source badges, non-exercise workout cards |
| `ui/pages/coach.py` | MODIFY | 2 | Session rename/delete controls, dynamic naming |
| `ui/chat.py` | MODIFY | 2, 7 | Title generation hook, routing info display |
| `ui/styles.py` | NEW | 3 | CSS injection module |
| `.streamlit/config.toml` | NEW | 3 | Streamlit theme configuration |
| `ui/dashboard.py` | MODIFY | 1, 3, 6 | Fitbit workouts in charts, CSS classes, time range toggle, heatmap |
| `ui/components/sidebar.py` | MODIFY | 3 | Branding and styled status pills |
| `app.py` | MODIFY | 3 | Call `inject_css()` |
| `ui/pages/settings.py` | MODIFY | 5 | Fact management section |
| `src/memory/manager.py` | MODIFY | 5 | Improve extraction reliability |
| `src/agents/tools/progress_tools.py` | MODIFY | 4 | Expose muscle volume and PR tools |
| `src/agents/tools/coach_tools.py` | MODIFY | 4 | Deload detection tool |
| `src/agents/coach_agent.py` | MODIFY | 7 | Reduce tool binding per intent |
| `src/agents/router.py` | MODIFY | 7 | Expose routing decision |
| `config.py` | MODIFY | 8 | Startup config validation |
| `tests/phase-tests/test_phase02_clients_and_tokens.py` | MODIFY | 1 | Fitbit activity client tests |
| `tests/phase-tests/test_phase05_sync_engine.py` | MODIFY | 1 | Fitbit sync path tests |
| `tests/phase-tests/test_phase04_analysis.py` | MODIFY | 4 | Analysis enhancement tests |

---

## Phase 1 — Fitbit Activity Sync

### 1.1 Fitbit Client — Activity Methods

Add to `src/clients/fitbit_client.py`:

```python
ACTIVITY_TYPE_MAP = {
    # Fitbit activityTypeId → category
    15000: "sport",       # Badminton
    90013: "strength",    # Strength Training
    90014: "strength",    # Weightlifting
    90015: "strength",    # Weights
    15680: "walking",     # Walk
    15670: "walking",     # Treadmill
    # ... extend as needed
}

@cached(ttl=3600, ignore=("self",))
def get_activities(self, before_date: str | None = None, limit: int = 20) -> list[dict]:
    """Fetch user activity log list from Fitbit."""
    params = {"beforeDate": before_date or datetime.now().strftime("%Y-%m-%d"),
              "offset": 0, "limit": limit, "sort": "desc"}
    resp = self._get("1/user/-/activities/list.json", params=params)
    return resp.get("activities", [])

@cached(ttl=3600, ignore=("self",))
def get_activity_detail(self, log_id: int) -> dict:
    """Fetch detail for a single activity log entry."""
    return self._get(f"1/user/-/activities/{log_id}.json")
```

Apply `@cached` and tenacity retry patterns matching existing methods.

### 1.2 Database Schema v3 Migration

In `src/utils/database.py`, extend the `workouts` table creation and add a migration path:

```sql
-- New columns (migration adds these if missing)
ALTER TABLE workouts ADD COLUMN source TEXT DEFAULT 'strava';
ALTER TABLE workouts ADD COLUMN workout_type TEXT;
ALTER TABLE workouts ADD COLUMN calories REAL;
ALTER TABLE workouts ADD COLUMN hr_zones TEXT;      -- JSON string
ALTER TABLE workouts ADD COLUMN distance_km REAL;

-- New index
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date);

-- Drop old unique constraint and create composite
-- (requires table rebuild in SQLite — create new table, copy, drop, rename)
```

The composite primary key becomes `(source, activity_id)` so Strava activity ID 12345 and Fitbit log ID 12345 coexist.

Update `validate_workout_record()` to accept and default the new fields:

```python
def validate_workout_record(record: dict) -> dict:
    validated = {
        "activity_id": str(record["activity_id"]),
        "source": record.get("source", "strava"),
        "workout_type": record.get("workout_type"),
        "date": record["date"],
        "title": record.get("title", "Untitled"),
        "duration_minutes": float(record.get("duration_minutes", 0)),
        "total_volume_kg": float(record.get("total_volume_kg", 0)),
        "exercises_raw": record.get("exercises_raw", "[]"),
        "readiness_score": record.get("readiness_score"),
        "readiness_label": record.get("readiness_label"),
        "calories": record.get("calories"),
        "hr_zones": record.get("hr_zones"),
        "distance_km": record.get("distance_km"),
    }
    return validated
```

Update `upsert_workout()` INSERT/UPDATE to use `(source, activity_id)` as the conflict target.

### 1.3 Fitbit Session Record Builder

Add to `src/analysis/dataset.py`:

```python
def build_fitbit_session_record(activity: dict, activity_type_map: dict) -> dict:
    """Build a workout record from a Fitbit activity log entry."""
    type_id = activity.get("activityTypeId", 0)
    return {
        "activity_id": str(activity["logId"]),
        "source": "fitbit",
        "workout_type": activity_type_map.get(type_id, "other"),
        "date": activity.get("startTime", "")[:10],
        "title": activity.get("activityName", "Fitbit Activity"),
        "duration_minutes": round(activity.get("activeDuration", 0) / 60000, 1),
        "total_volume_kg": 0,
        "exercises_raw": "[]",
        "calories": activity.get("calories", 0),
        "hr_zones": json.dumps(activity.get("heartRateZones", [])),
        "distance_km": round(activity.get("distance", 0), 2) if activity.get("distanceUnit") == "Kilometer" else None,
    }
```

### 1.4 Sync Engine — Fitbit Path

Add a `_sync_fitbit_activities()` method in `src/sync/engine.py`:

```python
def _sync_fitbit_activities(self) -> int:
    """Sync Fitbit activity log entries alongside Strava workouts."""
    last_synced = self._get_sync_meta("fitbit_activities")
    activities = self.fitbit.get_activities(
        before_date=datetime.now().strftime("%Y-%m-%d"),
        limit=50,
    )
    count = 0
    for activity in activities:
        record = build_fitbit_session_record(activity, ACTIVITY_TYPE_MAP)
        if last_synced and record["date"] <= last_synced:
            continue
        upsert_workout(record)
        count += 1
    if count:
        self._set_sync_meta("fitbit_activities", datetime.now().isoformat())
    return count
```

Call this from `sync()` after the Strava sync path.

### 1.5 UI Updates — History and Dashboard

**History page** (`ui/pages/history.py`):
- Add a source badge column: 🟠 Strava / 🔵 Fitbit
- For Fitbit non-exercise workouts, render duration + calories + HR zones instead of the exercise expander
- Add a source filter in the filter row

**Dashboard** (`ui/dashboard.py`):
- Include Fitbit workouts in session count and volume aggregation
- Show source breakdown in the sessions-this-week metric

### 1.6 Verification

- `pytest tests/phase-tests/test_phase02_clients_and_tokens.py -v` — new Fitbit methods
- `pytest tests/phase-tests/test_phase05_sync_engine.py -v` — Fitbit sync path
- Manual: sync → verify Badminton/Walk/Gym sessions in History with source badges

---

## Phase 2 — Chat Management

### 2.1 Database Helpers

Add to `src/utils/database.py`:

```python
def delete_session(session_id: int) -> bool:
    """Delete a chat session and all its messages."""
    conn = _get_connection()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    return True

def rename_session(session_id: int, title: str) -> bool:
    """Rename a chat session."""
    conn = _get_connection()
    conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()
    return True
```

### 2.2 Dynamic Chat Naming

After the first assistant response in `ui/chat.py`, call the LLM to generate a short title:

```python
def generate_chat_title(user_message: str, assistant_response: str) -> str:
    """Generate a 3-5 word chat title from the first exchange."""
    llm = get_llm()
    prompt = (
        "Generate a concise 3-5 word title for this fitness chat. "
        "Return only the title, no quotes or punctuation.\n\n"
        f"User: {user_message[:200]}\n"
        f"Assistant: {assistant_response[:200]}"
    )
    result = llm.invoke(prompt)
    title = result.content.strip()[:50]
    return title if title else "Chat"
```

Call `rename_session()` with the generated title after the first exchange.

### 2.3 Coach Page Controls

In `ui/pages/coach.py`, add inline controls next to the session picker:

```python
col_select, col_rename, col_delete = st.columns([6, 1, 1])
with col_select:
    session_id = st.selectbox("Session", sessions, format_func=lambda s: s["title"])
with col_rename:
    if st.button("✏️", help="Rename session"):
        # Show rename input in a popover or expander
        ...
with col_delete:
    if st.button("🗑️", help="Delete session"):
        # Show confirmation before deleting
        ...
```

### 2.4 Verification

- `pytest tests/phase-tests/test_phase01_foundation.py -v` — DB helpers
- `pytest tests/phase-tests/test_phase08_ui_coach.py -v` — session controls
- Manual: create → message → verify auto-rename → rename manually → delete → confirm messages gone

---

## Phase 3 — Custom CSS + UI Theming

### 3.1 Streamlit Theme Configuration

Create `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#22c55e"          # green accent
backgroundColor = "#0f172a"       # dark slate
secondaryBackgroundColor = "#1e293b"
textColor = "#f8fafc"
font = "sans serif"
```

### 3.2 CSS Injection Module

Create `ui/styles.py`:

```python
import streamlit as st

def inject_css():
    """Inject custom CSS for visual polish."""
    st.markdown("""
    <style>
    /* Chat bubbles */
    .stChatMessage[data-testid="stChatMessage"] {
        border-radius: 12px;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 1rem;
    }

    /* Readiness zone borders */
    .readiness-green { border-left: 4px solid #22c55e; }
    .readiness-amber { border-left: 4px solid #f59e0b; }
    .readiness-red   { border-left: 4px solid #ef4444; }

    /* Sidebar branding */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem;
    }

    /* Connection status pills */
    .status-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-connected { background: #166534; color: #bbf7d0; }
    .status-disconnected { background: #7f1d1d; color: #fecaca; }

    /* Loading skeleton */
    .skeleton {
        background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 4px;
        height: 1.2rem;
    }
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    </style>
    """, unsafe_allow_html=True)
```

### 3.3 Integration

In `app.py`, call `inject_css()` immediately after `st.set_page_config()`.

### 3.4 Sidebar Branding

Update `ui/components/sidebar.py`:
- Replace emoji connection dots with styled pills using the `.status-pill` class
- Add an app title header or logo placeholder at the top

### 3.5 Verification

- Visual check across all pages (Dashboard, Coach, History, Settings, Diagnostics)
- `pytest tests/phase-tests/test_phase08_ui_dashboard.py -v` — no rendering regressions

---

## Phase 4 — Analysis Enhancements

### 4.1 Muscle-Group Volume

Add to `src/analysis/load.py`:

```python
def compute_muscle_group_volume(df: pd.DataFrame) -> dict[str, float]:
    """Aggregate weekly volume per muscle group from exercises_raw JSON."""
    # Parse exercises_raw, map exercise names to muscle groups,
    # sum weight × reps per group
    ...
```

Requires an exercise-to-muscle-group mapping dict (at minimum: chest, back, shoulders, legs, arms, core).

### 4.2 Strength Module

Create `src/analysis/strength.py`:

```python
def estimate_1rm(weight_kg: float, reps: int) -> float:
    """Estimate 1RM using Epley formula."""
    if reps == 1:
        return weight_kg
    return round(weight_kg * (1 + reps / 30), 1)

def detect_prs(df: pd.DataFrame) -> list[dict]:
    """Scan exercises across workouts, return personal records."""
    # Group by exercise name, find max estimated 1RM, max volume, max reps
    ...

def detect_progressive_overload(df: pd.DataFrame, exercise_name: str) -> dict:
    """Compare last 3 instances of an exercise for progression."""
    # Return trend direction and percentage change
    ...
```

### 4.3 Deload Detection

Add to `src/analysis/load.py`:

```python
def detect_deload_weeks(df: pd.DataFrame) -> list[dict]:
    """Flag weeks where volume dropped >30% from the prior week."""
    ...
```

### 4.4 Agent Tool Exposure

Add tools in `src/agents/tools/progress_tools.py`:
- `get_muscle_group_volume` — returns per-group volume for a given week
- `get_personal_records` — returns current PRs

Add tool in `src/agents/tools/coach_tools.py`:
- `check_deload_status` — reports whether a deload week was detected

### 4.5 Verification

- `pytest tests/phase-tests/test_phase04_analysis.py -v` — new functions
- Manual: ask "How has my chest volume been this week?" — verify data-backed response

---

## Phase 5 — Memory / Fact Management UI

### 5.1 Settings Page — Fact Section

Add to `ui/pages/settings.py`:

```python
st.subheader("🧠 What the AI knows about you")
facts = get_all_facts()
for fact in facts:
    col_text, col_edit, col_del = st.columns([8, 1, 1])
    with col_text:
        st.text(f"{fact['key']}: {fact['value']}")
    with col_edit:
        if st.button("✏️", key=f"edit_{fact['id']}"):
            ...  # inline edit flow
    with col_del:
        if st.button("🗑️", key=f"del_{fact['id']}"):
            delete_fact(fact["id"])
            st.rerun()
```

### 5.2 Extraction Reliability

In `src/memory/manager.py`, replace the bare `except Exception: pass` in `extract_and_store_facts()` with:
- JSON validation of the LLM response
- Fallback regex extraction for common patterns (injury, goal, preference)
- Logging of extraction failures for debugging

### 5.3 Verification

- Manual: view facts → edit one → delete one → verify persistence
- `pytest tests/phase-tests/test_phase06_memory_guardrails.py -v`

---

## Phase 6 — Dashboard Improvements

### 6.1 Time Range Toggle

Replace hardcoded `days=28` with a toggle:

```python
range_options = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}
selected = st.radio("Time range", list(range_options.keys()), horizontal=True, index=2)
days = range_options[selected]
```

Thread `days` through all data-fetching calls.

### 6.2 Calendar Heatmap

Render a GitHub-style contribution grid using workout dates:

```python
def render_heatmap(workout_dates: list[str], days: int):
    """Render a CSS-based calendar heatmap of workout days."""
    ...
```

Use HTML/CSS grid with `unsafe_allow_html=True`, coloured cells by workout count per day.

### 6.3 HR Zone + Calorie Charts (requires Phase 1)

- Time-in-zone stacked bar chart from `hr_zones` JSON column
- Calorie burn line chart from `calories` column

### 6.4 Verification

- Toggle each range, verify data updates correctly
- `pytest tests/phase-tests/test_phase08_ui_dashboard.py -v`

---

## Phase 7 — Agent Intelligence

### 7.1 Tool Set Reduction

In `src/agents/coach_agent.py`, instead of binding all 9 tools:

```python
# Before (current):
tools = readiness_tools + progress_tools + coach_tools  # 9 tools

# After: select tools based on routing classification
TOOL_SETS = {
    "readiness": readiness_tools + [get_coaching_advice],
    "progress": progress_tools + [get_coaching_advice],
    "coaching": coach_tools,
}
```

Pass the classified intent from the router to the coach agent to select the appropriate tool subset.

### 7.2 Routing Visibility

In `ui/chat.py`, display a small caption after routing:

```python
st.caption(f"🔀 Routed to: {route_result['classification'].title()} Specialist")
```

### 7.3 Follow-Up Questions

Add a system prompt instruction that allows the agent to ask for clarification when the query is ambiguous (e.g., "Which exercise do you mean — Bench Press or Incline Bench Press?").

### 7.4 Verification

- `pytest tests/phase-tests/test_phase07_agents.py -v`
- Manual: ask ambiguous question, verify agent requests clarification

---

## Phase 8 — Developer Experience + Resilience

### 8.1 Database Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date);
CREATE INDEX IF NOT EXISTS idx_workouts_source ON workouts(source);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
```

### 8.2 Sync Audit Log

```sql
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    synced_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_detail TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);
```

Write entries from `SyncEngine.sync()` on each run.

### 8.3 Config Validation

Add to `config.py`:

```python
def validate_config():
    """Check required env vars at startup, warn on missing."""
    required = ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET",
                 "FITBIT_CLIENT_ID", "FITBIT_CLIENT_SECRET"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.warning(f"Missing env vars: {', '.join(missing)}. Some features will be unavailable.")
```

### 8.4 Strava API Quota Tracking

Track request counts per 15-minute window in memory, warn when approaching limits (80/100 requests).

### 8.5 Verification

- `pytest tests/phase-tests/test_phase00_environment.py -v`
- `pytest tests/phase-tests/test_phase05_sync_engine.py -v`

---

## Execution Order Summary

```text
┌──────────────────────────────────────────┐
│  Phase 1: Fitbit Activity Sync           │──┐
├──────────────────────────────────────────┤  │
│  Phase 2: Chat Management          ◄────│──┤ parallel
├──────────────────────────────────────────┤  │
│  Phase 3: CSS Theming              ◄────│──┘ parallel
├──────────────────────────────────────────┤
│  Phase 4: Analysis Enhancements          │ ← needs Phase 1
├──────────────────────────────────────────┤
│  Phase 5: Memory / Fact UI               │ ← independent
├──────────────────────────────────────────┤
│  Phase 6: Dashboard Improvements         │ ← needs Phase 1
├──────────────────────────────────────────┤
│  Phase 7: Agent Intelligence             │ ← needs Phase 4
├──────────────────────────────────────────┤
│  Phase 8: Dev Experience + Resilience    │ ← needs Phase 1
└──────────────────────────────────────────┘
```

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Fitbit API rate limits during bulk sync | Paginate with `limit=50`, respect `Retry-After` headers, use existing tenacity backoff |
| SQLite table rebuild for composite PK | Test migration on a copy of production DB first; keep backup script |
| Dynamic chat naming adds latency | Run LLM title generation asynchronously after rendering the response |
| Small LLMs struggle with tool selection even with reduced sets | Test with both Qwen2.5:4b and larger models; fall back to keyword routing if needed |
| CSS injection may break on Streamlit version upgrades | Pin Streamlit version; use `data-testid` selectors which are more stable |
| HR zone data may be missing for older Pixel Watch activities | Gracefully handle missing `heartRateZones` — show "No HR data" instead of crashing |
