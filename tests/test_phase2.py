import os
import sys

# Ensure Python can find 'config' module at the root, and 'src' package
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from src.clients.strava_client import StravaClient, AuthError as StravaAuthError
from src.clients.fitbit_client import FitbitClient, AuthError as FitbitAuthError

def test_clients():
    print("Testing Strava Client...")
    try:
        strava = StravaClient()
        if strava.check_connection():
            print("Strava connection OK.")
            acts = strava.get_activities(per_page=1)
            print(f"Fetched {len(acts)} activities from Strava.")
        else:
            print("Strava connection Failed.")
    except Exception as e:
        print(f"Strava test error: {e}")

    print("\nTesting Fitbit Client...")
    try:
        fitbit = FitbitClient()
        if fitbit.check_connection():
            print("Fitbit connection OK.")
            import datetime
            today = datetime.date.today().isoformat()
            try:
                hrv = fitbit.get_hrv(today)
                print(f"Fetched Fitbit HRV for {today}.")
            except Exception as fe:
                print(f"API Call failed (maybe token lacks scopes?): {fe}")
        else:
            print("Fitbit connection Failed.")
    except Exception as e:
        print(f"Fitbit test error: {e}")

if __name__ == "__main__":
    test_clients()
