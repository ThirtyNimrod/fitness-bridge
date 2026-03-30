import streamlit as st

from src.agents.router import get_routing_metrics, reset_routing_metrics
from src.utils.database import get_last_synced


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _render_routing_metrics():
    st.subheader("Router Metrics")
    metrics = get_routing_metrics()
    total = int(metrics.get("total_routed", 0) or 0)
    heuristic_hits = int(metrics.get("heuristic_hits", 0) or 0)
    llm_fallbacks = int(metrics.get("llm_fallbacks", 0) or 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        with st.container(border=True):
            st.metric("Total Routed", total)
    with col2:
        with st.container(border=True):
            st.metric("Heuristic Hits", heuristic_hits)
    with col3:
        with st.container(border=True):
            st.metric("LLM Fallbacks", llm_fallbacks)
    with col4:
        with st.container(border=True):
            st.metric("Heuristic Rate", f"{_safe_rate(heuristic_hits, total)}%")

    if st.button("Reset Router Metrics", use_container_width=True):
        reset_routing_metrics()
        st.success("Router metrics reset.")
        st.rerun()


def _render_sync_health():
    st.subheader("Sync Health")
    col1, col2 = st.columns(2)

    strava_last = get_last_synced("strava")
    fitbit_last = get_last_synced("fitbit")

    with col1:
        with st.container(border=True):
            st.metric("Strava Last Sync", strava_last.strftime("%d %b %Y, %H:%M") if strava_last else "Never")
    with col2:
        with st.container(border=True):
            st.metric("Fitbit Last Sync", fitbit_last.strftime("%d %b %Y, %H:%M") if fitbit_last else "Never")


st.header("Diagnostics")
st.caption("Runtime visibility for routing behavior and sync freshness.")
_render_routing_metrics()
st.divider()
_render_sync_health()