import streamlit as st
from datetime import datetime, timezone

from config import CACHE_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL, STRAVA_TOKEN_EXPIRES_AT, FITBIT_TOKEN_EXPIRES_AT
from src.utils.cache import get_cache
from src.utils.database import get_last_synced, get_all_facts, upsert_fact, delete_fact
from src.utils.logger import app_logger, ui_logger
from ui.shared import get_token_statuses, get_connection_statuses, run_sync_with_lock


def _render_connection_status():
    st.subheader("Connections")
    st.caption("Token presence check — no API call. Use **Test Live Connection** to verify the APIs are reachable.")

    token_statuses = get_token_statuses()

    col1, col2 = st.columns(2)
    with col1:
        if token_statuses["strava"]["has_token"]:
            st.success("🟠 Strava — refresh token present")
        else:
            st.error("🟠 Strava — no refresh token set")
    with col2:
        if token_statuses["fitbit"]["has_token"]:
            st.success("🔵 Fitbit — refresh token present")
        else:
            st.error("🔵 Fitbit — no refresh token set")

    # Live connection test — only fires when button is clicked
    if st.button("🔌 Test Live Connection", use_container_width=True):
        with st.spinner("Pinging Strava and Fitbit APIs..."):
            live = get_connection_statuses()
            st.session_state["live_connection_result"] = live

    if "live_connection_result" in st.session_state:
        live = st.session_state["live_connection_result"]
        for name in ("strava", "fitbit"):
            label = name.capitalize()
            status = live[name]
            if status["error"]:
                ui_logger.error(f"{label} Error: {status['error']}")
                st.error(f"{label}: {status['error']}")
            elif status["connected"]:
                ui_logger.info(f"{label} connected successfully")
                st.success(f"{label}: API reachable ✅")
            else:
                ui_logger.warning(f"{label} not connected")
                st.warning(f"{label}: API not reachable")


def _render_token_expiry():
    st.subheader("🔑 Token Expiry")
    st.caption(
        "Access tokens are short-lived (~6–8 hours for Strava, ~8 hours for Fitbit). "
        "The app refreshes them automatically using your saved **refresh token**. "
        "If you ever get persistent 401 errors, re-run `scripts\\GET_TOKENS.ps1` to obtain a fresh refresh token."
    )

    now = datetime.now(timezone.utc)
    for label, raw_ts in (("Strava", STRAVA_TOKEN_EXPIRES_AT), ("Fitbit", FITBIT_TOKEN_EXPIRES_AT)):
        if not raw_ts:
            st.warning(f"{label}: No token expiry recorded yet.")
            continue
        try:
            expires_at = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc)
            delta = expires_at - now
            total_mins = int(delta.total_seconds() / 60)
            expires_fmt = expires_at.strftime("%d %b %Y, %H:%M UTC")
            if delta.total_seconds() < 0:
                st.error(
                    f"**{label}** access token **expired** at {expires_fmt}. "
                    "The app will try to auto-refresh — if it keeps failing, re-run `GET_TOKENS.ps1`."
                )
            elif total_mins < 30:
                st.warning(f"**{label}** access token expires in **{total_mins} min** ({expires_fmt}). Auto-refresh will kick in soon.")
            else:
                hours, mins = divmod(total_mins, 60)
                st.success(f"**{label}** token valid for **{hours}h {mins}m** (expires {expires_fmt})")
        except (ValueError, TypeError, OSError):
            st.warning(f"{label}: Could not parse token expiry value `{raw_ts}`.")


def _render_sync_controls():
    st.subheader("Sync")
    last_sync = get_last_synced("strava")

    if st.button("Sync Workouts", use_container_width=True):
        with st.spinner("Syncing workouts..."):
            try:
                result = run_sync_with_lock(force=True)
                get_token_statuses.clear()
                st.cache_data.clear()
                st.success(f"Synced {result['synced']} workouts.")
                st.rerun()
            except Exception as exc:
                app_logger.warning(f"Manual sync failed: {exc}")
                st.warning("Sync failed — showing last cached data.")

    if last_sync:
        st.caption(f"Last synced: {last_sync.strftime('%d %b %Y, %H:%M')}")
    else:
        st.caption("Never synced — click Sync Workouts.")


def _render_fact_management():
    st.subheader("🧠 What the AI knows about you")
    st.caption("These facts are extracted from your conversations and used for personalised coaching.")

    facts = get_all_facts()

    if not facts:
        st.info("No facts stored yet. Chat with the AI Coach and it will learn about your goals, preferences, and training history.")
        return

    for key, value in facts.items():
        col_text, col_edit, col_del = st.columns([8, 1, 1])
        with col_text:
            st.text(f"{key}: {value}")
        with col_edit:
            if st.button("✏️", key=f"edit_{key}", help="Edit this fact"):
                st.session_state[f"editing_fact_{key}"] = True
        with col_del:
            if st.button("🗑️", key=f"del_{key}", help="Delete this fact"):
                delete_fact(key)
                ui_logger.info(f"Deleted fact: {key}")
                st.rerun()

        if st.session_state.get(f"editing_fact_{key}"):
            new_value = st.text_input(f"Edit '{key}'", value=value, key=f"edit_input_{key}")
            save_col, cancel_col = st.columns(2)
            with save_col:
                if st.button("Save", key=f"save_{key}", use_container_width=True):
                    if new_value.strip():
                        upsert_fact(key, new_value.strip())
                        ui_logger.info(f"Updated fact: {key} = {new_value.strip()}")
                    st.session_state[f"editing_fact_{key}"] = False
                    st.rerun()
            with cancel_col:
                if st.button("Cancel", key=f"cancel_{key}", use_container_width=True):
                    st.session_state[f"editing_fact_{key}"] = False
                    st.rerun()

    st.divider()

    with st.expander("➕ Add a fact manually"):
        new_key = st.text_input("Fact name (e.g. 'goal', 'injury')", max_chars=64, key="new_fact_key")
        new_val = st.text_input("Value", max_chars=200, key="new_fact_val")
        if st.button("Add Fact", use_container_width=True):
            if new_key.strip() and new_val.strip():
                upsert_fact(new_key.strip().lower(), new_val.strip())
                ui_logger.info(f"Added fact: {new_key.strip().lower()} = {new_val.strip()}")
                st.rerun()
            else:
                st.warning("Both name and value are required.")


def _render_configuration():
    st.subheader("Configuration")
    st.text_input("Ollama Base URL", value=OLLAMA_BASE_URL, disabled=True)
    st.text_input("Ollama Model", value=OLLAMA_MODEL, disabled=True)
    st.text_input("Cache Directory", value=CACHE_DIR, disabled=True)

    if st.button("Clear Cache", use_container_width=True):
        get_cache().clear()
        st.cache_data.clear()
        st.success("Local cache cleared.")
        st.rerun()


st.header("Settings")
_render_connection_status()
st.divider()
_render_token_expiry()
st.divider()
_render_sync_controls()
st.divider()
_render_fact_management()
st.divider()
_render_configuration()