import streamlit as st

from config import CACHE_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL
from src.utils.cache import get_cache
from src.utils.database import get_last_synced
from src.utils.logger import app_logger, ui_logger
from ui.shared import get_connection_statuses, run_sync_with_lock


def _render_connection_status(statuses):
    st.subheader("Connections")

    for name in ("strava", "fitbit"):
        status = statuses[name]
        label = name.capitalize()
        if status["error"]:
            ui_logger.error(f"{label} Error: {status['error']}")
            st.error(f"{label}: {status['error']}")
        elif status["connected"]:
            ui_logger.info(f"{label} connected successfully")
            st.success(f"{label}: Connected")
        else:
            ui_logger.warning(f"{label} not connected")
            st.warning(f"{label}: Not connected")


def _render_sync_controls():
    st.subheader("Sync")
    last_sync = get_last_synced("strava")

    if st.button("Sync Workouts", use_container_width=True):
        with st.spinner("Syncing workouts..."):
            try:
                result = run_sync_with_lock(force=True)
                get_connection_statuses.clear()
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
statuses = get_connection_statuses()
_render_connection_status(statuses)
st.divider()
_render_sync_controls()
st.divider()
_render_configuration()