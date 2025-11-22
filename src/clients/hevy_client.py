import requests

class HevyClient:
    def __init__(self, api_key):
        self.base_url = "https://api.hevyapp.com/v1"
        self.headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }

    def check_connection(self):
        """Check if API key is valid."""
        url = f"{self.base_url}/workouts/count"
        try:
            response = requests.get(url, headers=self.headers)
            return response.status_code == 200
        except:
            return False

    def get_routines(self, page=1, page_size=5):
        url = f"{self.base_url}/routines"
        params = {"page": page, "pageSize": page_size}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def get_workouts(self, page=1, page_size=5):
        url = f"{self.base_url}/workouts"
        params = {"page": page, "pageSize": page_size}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def update_routine(self, routine_id, payload):
        url = f"{self.base_url}/routines/{routine_id}"
        response = requests.put(url, headers=self.headers, json=payload)
        return response.json()