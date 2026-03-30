# 003 — UI Roadmap: Design, History, and Tests

**Date:** 2026-03-31  
**Status:** Draft  
**Scope:** Dashboard/Coach visual refinement, History page implementation, phase08 UI test coverage

---

## Problem Statement

The app now has a better page structure, but three follow-up gaps remain:

1. The Dashboard and Coach pages use the extra space more effectively than before, but the interface still looks like a first-pass utility UI.
2. The History page is still a placeholder, so the local workout cache is not fully exposed to the user.
3. The multipage surface is not yet protected by UI-focused tests.

---

## Goal

> Execute the next UI roadmap in three phases: improve presentation, add workout browsing, then add UI regression coverage.

---

## Phase Order

```text
Phase A: Visual design improvements
Phase B: History page implementation
Phase C: UI test layer
```

Phase A and B are logically independent, but the recommended execution order is A → B → C so the test layer reflects the intended final UI behavior.

---

## Files To Add Or Modify

| File | Change | Purpose |
|---|---|---|
| `ui/dashboard.py` | MODIFY | Improve metric presentation, chart framing, and last-workout layout |
| `ui/pages/coach.py` | MODIFY | Improve session controls and page context display |
| `ui/shared.py` | MODIFY | Host shared UI helpers such as `format_set()` |
| `ui/pages/history.py` | MODIFY | Replace placeholder with a filterable, paginated workout browser |
| `src/utils/database.py` | MODIFY | Add filtered workout query helper(s) for History page |
| `tests/conftest.py` | MODIFY | Add shared DB fixture(s) for UI tests |
| `tests/phase-tests/test_phase08_ui_dashboard.py` | NEW | Dashboard page UI tests |
| `tests/phase-tests/test_phase08_ui_coach.py` | NEW | Coach page UI tests |
| `tests/phase-tests/test_phase08_ui_history.py` | NEW | History page UI tests |
| `tests/phase-tests/test_phase08_ui_settings.py` | NEW | Settings page UI tests |

---

## Phase A — Visual Design Improvements

### A.1 Dashboard metric row

In `ui/dashboard.py`:

- add icons to metric labels
- wrap metric blocks in bordered containers for stronger separation
- add a fourth metric for weekly session count
- color ACWR interpretation through `delta_color` based on zone

Target metrics:

- `⚡ Today's Readiness`
- `🏋️ This Week's Volume`
- `📊 ACWR`
- `🗓️ Sessions This Week`

### A.2 Dashboard chart framing

- wrap readiness and volume chart blocks in bordered containers
- give each chart more framing context and spacing
- avoid the current flat divider-to-chart flow

### A.3 Last workout redesign

- split the section into two columns
- left column: exercise expanders
- right column: summary card with duration, sets, volume, readiness label, and technique flags

### A.4 Coach page controls

In `ui/pages/coach.py`:

- move away from the current split-column control layout with an empty spacer
- use a full-width session selector followed by a full-width `+ New Chat` button
- add a session title caption below the page header
- separate controls from the chat body with a divider

---

## Phase B — History Page

### B.1 Shared formatting helper

Move `format_set()` out of `ui/dashboard.py` into `ui/shared.py` so both Dashboard and History can render exercise sets without an indirect page dependency.

### B.2 Filtered workout queries

Add helper(s) in `src/utils/database.py` for practical History page data access.

Recommended shape:

```python
def get_workouts_filtered(
    start_date: str | None = None,
    end_date: str | None = None,
    title_query: str | None = None,
    min_volume: float | None = None,
    max_volume: float | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    ...
```

Keep `muscle_groups` filtering in the page layer if it remains stored as JSON text.

### B.3 History page layout

Replace the placeholder in `ui/pages/history.py` with:

1. a page header and short explanatory caption
2. a filter row including:
   - date range
   - workout title search
   - muscle group multiselect
   - volume threshold or range
3. a summary row showing:
   - result count
   - total volume in view
   - average readiness in view
