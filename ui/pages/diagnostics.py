import streamlit as st

from src.agents.router import get_routing_metrics, reset_routing_metrics
from src.utils.database import get_last_synced
from src.clients.strava_client import get_strava_quota, STRAVA_15MIN_LIMIT, STRAVA_DAILY_LIMIT


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
    col1, col2, col3 = st.columns(3)

    strava_last = get_last_synced("strava")
    fitbit_last = get_last_synced("fitbit")
    fitbit_act_last = get_last_synced("fitbit_activities")

    with col1:
        with st.container(border=True):
            st.metric("Strava Last Sync", strava_last.strftime("%d %b %Y, %H:%M") if strava_last else "Never")
    with col2:
        with st.container(border=True):
            st.metric("Fitbit Last Sync", fitbit_last.strftime("%d %b %Y, %H:%M") if fitbit_last else "Never")
    with col3:
        with st.container(border=True):
            st.metric("Fitbit Activities", fitbit_act_last.strftime("%d %b %Y, %H:%M") if fitbit_act_last else "Never")


def _render_api_quota():
    st.subheader("Strava API Quota")
    quota = get_strava_quota()
    col1, col2 = st.columns(2)
    with col1:
        count_15 = int(quota.get("15min_count", 0) or 0)
        with st.container(border=True):
            st.metric("15-min Window", f"{count_15} / {STRAVA_15MIN_LIMIT}")
            if count_15 >= STRAVA_15MIN_LIMIT * 0.8:
                st.warning("Approaching 15-min rate limit")
    with col2:
        count_daily = int(quota.get("daily_count", 0) or 0)
        with st.container(border=True):
            st.metric("Daily", f"{count_daily} / {STRAVA_DAILY_LIMIT}")
            if count_daily >= STRAVA_DAILY_LIMIT * 0.8:
                st.warning("Approaching daily rate limit")


st.header("Diagnostics")
st.caption("Runtime visibility for routing behavior, sync freshness, and API quotas.")
_render_routing_metrics()
st.divider()
_render_sync_health()
st.divider()
_render_api_quota()