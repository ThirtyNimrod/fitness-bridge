import json
import pandas as pd
from src.utils.database import get_workouts, get_workout_by_date
from src.parsers.hevy_parser import parse_description
from src.analysis.readiness import compute_readiness
from src.utils.logger import app_logger


def build_session_record(activity, exercises, readiness):
    """Build a unified workout dict from Strava activity + parsed exercises + readiness.
    Still used by SyncEngine during the sync phase.
    """
    muscle_groups = list(set([e.get("muscle_group") for e in exercises if e.get("muscle_group")]))
    has_drop = any(any(s.get("tag") == "Drop" for s in e.get("sets", [])) for e in exercises)
    has_failure = any(any(s.get("tag") == "Failure" for s in e.get("sets", [])) for e in exercises)
    total_volume_kg = sum(e.get("total_volume_kg", 0) for e in exercises)

    local_date = activity.get("start_date_local", "")
    date_str = local_date[:10] if local_date else "1970-01-01"

    return {
        "date": date_str,
        "activity_id": str(activity.get("id", "")),
        "workout_title": activity.get("name", "Workout"),
        "duration_min": activity.get("elapsed_time", 0) / 60,
        "total_volume_kg": total_volume_kg,
        "exercise_count": len(exercises),
        "set_count": sum(e.get("set_count", 0) for e in exercises),
        "exercises_raw": json.dumps(exercises),
        "muscle_groups": json.dumps(muscle_groups),
        "has_drop_sets": has_drop,
        "has_failure_sets": has_failure,
        "sleep_hours": readiness.get("sleep_hours", 0),
        "sleep_efficiency": readiness.get("sleep_efficiency", 0),
        "hrv_ms": readiness.get("hrv_ms"),
        "resting_hr": readiness.get("resting_hr"),
        "readiness_score": readiness.get("score"),
        "readiness_label": readiness.get("label"),
    }


def build_dataset(n_days=30):
    """Read workouts from the local SQLite cache — instant, no API calls."""
    rows = get_workouts(n_days=n_days)
    if not rows:
        app_logger.info("build_dataset: no rows in DB, returning empty DataFrame")
        return pd.DataFrame()
    return pd.DataFrame(rows)


def get_session_for_date(date_str):
    """Return a single workout dict for the given date from the local cache."""
    return get_workout_by_date(date_str)

