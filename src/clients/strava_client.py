import os
import requests
from tenacity import retry, wait_exponential, stop_after_attempt
from src.utils.cache import cached
from src.utils.logger import app_logger
from src.utils.token_writer import write_token_to_env

from config import (
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
    STRAVA_REFRESH_TOKEN,
)

class AuthError(Exception):
    pass

class StravaClient:
    def __init__(self):
        self.base_url = "https://www.strava.com/api/v3"
        self.access_token = None
        self._refresh_access_token()

    def _refresh_access_token(self):
        url = "https://www.strava.com/oauth/token"
        payload = {
            "client_id": STRAVA_CLIENT_ID,
            "client_secret": STRAVA_CLIENT_SECRET,
            "refresh_token": STRAVA_REFRESH_TOKEN,
            "grant_type": "refresh_token"
        }
        res = requests.post(url, data=payload)
        if res.status_code == 200:
            data = res.json()
            self.access_token = data.get("access_token")
            app_logger.info("Strava token refresh successful")
            write_token_to_env("STRAVA_ACCESS_TOKEN", self.access_token)
        else:
            app_logger.error(f"Strava token refresh failed: {res.text}")
            raise AuthError(f"Strava token refresh failed: {res.text}")

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_activities(self, per_page=10, page=1):
        url = f"{self.base_url}/athlete/activities"
        params = {"per_page": per_page, "page": page}
        res = requests.get(url, headers=self._headers(), params=params)
        res.raise_for_status()
        return res.json()

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
    def get_activity_detail(self, activity_id):
        url = f"{self.base_url}/activities/{activity_id}"
        res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    def check_connection(self):
        url = f"{self.base_url}/athlete"
        res = requests.get(url, headers=self._headers())
        return res.status_code == 200
