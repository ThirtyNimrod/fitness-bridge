import base64
from datetime import datetime, timedelta, timezone
import os

import requests
from tenacity import retry, wait_exponential, stop_after_attempt
from src.utils.cache import cached
from src.utils.logger import app_logger
from src.utils.token_writer import write_token_to_env

from config import (
    FITBIT_CLIENT_ID,
    FITBIT_CLIENT_SECRET,
    FITBIT_ACCESS_TOKEN,
    FITBIT_REFRESH_TOKEN,
    FITBIT_TOKEN_EXPIRES_AT,
)

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
        self.access_token = self._get_runtime_value("FITBIT_ACCESS_TOKEN", FITBIT_ACCESS_TOKEN)
        self.refresh_token = self._get_runtime_value("FITBIT_REFRESH_TOKEN", self.refresh_token)
        self.token_expires_at = self._parse_expiry(
            self._get_runtime_value("FITBIT_TOKEN_EXPIRES_AT", FITBIT_TOKEN_EXPIRES_AT)
        )

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
            app_logger.info("Fitbit token refresh successful")
            write_token_to_env("FITBIT_ACCESS_TOKEN",  self.access_token)
            if self.refresh_token:
                write_token_to_env("FITBIT_REFRESH_TOKEN", self.refresh_token)
            if self.token_expires_at:
                write_token_to_env("FITBIT_TOKEN_EXPIRES_AT", str(int(self.token_expires_at.timestamp())))
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