4. a paginated result list using workout cards or expanders

### B.4 Workout detail rendering

Each workout result should expose:

- date and title
- total volume, duration, exercises, and sets
- readiness label when present
- expanded exercise detail using the shared `format_set()` helper

### B.5 Pagination

Use `st.session_state` for page index and render results in fixed-size pages, such as 10 workouts at a time.

---

## Phase C — UI Test Layer

### C.1 Shared fixture setup

Promote a reusable temporary database fixture into `tests/conftest.py` so UI tests can seed isolated sessions and workouts consistently.

### C.2 Streamlit UI test approach

Use built-in Streamlit testing support (`streamlit.testing.v1.AppTest`) rather than adding a separate UI test dependency.

### C.3 Dashboard tests

Create `test_phase08_ui_dashboard.py` with coverage for:

- empty-state render
- populated dashboard render
- cache-clear button visibility/behavior

### C.4 Coach tests

Create `test_phase08_ui_coach.py` with coverage for:

- page render with existing sessions
- new-session creation
- session selector options

### C.5 History tests

Create `test_phase08_ui_history.py` with coverage for:

- empty render
- title filtering
- pagination behavior
- exercise detail rendering for a seeded workout

### C.6 Settings tests

Create `test_phase08_ui_settings.py` with coverage for:

- page render
- sync button dispatch using a mocked sync helper
- cache-clear action using a mocked cache object

---

## Pseudocode

### Dashboard metric framing

```python
metric_columns = st.columns(4)

with metric_columns[0]:
    with st.container(border=True):
        st.metric("⚡ Today's Readiness", score, label)

with metric_columns[1]:
    with st.container(border=True):
        st.metric("🏋️ This Week's Volume", volume_text)

with metric_columns[2]:
    with st.container(border=True):
        st.metric("📊 ACWR", ratio, zone, delta_color=delta_color)

with metric_columns[3]:
    with st.container(border=True):
        st.metric("🗓️ Sessions This Week", weekly["session_count"])
```

### History page flow

```python
filters = render_history_filters()
rows = load_filtered_workouts(filters)
rows = apply_muscle_group_filter(rows, filters.selected_muscle_groups)

render_history_summary(rows)
render_history_results(rows, page=st.session_state.history_page)
render_history_pagination(rows)
```

### UI tests with AppTest

```python
from streamlit.testing.v1 import AppTest

def test_history_page_loads(fresh_db):
    at = AppTest.from_file("ui/pages/history.py")
    at.run()
    assert not at.exception
```

---

## Validation Plan

1. Run the app and verify the updated Dashboard and Coach layouts manually.
2. Run the app and verify History filtering and pagination manually.
3. Run `pytest tests/phase-tests/test_phase08_ui_*.py -v` once the UI tests are added.
4. Run the full suite with `python -m pytest -q` from the project virtualenv.

---

## Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Shared helper placement creates awkward dependencies | Hard-to-maintain imports | Put formatting helpers in `ui/shared.py` |
| History filtering becomes slow or overcomplicated | Poor page responsiveness | Push simple filters into SQL, keep JSON-specific filtering in the page layer |
| UI tests become brittle during active design changes | Maintenance cost | Add tests after the target UI behavior is implemented |
| Page state leaks between tests | Flaky results | Use isolated DB fixtures and page-local AppTest runs |

---

## Out Of Scope

- Replacing Streamlit with another frontend framework
- Redesigning the backend architecture
- Changing sync semantics or analysis calculations
- Adding live collaborative or multi-user UI behavior

---

## Related

- [mark-ii-ui-roadmap-dev-plan_20260331.md](../dev-plan/mark-ii-ui-roadmap-dev-plan_20260331.md)
- [002_mark-ii_streamlit_multipage_ui_20260331.md](002_mark-ii_streamlit_multipage_ui_20260331.md)
- [technical_reference.md](../technical_reference.md)
