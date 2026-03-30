import streamlit as st

from src.utils.database import get_last_synced
from ui.shared import get_connection_statuses


def _status_label(name: str, connected: bool) -> str:
    icon = "🟢" if connected else "🔴"
    return f"{icon} {name}"


def render_sidebar():
    statuses = get_connection_statuses()
    last_sync = get_last_synced("strava")

    with st.sidebar:
        st.header("Fitness Bridge")
        st.caption("Status")
        st.write(_status_label("Strava", statuses["strava"]["connected"]))
        st.write(_status_label("Fitbit", statuses["fitbit"]["connected"]))
        st.divider()

        if last_sync:
            st.caption(f"Last synced: {last_sync.strftime('%d %b %Y, %H:%M')}")
        else:
            st.caption("Never synced")

        st.caption("Open Settings for connection details and sync controls.")