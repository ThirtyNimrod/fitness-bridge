from langchain_core.tools import tool
from datetime import date, timedelta
import json
from src.utils.database import get_workouts, get_workout_by_date

@tool
def get_todays_readiness():
    """
    Fetches today's readiness score computed from sleep,
    HRV, and resting heart rate data. Returns score 0-100,
    label, component breakdown, and a recommendation.
    """
    today = date.today().isoformat()
    session = get_workout_by_date(today)
    
    if not session:
        return json.dumps({"error": "No data synced for today yet."})
        
    return json.dumps({
        "score": session.get("readiness_score"),
        "label": session.get("readiness_label"),
        "sleep_hours": session.get("sleep_hours"),
        "hrv_ms": session.get("hrv_ms"),
        "resting_hr": session.get("resting_hr"),
    })

@tool
def get_readiness_trend(days: int = 7):
    """
    Returns readiness scores for the last N days.
    Useful for identifying a recovery pattern over time.
    """
    workouts = get_workouts(n_days=days)
    if not workouts:
        return json.dumps({"error": "No data available."})
        
    trend = []
    # get_workouts returns newest first, we want oldest first for a trend
    for w in reversed(workouts):
        if w.get("readiness_score") is not None:
            trend.append({
                "date": w["date"], 
                "score": w["readiness_score"], 
                "label": w["readiness_label"]
            })

    return json.dumps(trend)

readiness_tools = [get_todays_readiness, get_readiness_trend]
