from langchain_core.tools import tool
from datetime import date
import json
from src.analysis.load import compute_weekly_load, compute_acwr, detect_overreach
from src.analysis.dataset import build_dataset
from src.utils.database import get_workout_by_date
from src.utils.cache import cached


def _clamp_non_negative(value):
    if value is None:
        return None
    return max(0.0, float(value))


@cached(ttl=120)
def _build_full_context_payload(today: str):
    session = get_workout_by_date(today)

    if session:
        score = session.get("readiness_score")
        if score is not None:
            score = max(0.0, min(100.0, float(score)))
        readiness = {
            "score": score,
            "label": session.get("readiness_label"),
            "sleep_hours": _clamp_non_negative(session.get("sleep_hours")),
            "hrv_ms": _clamp_non_negative(session.get("hrv_ms")),
            "resting_hr": _clamp_non_negative(session.get("resting_hr")),
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

    return {
        "readiness": readiness,
        "weekly_load": weekly,
        "acwr": acwr,
        "overreach_flag": overreach,
        "overreach_message": overreach_msg,
    }

@tool
def get_full_context():
    """
    Returns a combined view of today's readiness and this week's
    training load. Use this for holistic coaching recommendations.
    """
    today = date.today().isoformat()
    return json.dumps(_build_full_context_payload(today))

coach_tools = [get_full_context]

