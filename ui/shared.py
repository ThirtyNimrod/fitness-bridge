import threading
import time
import json

import streamlit as st

from src.clients.fitbit_client import FitbitClient
from src.clients.strava_client import StravaClient
from src.sync.engine import SyncEngine
from src.utils.logger import app_logger

_sync_lock = threading.Lock()


def run_sync_with_lock(force: bool = False):
    with _sync_lock:
        return SyncEngine().sync(force=force)


def _background_sync_loop():
    while True:
        time.sleep(2 * 60 * 60)
        try:
            run_sync_with_lock(force=False)
        except Exception as exc:
            app_logger.warning(f"Background sync failed: {exc}")


@st.cache_resource
def start_background_sync():
    thread = threading.Thread(target=_background_sync_loop, daemon=True)
    thread.start()
    return True


@st.cache_resource
def run_startup_sync():
    try:
        result = run_sync_with_lock(force=False)
        app_logger.info(f"Startup sync: {result['synced']} new workouts")
    except Exception as exc:
        app_logger.warning(f"Startup sync failed: {exc}")
    return True


@st.cache_data(ttl=120)
def get_connection_statuses():
    statuses = {
        "strava": {"connected": False, "error": None},
        "fitbit": {"connected": False, "error": None},
    }

    try:
        statuses["strava"]["connected"] = StravaClient().check_connection()
    except Exception as exc:
        statuses["strava"]["error"] = str(exc)[:80]

    try:
        statuses["fitbit"]["connected"] = FitbitClient().check_connection()
    except Exception as exc:
        statuses["fitbit"]["error"] = str(exc)[:80]

    return statuses


def format_set(set_data: dict) -> str:
    if set_data.get("type") == "duration":
        return f"Set {set_data.get('set_number')}: {set_data.get('duration_str')}"
    if set_data.get("type") == "weighted":
        tag = f" [{set_data['tag']}]" if set_data.get("tag") else ""
        return f"Set {set_data.get('set_number')}: {set_data.get('weight_kg')} kg x {set_data.get('reps')}{tag}"
    if set_data.get("type") == "bodyweight":
        tag = f" [{set_data['tag']}]" if set_data.get("tag") else ""
        return f"Set {set_data.get('set_number')}: {set_data.get('reps')} reps{tag}"
    return f"Set {set_data.get('set_number')}"


def parse_json_list(raw_value: str | None) -> list:
    if not raw_value:
        return []
    try:
        data = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []