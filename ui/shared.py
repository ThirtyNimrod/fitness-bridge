import threading
import time
import json
import os

import streamlit as st

from src.clients.fitbit_client import FitbitClient
from src.clients.strava_client import StravaClient
from src.sync.engine import SyncEngine
from src.utils.logger import app_logger
from config import BACKGROUND_SYNC_INTERVAL

_sync_lock = threading.Lock()


def run_sync_with_lock(force: bool = False):
    with _sync_lock:
        return SyncEngine().sync(force=force)


def _background_sync_loop():
    while True:
        time.sleep(BACKGROUND_SYNC_INTERVAL)
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


@st.cache_data(ttl=3600)
def get_token_statuses() -> dict:
    """
    Cheap, API-free status check — reads token presence from os.environ.
    Safe to call on every render / tab switch. Cached for 1 hour.
    'has_token' = True means a refresh token is stored (app can operate).
    """
    return {
        "strava": {"has_token": bool(os.getenv("STRAVA_REFRESH_TOKEN"))},
        "fitbit": {"has_token": bool(os.getenv("FITBIT_REFRESH_TOKEN"))},
    }


def get_connection_statuses() -> dict:
    """
    Live API ping — calls /athlete and /profile endpoints.
    DO NOT call this on a normal render cycle (every tab switch).
    Call it only from an explicit user action:
      - 'Test Connection' button in Settings
      - Immediately after a manual sync
    """
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