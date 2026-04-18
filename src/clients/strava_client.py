from datetime import datetime, timedelta, timezone
import os
import threading

import requests
from tenacity import retry, wait_exponential, stop_after_attempt
from src.utils.cache import cached
from src.utils.logger import app_logger
from src.utils.database import get_api_token, upsert_api_token

from config import (
    STRAVA_ACCESS_TOKEN,
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_REFRESH_TOKEN,
    STRAVA_TOKEN_EXPIRES_AT,
)

# ── Strava API Quota Tracker ────────────────────────────────────────────────
# Strava limits: 100 requests / 15 min, 1000 / day
_quota_lock = threading.Lock()
_quota_state = {
    "15min_count": 0,
    "15min_window_start": None,
    "daily_count": 0,
    "daily_window_start": None,
}

STRAVA_15MIN_LIMIT = 100
STRAVA_DAILY_LIMIT = 1000


def _track_api_call():
    """Increment API call counters and log warnings near limits."""
    now = datetime.now(timezone.utc)
    with _quota_lock:
        # 15-min window
        if _quota_state["15min_window_start"] is None or (now - _quota_state["15min_window_start"]) > timedelta(minutes=15):
            _quota_state["15min_count"] = 0
            _quota_state["15min_window_start"] = now
        _quota_state["15min_count"] += 1

        # Daily window
        if _quota_state["daily_window_start"] is None or (now - _quota_state["daily_window_start"]) > timedelta(hours=24):
            _quota_state["daily_count"] = 0
            _quota_state["daily_window_start"] = now
        _quota_state["daily_count"] += 1

        if _quota_state["15min_count"] >= STRAVA_15MIN_LIMIT * 0.8:
            app_logger.warning(f"Strava quota: {_quota_state['15min_count']}/{STRAVA_15MIN_LIMIT} requests in 15-min window")
        if _quota_state["daily_count"] >= STRAVA_DAILY_LIMIT * 0.8:
            app_logger.warning(f"Strava quota: {_quota_state['daily_count']}/{STRAVA_DAILY_LIMIT} daily requests")


def get_strava_quota() -> dict:
    """Return current quota usage snapshot."""
    with _quota_lock:
        return dict(_quota_state)

class AuthError(Exception):
    pass

# Browser-like User Agent to avoid connection resets from Strava's infrastructure
STRAVA_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class StravaClient:
    def __init__(self):
        self.base_url = "https://www.strava.com/api/v3"
        self.client_id = STRAVA_CLIENT_ID
        self.client_secret = STRAVA_CLIENT_SECRET
        self.refresh_token = STRAVA_REFRESH_TOKEN
        self.access_token = None
        self.token_expires_at = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": STRAVA_USER_AGENT,
            "Accept": "application/json",
            "Connection": "close"
        })
        self._load_runtime_auth_state()
        self._ensure_access_token()

    def _get_runtime_value(self, key: str, fallback):
        env_val = os.getenv(key)
        if env_val is None:
            return fallback
        env_val = env_val.strip()
        return env_val if env_val else None

    def _load_runtime_auth_state(self):
        # 1. Try Database (The Vault)
        token_data = get_api_token("strava")
        if token_data and token_data.get("refresh_token"):
            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")
            self.token_expires_at = self._parse_expiry(token_data.get("expires_at"))
            app_logger.info("Strava tokens loaded from database vault")
            return

        # 2. Fallback to Environment (Initial setup)
        self.access_token = self._get_runtime_value("STRAVA_ACCESS_TOKEN", STRAVA_ACCESS_TOKEN)
        self.refresh_token = self._get_runtime_value("STRAVA_REFRESH_TOKEN", self.refresh_token)
        self.token_expires_at = self._parse_expiry(
            self._get_runtime_value("STRAVA_TOKEN_EXPIRES_AT", STRAVA_TOKEN_EXPIRES_AT)
        )
        if self.refresh_token:
            app_logger.info("Strava tokens loaded from environment (fallback)")

    def _parse_expiry(self, expiry_value):
        if not expiry_value:
            return None
        try:
            return datetime.fromtimestamp(int(expiry_value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    def _is_token_expired(self) -> bool:
        if not self.access_token:
            return True
        if not self.token_expires_at:
            return False
        # Refresh 2 minutes early to avoid edge-of-expiry request failures.
        return datetime.now(timezone.utc) >= (self.token_expires_at - timedelta(minutes=2))

    def _ensure_access_token(self):
        self._load_runtime_auth_state()
        if self._is_token_expired():
            self._refresh_access_token()

    def _refresh_access_token(self):
        url = "https://www.strava.com/oauth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        res = self.session.post(url, data=payload)
        if res.status_code == 200:
            data = res.json()
            self.access_token = data.get("access_token")
            self.token_expires_at = self._parse_expiry(data.get("expires_at"))
            if data.get("refresh_token"):
                self.refresh_token = data["refresh_token"]
            
            app_logger.info("Strava token refresh successful — updating vault")
            
            expires_timestamp = data.get("expires_at")
            upsert_api_token(
                "strava",
                self.access_token,
                self.refresh_token,
                int(expires_timestamp) if expires_timestamp else None
            )
        else:
            app_logger.error(f"Strava token refresh failed: {res.text}")
            raise AuthError(f"Strava token refresh failed: {res.text}")

    def _headers(self):
        self._ensure_access_token()
        return {"Authorization": f"Bearer {self.access_token}"}

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_activities(self, per_page=10, page=1):
        _track_api_call()
        url = f"{self.base_url}/athlete/activities"
        params = {"per_page": per_page, "page": page}
        res = self.session.get(url, headers=self._headers(), params=params)
        if res.status_code == 401:
            self._refresh_access_token()
            _track_api_call()
            res = self.session.get(url, headers=self._headers(), params=params)
        res.raise_for_status()
        return res.json()

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_activity_detail(self, activity_id):
        _track_api_call()
        url = f"{self.base_url}/activities/{activity_id}"
        res = self.session.get(url, headers=self._headers())
        if res.status_code == 401:
            self._refresh_access_token()
            _track_api_call()
            res = self.session.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    def check_connection(self):
        url = f"{self.base_url}/athlete"
        res = self.session.get(url, headers=self._headers())
        return res.status_code == 200
