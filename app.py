import streamlit as st
import os
import sys
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != base_dir:
    os.chdir(base_dir)
sys.path.insert(0, base_dir)

load_dotenv()

from src.utils.database import init_db, create_session, get_sessions
from src.clients.strava_client import StravaClient
from src.clients.fitbit_client import FitbitClient
from ui.dashboard import render_dashboard
from ui.chat import render_chat

init_db()

st.set_page_config(title="Fitness Bridge AI", layout="wide", page_icon="🏋️")

# Sidebar
with st.sidebar:
    st.header("Connections")
    
    try:
        strava = StravaClient()
        if strava.check_connection():
            st.success("✅ Strava Connected")
        else:
            st.error("❌ Strava Not Connected")
    except Exception as e:
        st.error(f"❌ Strava Error: {str(e)[:50]}")
        
    try:
        fitbit = FitbitClient()
        if fitbit.check_connection():
            st.success("✅ Fitbit Connected")
        else:
            st.error("❌ Fitbit Not Connected")
    except Exception as e:
        st.error(f"❌ Fitbit Error: {str(e)[:50]}")

    st.divider()

    st.header("Sessions")
    if st.button("+ New Chat", use_container_width=True):
        st.session_state.session_id = create_session("New Session")
        st.rerun()

    sessions = get_sessions()
    if sessions:
        # Create a lookup dictionary
        session_dict = {s["id"]: s["title"] for s in sessions}
        selected_id = st.selectbox(
            "Past chats", 
            options=list(session_dict.keys()), 
            format_func=lambda x: session_dict[x],
            index=0 if "session_id" not in st.session_state else list(session_dict.keys()).index(st.session_state.session_id) if st.session_state.session_id in session_dict else 0
        )
        st.session_state.session_id = selected_id
    else:
        st.write("No prior chats.")
        if "session_id" not in st.session_state:
            st.session_state.session_id = create_session("Initial Session")

# Main Area
tab_dash, tab_chat = st.tabs(["📊 Dashboard", "💬 AI Coach"])

with tab_dash:
    render_dashboard()

with tab_chat:
    if "session_id" in st.session_state:
        render_chat(st.session_state.session_id)
    else:
        st.error("No active session.")
