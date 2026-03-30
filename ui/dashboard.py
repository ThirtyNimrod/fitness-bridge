import streamlit as st
import json
from src.analysis.dataset import build_dataset
from src.utils.cache import get_cache
from src.analysis.load import compute_weekly_load, compute_acwr
from src.agents.tools.readiness_tools import get_todays_readiness
from ui.shared import format_set


@st.cache_data(ttl=60)
def _get_dashboard_dataset(days: int):
    return build_dataset(n_days=days)


@st.cache_data(ttl=60)
def _get_todays_readiness_payload():
    return json.loads(get_todays_readiness.invoke({}))


def _acwr_delta_color(zone: str) -> str:
    if zone == "optimal":
        return "normal"
    if zone == "overreach_risk":
        return "inverse"
    return "off"


def _render_metric_card(label: str, value, delta=None, delta_color: str = "normal"):
    with st.container(border=True):
        st.metric(label, value, delta, delta_color=delta_color)


def _render_last_workout_summary(last):
    with st.container(border=True):
        st.markdown(f"### {last['workout_title']}")
        st.caption(last["date"])
        st.metric("Volume", f"{last.get('total_volume_kg', 0):,.0f} kg")
        st.metric("Sets", int(last.get("set_count", 0) or 0))
        st.metric("Exercises", int(last.get("exercise_count", 0) or 0))
        if last.get("duration_min") is not None:
            st.metric("Duration", f"{last.get('duration_min', 0):.0f} min")
        if last.get("readiness_label"):
            st.info(f"Readiness: {last['readiness_label']}")
        flags = []
        if last.get("has_drop_sets"):
            flags.append("Drop sets")
        if last.get("has_failure_sets"):
            flags.append("Failure sets")
        if flags:
            st.caption("Techniques: " + " · ".join(flags))

def render_dashboard():
    st.header("Your Training Overview")

    df = _get_dashboard_dataset(days=28)

    if df.empty:
        st.info("No workout data found. Connect your Strava account and ensure you have recent activities.")
        if st.button("Clear Cache"):
            get_cache().clear()
            st.rerun()
        return

    # Row 1: Key metrics
    col1, col2, col3, col4 = st.columns(4)
    weekly = compute_weekly_load(df)
    
    with col1:
        try:
            today_readiness = _get_todays_readiness_payload()
            if "score" in today_readiness:
                _render_metric_card("⚡ Today's Readiness", today_readiness["score"], today_readiness["label"])
            else:
                _render_metric_card("⚡ Today's Readiness", "N/A", "Data unavailable", delta_color="off")
        except Exception:
            _render_metric_card("⚡ Today's Readiness", "Error", "Exception", delta_color="off")
            
    with col2:
        _render_metric_card("🏋️ This Week's Volume", f"{weekly['total_volume_kg']:,.0f} kg")
        
    with col3:
        acwr = compute_acwr(df)
        if acwr:
            _render_metric_card("📊 ACWR", acwr["ratio"], acwr["zone"], delta_color=_acwr_delta_color(acwr["zone"]))
        else:
            _render_metric_card("📊 ACWR", "N/A", "Not enough history", delta_color="off")

    with col4:
        _render_metric_card("🗓️ Sessions This Week", weekly["session_count"])

    st.divider()

    # Row 2: Charts
    col_left, col_right = st.columns(2)
    with col_left:
        with st.container(border=True):
            st.subheader("Readiness — last 7 days")
            readiness_df = df[["date", "readiness_score"]].dropna().tail(7)
            if not readiness_df.empty:
                st.line_chart(readiness_df.set_index("date"))
            else:
                st.write("No readiness data recorded.")

    with col_right:
        with st.container(border=True):
            st.subheader("Weekly volume")
            if not df.empty:
                import pandas as pd
                chart_df = df.copy()
                chart_df["iso_week"] = pd.to_datetime(chart_df["date"]).dt.strftime('%G-W%V')
                weekly_df = chart_df.groupby("iso_week")["total_volume_kg"].sum()
                st.bar_chart(weekly_df)
            else:
                st.write("No volume data to chart.")

    st.divider()
    st.write("")

    # Row 3: Last workout detail
    st.subheader("Last Workout")
    df_sorted = df.sort_values(by="date", ascending=False)
    last = df_sorted.iloc[0]
    col_exercises, col_summary = st.columns([6, 4])

    with col_exercises:
        st.write(f"**{last['workout_title']}** — {last['date']}")
        st.write(f"{last.get('exercise_count', 0)} exercises · {last.get('set_count', 0)} sets · {last.get('total_volume_kg', 0):,.0f} kg total")

        try:
            exercises = json.loads(last.get('exercises_raw', '[]'))
            for ex in exercises:
                with st.expander(f"{ex['name']} ({ex.get('muscle_group', 'other')})"):
                    for set_data in ex.get("sets", []):
                        st.write(format_set(set_data))
        except Exception:
            st.write("Error parsing exercises JSON.")

    with col_summary:
        _render_last_workout_summary(last)
