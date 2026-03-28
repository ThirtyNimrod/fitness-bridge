from langchain_core.tools import tool
from datetime import date, timedelta
import json
from src.utils.database import get_workouts, get_workout_by_date


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))

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
        
    score = session.get("readiness_score")
    if score is not None:
        score = max(0.0, min(100.0, float(score)))

    return json.dumps({
        "score": score,
        "label": session.get("readiness_label"),
        "sleep_hours": max(0.0, float(session.get("sleep_hours") or 0.0)),
        "hrv_ms": max(0.0, float(session.get("hrv_ms") or 0.0)) if session.get("hrv_ms") is not None else None,
        "resting_hr": max(0.0, float(session.get("resting_hr") or 0.0)) if session.get("resting_hr") is not None else None,
    })

@tool
def get_readiness_trend(days: int = 7):
    """
    Returns readiness scores for the last N days.
    Useful for identifying a recovery pattern over time.
    """
    safe_days = _bounded_int(days, default=7, minimum=1, maximum=90)
    workouts = get_workouts(n_days=safe_days)
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
