# 002 — Streamlit Multipage UI Refactor

**Date:** 2026-03-31  
**Status:** Draft  
**Scope:** Streamlit UI structure, page split, sidebar simplification, settings extraction

---

## Problem Statement

The current UI is trying to fit four distinct concerns into one layout:

1. Application operations: connection status and sync controls
2. Chat operations: session selection and session creation
3. Analytics: dashboard metrics and charts
4. Coaching: streaming AI chat

This makes the sidebar overloaded and forces the dashboard and coach experiences to compete for the same page real estate.

---

## Goal

> Refactor the Streamlit app into a multipage structure while preserving the existing backend contracts and minimizing UI-layer churn.

---

## Target Architecture

```text
app.py
  ├── shared initialization
  ├── streamlit page navigation
  ├── slim sidebar
  └── page execution

ui/
  ├── chat.py
  ├── dashboard.py
  ├── shared.py
  ├── components/
  │   └── sidebar.py
  └── pages/
      ├── dashboard.py
      ├── coach.py
      ├── history.py
      └── settings.py
```

---

## Files To Add Or Modify

| File | Change | Purpose |
|---|---|---|
| `app.py` | MODIFY | Replace tab-based layout with Streamlit multipage navigation |
| `ui/shared.py` | NEW | Shared sync, connection, and startup helpers for page-level access |
| `ui/components/sidebar.py` | NEW | Lightweight persistent sidebar status renderer |
| `ui/pages/dashboard.py` | NEW | Thin page wrapper around `render_dashboard()` |
| `ui/pages/coach.py` | NEW | Session controls + chat page wrapper around `render_chat()` |
| `ui/pages/history.py` | NEW | Placeholder page for future workout browsing |
| `ui/pages/settings.py` | NEW | Connections, sync, cache, and model visibility page |
| `ui/chat.py` | KEEP | Preserve existing chat rendering and stream behavior |
| `ui/dashboard.py` | KEEP | Preserve existing dashboard rendering |

---

## Implementation Plan

### 1. Extract shared UI helpers

Create `ui/shared.py` and move the following from `app.py` into it:

- `_sync_lock`
- `run_sync_with_lock(force: bool = False)`
- `_background_sync_loop()`
- `start_background_sync()`
- `run_startup_sync()`
- `get_connection_statuses()`

This avoids circular imports when multiple page modules need access to sync state and connection checks.

---

### 2. Convert `app.py` into a navigation entrypoint

Keep:

- environment loading
- `init_db()`
- startup sync and background sync bootstrapping
- `st.set_page_config(...)`

Replace:

- the current sidebar block
- dashboard/chat tabs

With:

```python
dashboard_page = st.Page("ui/pages/dashboard.py", title="Dashboard", icon="📊", default=True)
coach_page = st.Page("ui/pages/coach.py", title="AI Coach", icon="💬")
history_page = st.Page("ui/pages/history.py", title="History", icon="📋")
settings_page = st.Page("ui/pages/settings.py", title="Settings", icon="⚙️")

navigation = st.navigation([dashboard_page, coach_page, history_page, settings_page])
navigation.run()
```

Also ensure `st.session_state.session_id` exists before page execution begins.

---

### 3. Add a slim shared sidebar

Create `ui/components/sidebar.py` that renders:

- compact Strava status
- compact Fitbit status
- last synced caption
- a short pointer to Settings for detailed controls

The sidebar should stop being the primary control surface.

---

### 4. Add dedicated page entrypoints

#### `ui/pages/dashboard.py`
- Import and call `render_dashboard()` from `ui/dashboard.py`
- No page-local business logic beyond page title or small framing text

#### `ui/pages/coach.py`
- Render chat session picker and new-session button at the top of the page
- Use `create_session()` and `get_sessions()` from `src/utils/database.py`
- Persist active session using `st.session_state.session_id`
- Call `render_chat(session_id)` from `ui/chat.py`

#### `ui/pages/history.py`
- Add a placeholder page that establishes the navigation slot now
- Initial content can be a short explanation and a “coming soon” notice

#### `ui/pages/settings.py`
- Show detailed connection status and errors
- Expose manual sync trigger and last-sync display
- Add cache-clear action using `get_cache().clear()`
- Display read-only `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from `config.py`

---

### 5. Preserve existing renderer modules

Do not break apart `ui/chat.py` and `ui/dashboard.py` unless the page extraction reveals a concrete issue.

This keeps:

- streaming behavior intact
- dashboard rendering intact
- change scope limited to navigation and layout concerns

---

## Pseudocode

### `app.py`

```python
st.set_page_config(page_title="Fitness Bridge AI", layout="wide", page_icon="🏋️")

init_db()
run_startup_sync()
start_background_sync()

if "session_id" not in st.session_state:
    st.session_state.session_id = create_session("Initial Session")

render_sidebar()

navigation = st.navigation([
    st.Page("ui/pages/dashboard.py", title="Dashboard", icon="📊", default=True),
    st.Page("ui/pages/coach.py", title="AI Coach", icon="💬"),
    st.Page("ui/pages/history.py", title="History", icon="📋"),
    st.Page("ui/pages/settings.py", title="Settings", icon="⚙️"),
])

navigation.run()
```

### `ui/pages/coach.py`

```python
st.header("AI Coach")

sessions = get_sessions()
session_dict = {row["id"]: row["title"] for row in sessions}

col_left, col_right = st.columns([3, 1])

with col_left:
    selected_id = st.selectbox(...)
    st.session_state.session_id = selected_id

with col_right:
    if st.button("+ New Chat", use_container_width=True):
        st.session_state.session_id = create_session("New Session")
        st.rerun()

render_chat(st.session_state.session_id)
```

### `ui/pages/settings.py`

```python
st.header("Settings")

statuses = get_connection_statuses()
show_connection_details(statuses)

if st.button("Sync Workouts", use_container_width=True):
    result = run_sync_with_lock(force=True)
    get_connection_statuses.clear()
    st.success(f"Synced {result['synced']} workouts.")

if st.button("Clear Cache"):
    get_cache().clear()
    st.rerun()

st.code(OLLAMA_BASE_URL)
st.code(OLLAMA_MODEL)
```

---

## Validation Plan

1. Run `streamlit run app.py` and verify the navigation shows all four pages.
2. Verify Dashboard renders the same metrics, charts, and workout detail as before.
3. Verify Coach page preserves streaming response behavior.
4. Verify creating a new chat updates `st.session_state.session_id` and persists across page switches.
5. Verify Settings page can trigger sync and reflect updated last-sync state.
6. Verify cache clear still works.
7. Run `pytest` to confirm no backend regressions.

---

## Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Circular imports between app and pages | Broken page startup | Extract shared logic into `ui/shared.py` |
| Session state not initialized on non-coach pages | Chat page crashes later | Initialize `session_id` in `app.py` before navigation runs |
| Sync controls duplicated across sidebar and settings | Confusing UX | Keep detailed controls only in Settings |
| Refactor expands beyond UI layer | Higher regression risk | Preserve existing renderer modules and backend contracts |

---

## Out Of Scope

- Replacing Streamlit with React, Next.js, or another frontend stack
- Exposing a public API layer for the UI
- Reworking analysis or agent internals
- Building the full History page in this change

---

## Related

- [mark-ii-ui-multipage-dev-plan_20260331.md](../dev-plan/mark-ii-ui-multipage-dev-plan_20260331.md)
- [technical_reference.md](../technical_reference.md)
