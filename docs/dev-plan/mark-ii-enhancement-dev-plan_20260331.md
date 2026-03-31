# Mark II Enhancement Development Plan

**Date:** 2026-03-31  
**Status:** Proposed  
**Scope:** Multi-source workout sync, chat management, visual theming, analysis depth, memory UX, dashboard improvements, agent intelligence, and developer experience

---

## Problem Statement

Fitness Bridge currently relies exclusively on Strava for workouts and Fitbit only for biometrics (sleep, HRV, resting HR). Several daily-use UX gaps remain: users cannot organise or clean up chat sessions, the interface is visually plain, and the analysis layer lacks metrics that would make coaching meaningfully smarter.

Key gaps:

1. **Pixel Watch 2 workouts are invisible.** Badminton, Walk, Treadmill, Strength Training, and Weightlifting sessions tracked via Fitbit never reach the app.
2. **Chat sessions cannot be deleted, renamed, or automatically titled.**
3. **The UI has no branding, colour hierarchy, or visual polish.**
4. **The analysis layer is missing per-muscle-group volume, 1RM estimation, PR detection, and deload recognition.**
5. **Stored semantic facts are invisible to the user — no way to view, edit, or correct what the AI "knows."**
6. **The dashboard is locked to a single time window with no HR zone or calorie visualisation.**
7. **The coach agent binds 9 tools at once, which challenges small LLMs, and routing decisions are opaque.**
8. **Database indexes, sync audit logging, and API quota awareness are absent.**

---

## Goal

> Evolve Fitness Bridge from a Strava-only workout tracker into a multi-source, visually polished, analytically deep fitness coaching platform — while keeping each phase independently shippable and testable.

---

## Roadmap Phases

### Phase 1 — Fitbit Activity Sync (Pixel Watch 2 Workouts)

Unlock all workout data from Pixel Watch 2 via the Fitbit Web API.

- Add `get_activities(before_date, limit)` and `get_activity_detail(log_id)` to `FitbitClient`
- Create activity type mapping (`activityTypeId` → strength / cardio / sport / walking / other)
- Schema v3 migration: add `source`, `workout_type`, `calories`, `hr_zones`, `distance_km` columns; change PK to composite `(source, activity_id)`; add date index
- Add Fitbit activity sync path in `SyncEngine` with its own `sync_meta` key
- Add `build_fitbit_session_record()` for duration/calories/HR shape
- Update History page with source badges and non-exercise workout cards
- Update Dashboard to include Fitbit workouts in charts

### Phase 2 — Chat Management (Delete / Rename / Dynamic Names)

Remove daily UX friction around session organisation.

- Add `delete_session(session_id)` with explicit cascade delete of messages
- Add `rename_session(session_id, title)` in database layer
- Add inline rename (✏️) and delete (🗑️) controls in coach page session picker
- Auto-generate 3–5 word chat titles after first assistant response via LLM

### Phase 3 — Custom CSS + UI Theming

Visual polish across all pages.

- Create `.streamlit/config.toml` with branded colour palette
- Create `ui/styles.py` with `inject_css()` function
- Style chat messages with distinct user/assistant bubbles and avatars
- Style metric cards with readiness-zone-keyed coloured borders
- Style sidebar with branding and connection status pills
- Add loading skeleton CSS classes
- Optional: custom web font

### Phase 4 — Analysis Enhancements (Volume, 1RM, PRs)

Make the coach agent meaningfully smarter with computable metrics.

- Per-muscle-group weekly volume aggregation from `exercises_raw` JSON
- 1RM estimation via Epley formula
- Personal record detection by scanning exercises across all workouts
- Progressive overload detection (last 3 instances of same exercise)
- Deload week detection (volume drop > 30%)
- Expose new metrics as agent tools

### Phase 5 — Memory / Fact Management UI

Let users see and control what the AI stores about them.

- Add fact management section to Settings page
- Display all semantic facts in an editable table
- Add edit and delete controls per fact
- Improve fact extraction reliability with validation and fallback patterns

### Phase 6 — Dashboard Improvements

Small effort, big usability wins.

- Add time range toggle (7d / 14d / 30d / 90d) replacing hardcoded 28-day window
- Add calendar heatmap widget for workout consistency
- Add HR zone time-in-zone chart (requires Phase 1)
- Add calorie burn trend chart (requires Phase 1)

### Phase 7 — Agent Intelligence

Reduce tool sprawl and improve transparency.

- Split coach agent's 9-tool binding into intent-focused subsets
- Show routing decision in chat UI ("Routed to: Readiness Specialist")
- Add follow-up question capability for ambiguous queries

### Phase 8 — Developer Experience + Resilience

Guard rails for growing complexity.

- Add database indexes on `date` column
- Add sync audit log table (`sync_log`)
- Add startup config validation for required env vars
- Add Strava API quota tracking (100 req/15min, 1000/day)

---

## Phase Dependencies

| Phase | Depends On | Can Parallel With |
|---|---|---|
| 1. Fitbit Activity Sync | — | — |
| 2. Chat Management | — | Phase 1 |
| 3. CSS Theming | — | Phase 1, 2 |
| 4. Analysis Enhancements | Phase 1 (Fitbit workout types) | Phase 2, 3 |
| 5. Memory/Fact UI | — | Phase 1, 2, 3 |
| 6. Dashboard Improvements | Phase 1 (HR zones, calories) | Phase 2, 3, 5 |
| 7. Agent Intelligence | Phase 4 (new tools) | Phase 3, 5, 6 |
| 8. Dev Experience | Phase 1 (new schema) | Any |

Phases 1, 2, and 3 can execute in parallel since they touch different layers.

---

## Scope Boundaries

**Included:** All 8 phases above.

**Excluded (deferred to future plans):**
- Custom frontend (replacing Streamlit)
- REST/WebSocket API layer
- Nutrition integration (MyFitnessPal, Cronometer)
- Training plan generator
- Voice input
- Export / PDF reports
- Body composition tracking
- Workout template system

---

## Success Criteria

- Fitbit activities from Pixel Watch 2 appear in History and Dashboard
- Chat sessions can be created, renamed, auto-titled, and deleted
- The app has a consistent visual identity across all pages
- Coach can answer muscle-group volume, 1RM, and PR questions with data
- Users can view, edit, and delete stored semantic facts
- Dashboard supports multiple time ranges and shows workout heatmap
- All existing tests continue to pass after each phase
