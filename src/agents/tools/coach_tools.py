from langchain_core.tools import tool
from datetime import date
import json
from src.analysis.load import compute_weekly_load, compute_acwr, detect_overreach
from src.analysis.dataset import build_dataset
from src.utils.database import get_workout_by_date

@tool
def get_full_context():
    """
    Returns a combined view of today's readiness and this week's
    training load. Use this for holistic coaching recommendations.
    """
    today = date.today().isoformat()
    session = get_workout_by_date(today)
    
    if session:
        readiness = {
            "score": session.get("readiness_score"),
            "label": session.get("readiness_label"),
            "sleep_hours": session.get("sleep_hours"),
            "hrv_ms": session.get("hrv_ms"),
            "resting_hr": session.get("resting_hr"),
        }
    else:
        readiness = {"error": "No readiness data synced for today."}

    df = build_dataset(n_days=35)
    weekly = compute_weekly_load(df) if not df.empty else {"total_volume_kg": 0}
    acwr = compute_acwr(df) if not df.empty else None
    
    if df.empty:
        overreach, overreach_msg = False, "No data"
    else:
        overreach, overreach_msg = detect_overreach(df)

    return json.dumps({
        "readiness": readiness,
        "weekly_load": weekly,
        "acwr": acwr,
        "overreach_flag": overreach,
        "overreach_message": overreach_msg
    })

coach_tools = [get_full_context]

