from langchain_core.tools import tool
from datetime import date, timedelta
import json
from src.clients.fitbit_client import FitbitClient
from src.analysis.readiness import compute_readiness

@tool
def get_todays_readiness():
    """
    Fetches today's readiness score computed from Fitbit sleep,
    HRV, and resting heart rate data. Returns score 0-100,
    label, component breakdown, and a recommendation.
    """
    today = date.today().isoformat()
    try:
        fitbit = FitbitClient()
        sleep_data = fitbit.get_sleep(today)
        hrv_data   = fitbit.get_hrv(today)
        resting_hr = fitbit.get_resting_hr(today)
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch data: {str(e)}"})

    result = compute_readiness(sleep_data, hrv_data, resting_hr)
    return json.dumps(result)

@tool
def get_readiness_trend(days: int = 7):
    """
    Returns readiness scores for the last N days.
    Useful for identifying a recovery pattern over time.
    """
    try:
        fitbit = FitbitClient()
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch data: {str(e)}"})
        
    trend = []
    for i in range(days):
        date_str = (date.today() - timedelta(days=i)).isoformat()
        try:
            sleep = fitbit.get_sleep(date_str)
            hrv   = fitbit.get_hrv(date_str)
            rhr   = fitbit.get_resting_hr(date_str)
            readiness = compute_readiness(sleep, hrv, rhr)
            trend.append({"date": date_str, "score": readiness["score"], "label": readiness["label"]})
        except Exception:
            continue

    return json.dumps(list(reversed(trend)))

readiness_tools = [get_todays_readiness, get_readiness_trend]
