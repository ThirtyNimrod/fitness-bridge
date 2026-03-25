import os
import sys

# Ensure Python can find 'config' module at the root, and 'src' package
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from src.clients.strava_client import StravaClient, AuthError as StravaAuthError
from src.clients.fitbit_client import FitbitClient, AuthError as FitbitAuthError
from src.utils.logger import app_logger

def test_clients():
    app_logger.info("Testing Strava Client...")
    try:
        strava = StravaClient()
        if strava.check_connection():
            app_logger.info("Strava connection OK.")
            acts = strava.get_activities(per_page=1)
            app_logger.info(f"Fetched {len(acts)} activities from Strava.")
        else:
            app_logger.warning("Strava connection Failed.")
    except Exception as e:
        app_logger.error(f"Strava test error: {e}")

    app_logger.info("Testing Fitbit Client...")
    try:
        fitbit = FitbitClient()
        if fitbit.check_connection():
            app_logger.info("Fitbit connection OK.")
            import datetime
            today = datetime.date.today().isoformat()
            try:
                hrv = fitbit.get_hrv(today)
                app_logger.info(f"Fetched Fitbit HRV for {today}.")
            except Exception as fe:
                app_logger.error(f"API Call failed (maybe token lacks scopes?): {fe}")
        else:
            app_logger.warning("Fitbit connection Failed.")
    except Exception as e:
        app_logger.error(f"Fitbit test error: {e}")

if __name__ == "__main__":
    test_clients()
