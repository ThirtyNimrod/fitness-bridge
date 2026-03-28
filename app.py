import streamlit as st
import os
import sys
import threading
import time
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != base_dir:
    os.chdir(base_dir)
sys.path.insert(0, base_dir)

load_dotenv()

from src.utils.database import init_db, create_session, get_sessions, get_last_synced
from src.utils.logger import ui_logger, app_logger
from src.clients.strava_client import StravaClient
from src.clients.fitbit_client import FitbitClient
from src.sync.engine import SyncEngine
from ui.dashboard import render_dashboard
from ui.chat import render_chat

init_db()

# ── Background 2-hour auto-sync ───────────────────────────────────────────────
def _background_sync_loop():
    while True:
        time.sleep(2 * 60 * 60)   # 2 hours
        try:
            SyncEngine().sync()
        except Exception as e:
            app_logger.warning(f"Background sync failed: {e}")

@st.cache_resource
def start_background_sync():
    t = threading.Thread(target=_background_sync_loop, daemon=True)
    t.start()
    return True

# ── Startup sync (once per Streamlit process) ─────────────────────────────────
@st.cache_resource
def run_startup_sync():
    try:
        result = SyncEngine().sync()
        app_logger.info(f"Startup sync: {result['synced']} new workouts")
    except Exception as e:
        app_logger.warning(f"Startup sync failed: {e}")
    return True

run_startup_sync()
start_background_sync()


@st.cache_data(ttl=120)
def get_connection_statuses():
    statuses = {
        "strava": {"connected": False, "error": None},
        "fitbit": {"connected": False, "error": None},
    }

    try:
        statuses["strava"]["connected"] = StravaClient().check_connection()
    except Exception as e:
        statuses["strava"]["error"] = str(e)[:80]

    try:
        statuses["fitbit"]["connected"] = FitbitClient().check_connection()
    except Exception as e:
        statuses["fitbit"]["error"] = str(e)[:80]

    return statuses

st.set_page_config(page_title="Fitness Bridge AI", layout="wide", page_icon="🏋️")

# Sidebar
with st.sidebar:
    st.header("Connections")

    statuses = get_connection_statuses()

    if statuses["strava"]["error"]:
        ui_logger.error(f"Strava Error: {statuses['strava']['error']}")
        st.error(f"❌ Strava Error: {statuses['strava']['error']}")
    elif statuses["strava"]["connected"]:
        ui_logger.info("Strava Connected successfully")
        st.success("✅ Strava Connected")
    else:
        ui_logger.warning("Strava Not Connected")
        st.error("❌ Strava Not Connected")

    if statuses["fitbit"]["error"]:
        ui_logger.error(f"Fitbit Error: {statuses['fitbit']['error']}")
        st.error(f"❌ Fitbit Error: {statuses['fitbit']['error']}")
    elif statuses["fitbit"]["connected"]:
        ui_logger.info("Fitbit Connected successfully")
        st.success("✅ Fitbit Connected")
    else:
        ui_logger.warning("Fitbit Not Connected")
        st.error("❌ Fitbit Not Connected")

    st.divider()

    # Sync controls
    last_sync = get_last_synced("strava")
    if st.button("🔄 Sync Workouts", use_container_width=True):
        with st.spinner("Syncing..."):
            try:
                result = SyncEngine().sync(force=True)
                get_connection_statuses.clear()
                st.success(f"Synced {result['synced']} workouts.")
                st.rerun()
            except Exception as e:
                app_logger.warning(f"Manual sync failed: {e}")
                st.warning("Sync failed — showing last cached data.")

    if last_sync:
        st.caption(f"Last synced: {last_sync.strftime('%d %b %Y, %H:%M')}")
    else:
        st.caption("Never synced — click Sync Workouts.")

    st.divider()

    st.header("Sessions")
    if st.button("+ New Chat", use_container_width=True):
        st.session_state.session_id = create_session("New Session")
        ui_logger.info(f"Created new chat session: {st.session_state.session_id}")
        st.rerun()

    sessions = get_sessions()
    if sessions:
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
            ui_logger.info(f"Created initial chat session: {st.session_state.session_id}")

# Main Area
tab_dash, tab_chat = st.tabs(["📊 Dashboard", "💬 AI Coach"])

with tab_dash:
    render_dashboard()

with tab_chat:
    if "session_id" in st.session_state:
        render_chat(st.session_state.session_id)
    else:
        st.error("No active session.")

