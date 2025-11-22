import requests

class FitbitClient:
    def __init__(self, access_token):
        self.base_url = "https://api.fitbit.com/1"
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def get_profile(self):
        """Check connection."""
        url = f"{self.base_url}/user/-/profile.json"
        try:
            response = requests.get(url, headers=self.headers)
            return response.status_code == 200
        except:
            return False

    def get_sleep_summary(self, date_str):
        """Fetches sleep data."""
        url = f"{self.base_url}/user/-/sleep/date/{date_str}.json"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        return {"error": response.text}

    def get_heart_rate(self, date_str):
        """Fetches heart rate data."""
        url = f"{self.base_url}/user/-/activities/heart/date/{date_str}/1d.json"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        return {"error": response.text}