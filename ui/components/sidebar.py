import streamlit as st

from src.utils.database import get_last_synced
from ui.shared import get_connection_statuses


def _status_pill(name: str, connected: bool) -> str:
    css_class = "status-connected" if connected else "status-disconnected"
    label = "Connected" if connected else "Not connected"
    return f'<span class="status-pill {css_class}">{label}</span>'


def render_sidebar():
    statuses = get_connection_statuses()
    last_sync = get_last_synced("strava")

    with st.sidebar:
        st.header("🏋️ Fitness Bridge")
        st.caption("Status")
        st.markdown(f"**Strava** {_status_pill('Strava', statuses['strava']['connected'])}", unsafe_allow_html=True)
        st.markdown(f"**Fitbit** {_status_pill('Fitbit', statuses['fitbit']['connected'])}", unsafe_allow_html=True)
        st.divider()

        if last_sync:
            st.caption(f"Last synced: {last_sync.strftime('%d %b %Y, %H:%M')}")
        else:
            st.caption("Never synced")

        st.caption("Open Settings for connection details and sync controls.")