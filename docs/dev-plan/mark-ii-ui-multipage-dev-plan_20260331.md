# Mark II UI Multipage Development Plan

**Date:** 2026-03-31  
**Status:** Proposed  
**Scope:** UI structure, navigation, operational controls, future growth path

---

## Problem Statement

The current Streamlit UI is carrying too many responsibilities in a single page:

1. Connection health, sync controls, and chat session management are all packed into the sidebar.
2. Dashboard metrics, charts, workout detail, and AI coaching share the same screen through tabs.
3. The layout is functional, but it does not scale well as the product grows to include history browsing, diagnostics, and richer controls.
4. The app has outgrown a single-screen mental model before it has outgrown Streamlit as a framework.

---

## Goal

> Keep Streamlit, but restructure the app into a multipage interface that separates operational controls from user-facing analysis and coaching.

The objective is to improve clarity and room for growth without introducing a separate frontend stack or an API layer that the current architecture does not need.

---

## Decision Summary

The UI direction for Mark II is:

1. **Stay on Streamlit.** The bottleneck is layout organization, not framework capability.
2. **Adopt multipage navigation.** Split the current UI into dedicated pages for Dashboard, AI Coach, History, and Settings.
3. **Keep existing rendering modules.** Preserve `ui/dashboard.py` and `ui/chat.py` as the main rendering surfaces to minimize refactor risk.
4. **Move operational controls out of the main workspace.** Connection detail, sync actions, cache actions, and model visibility belong in Settings.
5. **Make the sidebar lightweight.** Use it as a persistent status strip rather than a control panel.

---

## Target Experience

### Dashboard
- Full-width training overview
- KPI metrics, readiness trends, load charts, and latest workout detail
- No chat competition for vertical space

### AI Coach
- Dedicated chat workspace
- Session picker and new-session controls placed where they are actually used
- More vertical room for streaming responses and conversation history

### History
- Reserved entry point for browsing prior workouts and later adding filtering/search

### Settings
- Connection health and failure visibility
- Manual sync trigger and last-sync information
- Cache actions and read-only model configuration visibility

---

## Architectural Direction

The UI should move from this shape:

```text
Single Streamlit page
  sidebar = status + sync + sessions
  tabs = dashboard + chat
```

to this shape:

```text
Multipage Streamlit app
  sidebar = slim persistent status
  pages/
    dashboard
    coach
    history
    settings
```

This keeps the Python-first architecture intact and avoids adding a transport layer between the UI and the existing analysis, sync, and agent modules.

---

## Why Not Replace Streamlit Now?

Moving to a custom frontend would require:

1. A formal API layer for dashboard, sync, sessions, and agent chat.
2. A new deployment and runtime model.
3. More UI state handling across client and server boundaries.
4. More work than the current problem justifies.

At this stage, the simpler and better decision is to improve the structure of the current UI rather than replace the stack.

---

## Design Principles For The Refactor

1. **Separate concerns by page, not by tab.**
2. **Keep operational tasks away from the main analytical workspace.**
3. **Preserve backend boundaries.** UI changes should not introduce cross-layer coupling.
4. **Prefer thin wrappers over deep rewrites.**
5. **Leave room for future pages without reopening the main app architecture.**

---

## Expected Benefits

1. Better use of limited screen space.
2. Cleaner mental model for users.
3. Easier extension path for future UI areas.
4. Lower implementation risk than a framework migration.
5. No disruption to the existing sync, analysis, or agent orchestration layers.

---

## Scope Boundaries

Included in this plan:

- Multipage Streamlit navigation
- Sidebar simplification
- Settings page for operational controls
- Coach page session-management relocation
- Placeholder History page for future growth

Not included in this plan:

- Frontend framework migration
- New REST or WebSocket API layer
- Changes to analysis algorithms
- Changes to agent routing or tool behavior
- Data model changes unrelated to UI needs

---

## Related

- [technical_reference.md](../technical_reference.md)
- [001_mark-ii_local-workout-cache-sync_20260325.md](../implementation-plan/001_mark-ii_local-workout-cache-sync_20260325.md)
