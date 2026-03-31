import streamlit as st
import json
from datetime import date, timedelta

import pandas as pd

from src.analysis.dataset import build_dataset
from src.analysis.strength import compute_muscle_group_volume
from src.utils.cache import get_cache
from src.analysis.load import compute_weekly_load, compute_acwr
from src.agents.tools.readiness_tools import get_todays_readiness
from ui.shared import format_set, parse_json_list

_TIME_RANGE_OPTIONS = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}


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
    source = last.get("source", "strava")
    source_badge = "🔵 Fitbit" if source == "fitbit" else "🟠 Strava"

    with st.container(border=True):
        st.markdown(f"### {last['workout_title']}")
        st.caption(f"{last['date']} · {source_badge}")

        volume = float(last.get('total_volume_kg', 0) or 0)
        calories = last.get("calories")

        if volume > 0:
            st.metric("Volume", f"{volume:,.0f} kg")
        elif calories:
            st.metric("Calories", f"{float(calories):,.0f}")

        if int(last.get("set_count", 0) or 0) > 0:
            st.metric("Sets", int(last.get("set_count", 0) or 0))
        if int(last.get("exercise_count", 0) or 0) > 0:
            st.metric("Exercises", int(last.get("exercise_count", 0) or 0))
        if last.get("duration_min") is not None:
            st.metric("Duration", f"{float(last.get('duration_min', 0)):.0f} min")

        distance = last.get("distance_km")
        if distance and float(distance) > 0:
            st.metric("Distance", f"{float(distance):.1f} km")

        if last.get("readiness_label"):
            st.info(f"Readiness: {last['readiness_label']}")

        flags = []
        if last.get("has_drop_sets"):
            flags.append("Drop sets")
        if last.get("has_failure_sets"):
            flags.append("Failure sets")
        if flags:
            st.caption("Techniques: " + " · ".join(flags))


def _render_calendar_heatmap(df: pd.DataFrame, days: int):
    """Render a calendar-style heatmap of workout days."""
    if df.empty:
        return

    with st.container(border=True):
        st.subheader("Workout Calendar")

        today = date.today()
        start = today - timedelta(days=days - 1)
        all_dates = pd.date_range(start=start, end=today, freq="D")
        workout_dates = set(pd.to_datetime(df["date"]).dt.date)

        # Build a simple grid: rows = weeks, cols = days (Mon-Sun)
        weeks: list[list[tuple[date, bool]]] = []
        current_week: list[tuple[date, bool]] = []
        for d in all_dates:
            day = d.date()
            if day.weekday() == 0 and current_week:
                weeks.append(current_week)
                current_week = []
            current_week.append((day, day in workout_dates))
        if current_week:
            weeks.append(current_week)

        # Render last 6 weeks max for readability
        display_weeks = weeks[-6:]
        for week in display_weeks:
            cols = st.columns(7)
            for i, col in enumerate(cols):
                if i < len(week):
                    day, has_workout = week[i]
                    if has_workout:
                        col.markdown(f"**:green[{day.day}]**")
                    else:
                        col.caption(str(day.day))
                else:
                    col.write("")

        active_days = len(workout_dates.intersection(d.date() for d in all_dates))
        st.caption(f"{active_days} active days in the last {days} days")


def _render_hr_zone_chart(df: pd.DataFrame):
    """Render aggregate HR zone time chart from Fitbit activities."""
    zone_totals: dict[str, int] = {}
    for _, row in df.iterrows():
        zones = parse_json_list(row.get("hr_zones"))
        for zone in zones:
            name = zone.get("name", "")
            minutes = int(zone.get("minutes", 0) or 0)
            if name and minutes > 0:
                zone_totals[name] = zone_totals.get(name, 0) + minutes

    if not zone_totals:
        return

    with st.container(border=True):
        st.subheader("Heart Rate Zones")
        zone_df = pd.DataFrame(
            {"Zone": list(zone_totals.keys()), "Minutes": list(zone_totals.values())}
        ).set_index("Zone")
        st.bar_chart(zone_df)


