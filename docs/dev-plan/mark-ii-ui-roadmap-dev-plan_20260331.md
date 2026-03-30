# Mark II UI Roadmap Development Plan

**Date:** 2026-03-31  
**Status:** Proposed  
**Scope:** Post-multipage UI roadmap covering visual refinement, workout history, and UI testing

---

## Problem Statement

The multipage refactor fixed the core layout pressure, but the UI is still early-stage in three important areas:

1. The Dashboard and AI Coach pages are structurally clearer but still visually plain.
2. The History page exists only as a placeholder and does not yet expose the cached workout data in a browsable form.
3. The app has strong backend and agent test coverage, but the new page-level UI behavior is not yet locked down by tests.

---

## Goal

> Turn the new multipage layout into a more complete product surface by improving presentation first, then adding workout browsing, then adding page-level UI tests.

This roadmap keeps the existing Streamlit direction intact and focuses on finishing the UI in a disciplined sequence rather than broadening scope.

---

## Roadmap Sequence

The next UI work should be sequenced as follows:

1. **Visual refinement** for Dashboard and Coach
2. **Real History page** with filtering, search, and pagination
3. **Phase08 UI test layer** for the new page behavior

This order keeps the test work aligned with the final UI surface and avoids rewriting tests during the visual and information-architecture changes.

---

## Why This Order

### 1. Visual refinement comes first

The multipage split created the space needed for better design. The next practical step is to improve clarity and hierarchy on the pages users see most often:

- training metrics need more visual weight
- charts need better framing
- the last workout section can use space more intentionally
- coach session controls can be simplified and made more readable

### 2. History comes second

The History page is a clear product capability gap, but it should build on a stable page model and shared UI helpers. Once the core page styling direction is settled, workout browsing can follow without guessing at patterns.

### 3. UI tests come third

Tests should lock in the evolved UI rather than the temporary intermediate state. Adding page-level tests after the visible behavior is in place reduces churn and gives better long-term value.

---

## Target Outcomes

### Dashboard and Coach
- clearer metric hierarchy
- better use of full-width layout
- more intentional summary/detail balance
- simpler session controls and stronger chat context

### History
- date-aware workout browsing
- search by title
- filtering by muscle groups and training characteristics
- pagination for longer workout lists

### UI Test Layer
- repeatable page rendering checks
- regression coverage for session switching and settings actions
- a stable base for future UI additions

---

## Design Principles

1. **Keep the UI Python-first.** No new frontend stack or API layer.
2. **Preserve module boundaries.** Existing render modules and backend analysis contracts stay intact unless a concrete reason appears to split them.
3. **Prefer shared helpers over cross-page imports.** Reusable formatting and status helpers should live in shared UI modules.
4. **Test the user-facing surface after it stabilizes.** UI tests should validate the page contracts users actually depend on.
5. **Add product capability without reintroducing layout sprawl.** Each new page should deepen one concern, not recreate the old single-screen overload.

---

## Scope Boundaries

Included in this roadmap:

- dashboard visual improvements
- coach page control/layout improvements
- real workout History page
- page-level UI tests using built-in Streamlit support

Not included in this roadmap:

- replacing Streamlit
- redesigning the sync or analysis architecture
- changes to agent routing behavior
- public API creation for the UI

---

## Related

- [mark-ii-ui-multipage-dev-plan_20260331.md](mark-ii-ui-multipage-dev-plan_20260331.md)
- [technical_reference.md](../technical_reference.md)
- [002_mark-ii_streamlit_multipage_ui_20260331.md](../implementation-plan/002_mark-ii_streamlit_multipage_ui_20260331.md)
