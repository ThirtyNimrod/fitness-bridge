import base64
from datetime import datetime, timedelta, timezone
import os

import requests
from tenacity import retry, wait_exponential, stop_after_attempt
from src.utils.cache import cached
from src.utils.logger import app_logger
from src.utils.database import get_api_token, upsert_api_token

from config import (
    FITBIT_CLIENT_ID,
    FITBIT_CLIENT_SECRET,
    FITBIT_ACCESS_TOKEN,
    FITBIT_REFRESH_TOKEN,
    FITBIT_TOKEN_EXPIRES_AT,
)

# ── Fitbit Activity Type Mapping ──────────────────────────────────────────────
# Maps Fitbit activityTypeId codes to normalised categories.
# Extend this dict as you use more workout modes on your Pixel Watch.
ACTIVITY_TYPE_MAP = {
    # Sport
    15000: "sport",          # Badminton
    15010: "sport",          # Tennis
    15020: "sport",          # Table Tennis
    15030: "sport",          # Squash
    15040: "sport",          # Racquetball
    15050: "sport",          # Basketball
    15060: "sport",          # Football (Soccer)
    15070: "sport",          # Volleyball
    15080: "sport",          # Cricket
    # Strength
    90013: "strength",       # Strength Training
    90014: "strength",       # Weightlifting
    90015: "strength",       # Weights
    15820: "strength",       # Crossfit
    # Cardio
    90009: "cardio",         # Elliptical
    90001: "cardio",         # Bike
    90019: "cardio",         # Spinning
    1020:  "cardio",         # Cycling
    90024: "cardio",         # HIIT
    12010: "cardio",         # Swimming
    # Walking / Running
    15680: "walking",        # Walk
    15670: "walking",        # Treadmill
    90013: "strength",       # (duplicate guard)
    90009: "cardio",         # (duplicate guard)
    15000: "sport",          # (duplicate guard)
    17080: "walking",        # Hiking
    90020: "running",        # Run
    12150: "running",        # Outdoor Run
    # Flexibility / Yoga
    52001: "flexibility",    # Yoga
    52002: "flexibility",    # Pilates
    15660: "flexibility",    # Stretching
}

class AuthError(Exception):
    pass

class FitbitClient:
    def __init__(self):
        self.base_url = "https://api.fitbit.com/1"
        self.client_id = FITBIT_CLIENT_ID
        self.client_secret = FITBIT_CLIENT_SECRET
        self.refresh_token = FITBIT_REFRESH_TOKEN
        self.access_token = None
        self.token_expires_at = None
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
        token_data = get_api_token("fitbit")
        if token_data and token_data.get("refresh_token"):
            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")
            self.token_expires_at = self._parse_expiry(token_data.get("expires_at"))
            app_logger.info("Fitbit tokens loaded from database vault")
            return

        # 2. Fallback to Environment (Initial setup)
        self.access_token = self._get_runtime_value("FITBIT_ACCESS_TOKEN", FITBIT_ACCESS_TOKEN)
        self.refresh_token = self._get_runtime_value("FITBIT_REFRESH_TOKEN", self.refresh_token)
        self.token_expires_at = self._parse_expiry(
            self._get_runtime_value("FITBIT_TOKEN_EXPIRES_AT", FITBIT_TOKEN_EXPIRES_AT)
        )
        if self.refresh_token:
            app_logger.info("Fitbit tokens loaded from environment (fallback)")

    def _parse_expiry(self, expiry_value):
        if not expiry_value:
            return None
        try:
            return datetime.fromtimestamp(int(expiry_value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    def _is_token_expired(self):
        if not self.access_token:
            return True
        if not self.token_expires_at:
            return False
        # Refresh slightly early to avoid race conditions around expiration.
        return datetime.now(timezone.utc) >= (self.token_expires_at - timedelta(minutes=2))

    def _ensure_access_token(self):
        self._load_runtime_auth_state()
        if self._is_token_expired():
            self._refresh_access_token()

    def _refresh_access_token(self):
        url = "https://api.fitbit.com/oauth2/token"
        auth_str = f"{self.client_id}:{self.client_secret}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        res = requests.post(url, headers=headers, data=data)
        if res.status_code == 200:
            json_data = res.json()
            self.access_token  = json_data.get("access_token")
            new_refresh        = json_data.get("refresh_token")
            expires_in         = json_data.get("expires_in")
            if new_refresh:
                self.refresh_token = new_refresh
            if expires_in:
                self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            
            app_logger.info("Fitbit token refresh successful — updating vault")
            upsert_api_token(
                "fitbit",
                self.access_token,
                self.refresh_token,
                int(self.token_expires_at.timestamp()) if self.token_expires_at else None
            )
        else:
            app_logger.error(f"Fitbit token refresh failed: {res.text}")
            raise AuthError(f"Fitbit token refresh failed: {res.text}")

    def _headers(self):
        self._ensure_access_token()
        return {"Authorization": f"Bearer {self.access_token}"}

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_sleep(self, date_str):
        # date_str format: "YYYY-MM-DD"
        url = f"{self.base_url}/user/-/sleep/date/{date_str}.json"
        res = requests.get(url, headers=self._headers())
        if res.status_code == 401:
            self._refresh_access_token()
            res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_hrv(self, date_str):
        url = f"{self.base_url}/user/-/hrv/date/{date_str}.json"
        res = requests.get(url, headers=self._headers())
        if res.status_code == 401:
            self._refresh_access_token()
            res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_resting_hr(self, date_str):
        url = f"{self.base_url}/user/-/activities/heart/date/{date_str}/1d.json"
        res = requests.get(url, headers=self._headers())
        if res.status_code == 401:
            self._refresh_access_token()
            res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        data = res.json()
        
        try:
            activities = data.get("activities-heart", [])
            if not activities:
                return None
            val = activities[0].get("value", {})
            return val.get("restingHeartRate")
        except (IndexError, KeyError, TypeError):
            return None

    def check_connection(self):
        if not self.access_token:
            return False
            
        url = f"{self.base_url}/user/-/profile.json"
        res = requests.get(url, headers=self._headers())
        return res.status_code == 200

    # ── Activity Log Methods ──────────────────────────────────────────────────

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_activities(self, before_date: str | None = None, limit: int = 20) -> list[dict]:
        """Fetch user activity log list from Fitbit (Pixel Watch workouts).

        Args:
            before_date: ISO date string (YYYY-MM-DD). Defaults to today.
            limit: Max activities to return (Fitbit caps at 100).
        Returns:
            List of activity log dicts.
        """
        safe_limit = max(1, min(100, limit))
        params = {
            "beforeDate": before_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "offset": 0,
            "limit": safe_limit,
            "sort": "desc",
        }
        url = f"{self.base_url}/user/-/activities/list.json"
        res = requests.get(url, headers=self._headers(), params=params)
        if res.status_code == 401:
            self._refresh_access_token()
            res = requests.get(url, headers=self._headers(), params=params)
        res.raise_for_status()
        return res.json().get("activities", [])

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_activity_detail(self, log_id: int) -> dict:
        """Fetch detail for a single activity log entry."""
        url = f"{self.base_url}/user/-/activities/{int(log_id)}.json"
        res = requests.get(url, headers=self._headers())
        if res.status_code == 401:
            self._refresh_access_token()
            res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()
