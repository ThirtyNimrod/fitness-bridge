import base64
import requests
from tenacity import retry, wait_exponential, stop_after_attempt
from src.utils.cache import cached

from config import (
    FITBIT_CLIENT_ID,
    FITBIT_CLIENT_SECRET,
    FITBIT_ACCESS_TOKEN,
    FITBIT_REFRESH_TOKEN,
)

class AuthError(Exception):
    pass

class FitbitClient:
    def __init__(self):
        self.base_url = "https://api.fitbit.com/1"
        self.access_token = FITBIT_ACCESS_TOKEN
        
        if not self.check_connection():
            self._refresh_access_token()

    def _refresh_access_token(self):
        url = "https://api.fitbit.com/oauth2/token"
        auth_str = f"{FITBIT_CLIENT_ID}:{FITBIT_CLIENT_SECRET}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": FITBIT_REFRESH_TOKEN
        }
        res = requests.post(url, headers=headers, data=data)
        if res.status_code == 200:
            json_data = res.json()
            self.access_token = json_data.get("access_token")
        else:
            raise AuthError(f"Fitbit token refresh failed: {res.text}")

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def get_sleep(self, date_str):
        # date_str format: "YYYY-MM-DD"
        url = f"{self.base_url}/user/-/sleep/date/{date_str}.json"
        res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def get_hrv(self, date_str):
        url = f"{self.base_url}/user/-/hrv/date/{date_str}.json"
        res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        return res.json()

    @cached(ttl=3600, ignore=('self',))
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def get_resting_hr(self, date_str):
        url = f"{self.base_url}/user/-/activities/heart/date/{date_str}/1d.json"
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
