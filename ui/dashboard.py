import streamlit as st
import json
from datetime import date
from src.analysis.dataset import build_dataset
from src.utils.cache import get_cache
from src.analysis.load import compute_weekly_load, compute_acwr
from src.agents.tools.readiness_tools import get_todays_readiness


@st.cache_data(ttl=60)
def _get_dashboard_dataset(days: int):
    return build_dataset(n_days=days)


@st.cache_data(ttl=60)
def _get_todays_readiness_payload():
    return json.loads(get_todays_readiness.invoke({}))

def format_set(s):
    if s.get("type") == "duration":
        return f"Set {s.get('set_number')}: {s.get('duration_str')}"
    elif s.get("type") == "weighted":
        tag = f" [{s['tag']}]" if s.get("tag") else ""
        return f"Set {s.get('set_number')}: {s.get('weight_kg')} kg x {s.get('reps')}{tag}"
    elif s.get("type") == "bodyweight":
        tag = f" [{s['tag']}]" if s.get("tag") else ""
        return f"Set {s.get('set_number')}: {s.get('reps')} reps{tag}"
    return f"Set {s.get('set_number')}"

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
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            today_readiness = _get_todays_readiness_payload()
            if "score" in today_readiness:
                st.metric("Today's Readiness", today_readiness["score"], today_readiness["label"])
            else:
                st.metric("Today's Readiness", "N/A", "Data unavailable")
        except Exception:
            st.metric("Today's Readiness", "Error", "Exception")
            
    with col2:
        weekly = compute_weekly_load(df)
        st.metric("This Week's Volume", f"{weekly['total_volume_kg']:,.0f} kg")
        
    with col3:
        acwr = compute_acwr(df)
        if acwr:
            st.metric("ACWR", acwr["ratio"], acwr["zone"])
        else:
            st.metric("ACWR", "N/A", "Not enough history")

    st.divider()

    # Row 2: Charts
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Readiness — last 7 days")
        readiness_df = df[["date", "readiness_score"]].dropna().tail(7)
        if not readiness_df.empty:
            st.line_chart(readiness_df.set_index("date"))
        else:
            st.write("No readiness data recorded.")

    with col_right:
        st.subheader("Weekly volume")
        if not df.empty:
            import pandas as pd
            df['iso_week'] = pd.to_datetime(df['date']).dt.strftime('%G-W%V')
            weekly_df = df.groupby('iso_week')['total_volume_kg'].sum()
            st.bar_chart(weekly_df)
        else:
            st.write("No volume data to chart.")

    st.divider()

    # Row 3: Last workout detail
    st.subheader("Last Workout")
    df_sorted = df.sort_values(by="date", ascending=False)
    last = df_sorted.iloc[0]
    
    st.write(f"**{last['workout_title']}** — {last['date']}")
    st.write(f"{last.get('exercise_count', 0)} exercises · {last.get('set_count', 0)} sets · {last.get('total_volume_kg', 0):,.0f} kg total")

    try:
        exercises = json.loads(last.get('exercises_raw', '[]'))
        for ex in exercises:
            with st.expander(f"{ex['name']} ({ex.get('muscle_group', 'other')})"):
                for s in ex.get("sets", []):
                    st.write(format_set(s))
    except Exception:
        st.write("Error parsing exercises JSON.")