def _render_calorie_chart(df: pd.DataFrame):
    """Render a calorie burn trend chart."""
    cal_df = df[["date", "calories"]].dropna()
    if cal_df.empty:
        return

    cal_df = cal_df.copy()
    cal_df["calories"] = pd.to_numeric(cal_df["calories"], errors="coerce")
    cal_df = cal_df.dropna()
    if cal_df.empty:
        return

    with st.container(border=True):
        st.subheader("Calorie Burn")
        st.bar_chart(cal_df.set_index("date")["calories"])


def _render_muscle_volume_chart(df: pd.DataFrame):
    """Render a muscle group volume breakdown chart."""
    volumes = compute_muscle_group_volume(df)
    # Filter out empty/other
    volumes = {k: v for k, v in volumes.items() if v > 0 and k != "other"}
    if not volumes:
        return

    with st.container(border=True):
        st.subheader("Volume by Muscle Group")
        vol_df = pd.DataFrame(
            {"Muscle Group": list(volumes.keys()), "Volume (kg)": list(volumes.values())}
        ).set_index("Muscle Group").sort_values("Volume (kg)", ascending=False)
        st.bar_chart(vol_df)


def render_dashboard():
    st.header("Your Training Overview")

    # Time range toggle
    range_cols = st.columns(len(_TIME_RANGE_OPTIONS) + 1)
    with range_cols[0]:
        st.caption("Period:")
    selected_range = "30d"
    for i, label in enumerate(_TIME_RANGE_OPTIONS):
        with range_cols[i + 1]:
            if st.button(label, use_container_width=True, type="primary" if label == st.session_state.get("dash_range", "30d") else "secondary"):
                st.session_state["dash_range"] = label
                st.rerun()

    selected_range = st.session_state.get("dash_range", "30d")
    days = _TIME_RANGE_OPTIONS[selected_range]

    df = _get_dashboard_dataset(days=days)

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

    # Row 2: Calendar heatmap
    _render_calendar_heatmap(df, days)

    st.divider()

    # Row 3: Charts (2x2 grid)
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
                chart_df = df.copy()
                chart_df["iso_week"] = pd.to_datetime(chart_df["date"]).dt.strftime('%G-W%V')
                weekly_df = chart_df.groupby("iso_week")["total_volume_kg"].sum()
                st.bar_chart(weekly_df)
            else:
                st.write("No volume data to chart.")

    # Row 4: Muscle volume + HR zones / calories
    col_left2, col_right2 = st.columns(2)
    with col_left2:
        _render_muscle_volume_chart(df)

    with col_right2:
        _render_hr_zone_chart(df)

    # Calorie chart (full width)
    if "calories" in df.columns:
        _render_calorie_chart(df)

    st.divider()

    # Row 5: Last workout detail
    st.subheader("Last Workout")
    df_sorted = df.sort_values(by="date", ascending=False)
    last = df_sorted.iloc[0]
    col_exercises, col_summary = st.columns([6, 4])

    with col_exercises:
        source = last.get("source", "strava")
        source_badge = "🔵 Fitbit" if source == "fitbit" else "🟠 Strava"
        st.write(f"**{last['workout_title']}** — {last['date']} {source_badge}")

        volume = float(last.get('total_volume_kg', 0) or 0)
        exercise_count = int(last.get('exercise_count', 0) or 0)
        set_count = int(last.get('set_count', 0) or 0)

        if exercise_count > 0:
            st.write(f"{exercise_count} exercises · {set_count} sets · {volume:,.0f} kg total")
        else:
            # Fitbit non-exercise workout
            duration = float(last.get('duration_min', 0) or 0)
            calories = last.get("calories")
            parts = [f"{duration:.0f} min"]
            if calories:
                parts.append(f"{float(calories):,.0f} cal")
            st.write(" · ".join(parts))

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
