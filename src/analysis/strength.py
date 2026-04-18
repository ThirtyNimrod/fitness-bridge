"""
analysis/strength.py
1RM estimation, personal record detection, and progressive overload tracking.
"""

import json
import pandas as pd


# ── Exercise-to-Muscle-Group Mapping ─────────────────────────────────────────
# Lowercase exercise names → muscle group.
# Extend this as new exercises appear in your Hevy logs.
EXERCISE_MUSCLE_MAP = {
    # Chest
    "bench press": "chest",
    "incline bench press": "chest",
    "decline bench press": "chest",
    "dumbbell bench press": "chest",
    "incline dumbbell press": "chest",
    "chest fly": "chest",
    "cable fly": "chest",
    "pec deck": "chest",
    "push up": "chest",
    "dips": "chest",
    # Back
    "barbell row": "back",
    "bent over row": "back",
    "cable row": "back",
    "seated row": "back",
    "lat pulldown": "back",
    "pull up": "back",
    "chin up": "back",
    "deadlift": "back",
    "t-bar row": "back",
    "face pull": "back",
    # Shoulders
    "overhead press": "shoulders",
    "military press": "shoulders",
    "shoulder press": "shoulders",
    "lateral raise": "shoulders",
    "front raise": "shoulders",
    "rear delt fly": "shoulders",
    "arnold press": "shoulders",
    "upright row": "shoulders",
    # Legs
    "squat": "legs",
    "back squat": "legs",
    "front squat": "legs",
    "leg press": "legs",
    "lunge": "legs",
    "leg extension": "legs",
    "leg curl": "legs",
    "romanian deadlift": "legs",
    "hip thrust": "legs",
    "calf raise": "legs",
    "bulgarian split squat": "legs",
    "hack squat": "legs",
    # Arms
    "bicep curl": "arms",
    "hammer curl": "arms",
    "preacher curl": "arms",
    "tricep pushdown": "arms",
    "tricep extension": "arms",
    "skull crusher": "arms",
    "close grip bench press": "arms",
    "cable curl": "arms",
    # Core
    "plank": "core",
    "crunch": "core",
    "sit up": "core",
    "leg raise": "core",
    "ab wheel": "core",
    "cable crunch": "core",
    "russian twist": "core",
    "hanging leg raise": "core",
}


def _map_exercise_to_group(exercise_name: str) -> str:
    """Map an exercise name to a muscle group. Falls back to 'other'."""
    name = exercise_name.strip().lower()
    # Exact match first
    if name in EXERCISE_MUSCLE_MAP:
        return EXERCISE_MUSCLE_MAP[name]
    # Partial match
    for key, group in EXERCISE_MUSCLE_MAP.items():
        if key in name or name in key:
            return group
    return "other"


def estimate_1rm(weight_kg: float, reps: int) -> float:
    """Estimate 1RM using the Epley formula.

    Returns the weight itself for single-rep sets.
    """
    if reps <= 0 or weight_kg <= 0:
        return 0.0
    if reps == 1:
        return round(weight_kg, 1)
    return round(weight_kg * (1 + reps / 30), 1)


def detect_prs(df: pd.DataFrame) -> list[dict]:
    """Scan exercises across all workouts, return personal records.

    Returns a list of dicts: {exercise, pr_type, value, date}
    """
    if df.empty or "exercises_raw" not in df.columns:
        return []

    exercise_records: dict[str, dict] = {}

    for _, row in df.iterrows():
        try:
            exercises = json.loads(row.get("exercises_raw", "[]"))
        except (TypeError, json.JSONDecodeError):
            continue

        workout_date = row.get("date", "")

        for ex in exercises:
            name = ex.get("name", "").strip()
            if not name:
                continue

            if name not in exercise_records:
                exercise_records[name] = {
                    "max_1rm": 0, "max_1rm_date": "",
                    "max_volume": 0, "max_volume_date": "",
                    "max_reps": 0, "max_reps_date": "",
                }

            rec = exercise_records[name]

            # Estimated 1RM from best set
            for s in ex.get("sets", []):
                weight = float(s.get("weight_kg", 0) or 0)
                reps = int(s.get("reps", 0) or 0)
                if weight > 0 and reps > 0:
                    est = estimate_1rm(weight, reps)
                    if est > rec["max_1rm"]:
                        rec["max_1rm"] = est
                        rec["max_1rm_date"] = workout_date

                if reps > rec["max_reps"]:
                    rec["max_reps"] = reps
                    rec["max_reps_date"] = workout_date

            # Total volume per exercise
            vol = float(ex.get("total_volume_kg", 0) or 0)
            if vol > rec["max_volume"]:
                rec["max_volume"] = vol
                rec["max_volume_date"] = workout_date

    prs = []
    for name, rec in exercise_records.items():
        if rec["max_1rm"] > 0:
            prs.append({
                "exercise": name,
                "pr_type": "estimated_1rm",
                "value": rec["max_1rm"],
                "date": rec["max_1rm_date"],
            })
        if rec["max_volume"] > 0:
            prs.append({
                "exercise": name,
                "pr_type": "max_session_volume",
                "value": rec["max_volume"],
                "date": rec["max_volume_date"],
            })
    return prs


