from langchain_core.tools import tool
import json
from src.analysis.load import compute_weekly_load, compute_acwr, progressive_overload_check
from src.analysis.dataset import build_dataset
from src.analysis.strength import detect_prs, compute_muscle_group_volume


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _sanitize_exercise_name(value: str):
    clean = (value or "").strip()
    return clean[:80]

@tool
def get_recent_workouts(limit: int = 5):
    """
    Returns the last N workout sessions with parsed exercise details,
    volume, set count, and readiness on that day.
    """
    safe_limit = _bounded_int(limit, default=5, minimum=1, maximum=30)
    df = build_dataset(n_days=30)
    if df.empty:
        return json.dumps({"error": "No data available."})
        
    df_sorted = df.sort_values(by="date", ascending=False)
    recent = df_sorted.head(safe_limit)
    return recent.to_json(orient="records")

@tool
def get_weekly_load():
    """
    Returns this week's total training volume, session count,
    and comparison to the previous week.
    """
    df = build_dataset(n_days=28)
    current = compute_weekly_load(df)
    return json.dumps(current)

@tool
def get_acwr():
    """
    Returns the Acute:Chronic Workload Ratio.
    Values between 0.8 and 1.3 are optimal.
    Above 1.5 is overreach risk.
    """
    df = build_dataset(n_days=35)
    result = compute_acwr(df)
    return json.dumps(result)

@tool
def get_exercise_progress(exercise_name: str):
    """
    Returns progressive overload trend for a specific exercise
    over the last 6 sessions it appeared in.
    """
    safe_name = _sanitize_exercise_name(exercise_name)
    if not safe_name:
        return json.dumps({"error": "exercise_name is required."})

    df = build_dataset(n_days=60)
    result = progressive_overload_check(df, safe_name)
    return json.dumps(result)

@tool
def get_personal_records():
    """
    Returns current personal records (estimated 1RM, max session volume)
    for all exercises across the last 90 days.
    """
    df = build_dataset(n_days=90)
    if df.empty:
        return json.dumps({"error": "No data available."})
    prs = detect_prs(df)
    return json.dumps(prs)

@tool
def get_muscle_group_volume(days: int = 7):
    """
    Returns total volume (kg) per muscle group for the given time period.
    Useful for answering 'Did I hit enough chest volume this week?'
    """
    safe_days = _bounded_int(days, default=7, minimum=1, maximum=90)
    df = build_dataset(n_days=safe_days)
    if df.empty:
        return json.dumps({"error": "No data available."})
    volumes = compute_muscle_group_volume(df)
    return json.dumps(volumes)

progress_tools = [get_recent_workouts, get_weekly_load, get_acwr, get_exercise_progress,
                  get_personal_records, get_muscle_group_volume]
