import streamlit as st

from src.utils.database import get_last_synced
from ui.shared import get_token_statuses


def _status_pill(name: str, has_token: bool) -> str:
    css_class = "status-connected" if has_token else "status-disconnected"
    label = "Configured" if has_token else "Not configured"
    return f'<span class="status-pill {css_class}">{label}</span>'


def render_sidebar():
    token_statuses = get_token_statuses()
    last_sync = get_last_synced("strava")

    with st.sidebar:
        st.header("🏋️ Fitness Bridge")
        st.caption("Status")
        st.markdown(f"**Strava** {_status_pill('Strava', token_statuses['strava']['has_token'])}", unsafe_allow_html=True)
        st.markdown(f"**Fitbit** {_status_pill('Fitbit', token_statuses['fitbit']['has_token'])}", unsafe_allow_html=True)
        st.divider()

        if last_sync:
            st.caption(f"Last synced: {last_sync.strftime('%d %b %Y, %H:%M')}")
        else:
            st.caption("Never synced")

        st.caption("Open Settings for sync controls and token health.")