def detect_progressive_overload(df: pd.DataFrame, exercise_name: str) -> dict:
    """Compare last 3 instances of an exercise for progression.

    Returns: {exercise, trend, pct_change, last_3_volumes: [...]}
    """
    if df.empty or "exercises_raw" not in df.columns:
        return {"exercise": exercise_name, "trend": "insufficient_data", "pct_change": 0, "last_3_volumes": []}

    appearances = []
    df_sorted = df.sort_values(by="date")

    for _, row in df_sorted.iterrows():
        try:
            exs = json.loads(row.get("exercises_raw", "[]"))
        except (TypeError, json.JSONDecodeError):
            continue
        for ex in exs:
            if ex.get("name", "").strip().lower() == exercise_name.strip().lower():
                vol = float(ex.get("total_volume_kg", 0) or 0)
                appearances.append({"date": row["date"], "volume": vol})

    if len(appearances) < 3:
        return {"exercise": exercise_name, "trend": "insufficient_data", "pct_change": 0, "last_3_volumes": []}

    last_3 = appearances[-3:]
    first_vol = last_3[0]["volume"]
    last_vol = last_3[-1]["volume"]

    if first_vol == 0:
        pct = 0
    else:
        pct = round((last_vol - first_vol) / first_vol * 100, 1)

    if pct >= 5:
        trend = "progressing"
    elif pct >= -5:
        trend = "maintaining"
    else:
        trend = "regressing"

    return {
        "exercise": exercise_name,
        "trend": trend,
        "pct_change": pct,
        "last_3_volumes": [a["volume"] for a in last_3],
    }


def compute_muscle_group_volume(df: pd.DataFrame) -> dict[str, float]:
    """Aggregate volume per muscle group from exercises_raw across all workouts.

    Returns: {muscle_group: total_volume_kg}
    """
    if df.empty or "exercises_raw" not in df.columns:
        return {}

    group_volumes: dict[str, float] = {}

    for _, row in df.iterrows():
        try:
            exercises = json.loads(row.get("exercises_raw", "[]"))
        except (TypeError, json.JSONDecodeError):
            continue

        for ex in exercises:
            name = ex.get("name", "").strip()
            group = ex.get("muscle_group") or _map_exercise_to_group(name)
            vol = float(ex.get("total_volume_kg", 0) or 0)
            group_volumes[group] = group_volumes.get(group, 0) + vol

    return group_volumes


def detect_strength_plateaus(df: pd.DataFrame, exercise_name: str, window: int = 5) -> dict:
    """Detect if an exercise has stalled in performance over the last N appearances.
    
    A plateau is defined as < 1% improvement in E1RM over the window.
    """
    if df.empty or "exercises_raw" not in df.columns:
        return {"exercise": exercise_name, "plateau": False, "reason": "no_data"}

    appearances = []
    df_sorted = df.sort_values(by="date")
    
    for _, row in df_sorted.iterrows():
        try:
            exs = json.loads(row.get("exercises_raw", "[]"))
            for ex in exs:
                if ex.get("name", "").strip().lower() == exercise_name.strip().lower():
                    # Find max 1RM for this workout
                    max_e1rm = 0
                    for s in ex.get("sets", []):
                        w = float(s.get("weight_kg", 0) or 0)
                        r = int(s.get("reps", 0) or 0)
                        if w > 0 and r > 0:
                            est = estimate_1rm(w, r)
                            if est > max_e1rm:
                                max_e1rm = est
                    if max_e1rm > 0:
                        appearances.append({"date": row["date"], "e1rm": max_e1rm})
        except Exception:
            pass

    if len(appearances) < window:
        return {"exercise": exercise_name, "plateau": False, "reason": "insufficient_history"}

    recent = appearances[-window:]
    starting_e1rm = recent[0]["e1rm"]
    ending_e1rm = recent[-1]["e1rm"]
    
    improvement_pct = ((ending_e1rm - starting_e1rm) / starting_e1rm) * 100
    
    is_plateau = improvement_pct < 1.0 # Less than 1% progress over the window
    
    return {
        "exercise": exercise_name,
        "plateau": is_plateau,
        "improvement_pct": round(improvement_pct, 2),
        "history": [a["e1rm"] for a in recent]
    }
