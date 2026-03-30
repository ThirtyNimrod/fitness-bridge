import streamlit as st
import os
import sys
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != base_dir:
    os.chdir(base_dir)
sys.path.insert(0, base_dir)

load_dotenv()

from src.utils.database import create_session, init_db
from ui.components.sidebar import render_sidebar
from ui.shared import run_startup_sync, start_background_sync

init_db()

run_startup_sync()
start_background_sync()

st.set_page_config(page_title="Fitness Bridge AI", layout="wide", page_icon="🏋️")

if "session_id" not in st.session_state:
    st.session_state.session_id = create_session("Initial Session")

render_sidebar()

navigation = st.navigation(
    [
        st.Page("ui/pages/dashboard.py", title="Dashboard", icon="📊", default=True),
        st.Page("ui/pages/coach.py", title="AI Coach", icon="💬"),
        st.Page("ui/pages/history.py", title="History", icon="📋"),
        st.Page("ui/pages/settings.py", title="Settings", icon="⚙️"),
        st.Page("ui/pages/diagnostics.py", title="Diagnostics", icon="🩺"),
    ]
)

navigation.run()

