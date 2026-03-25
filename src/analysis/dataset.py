import json
import pandas as pd
from src.clients.strava_client import StravaClient
from src.clients.fitbit_client import FitbitClient
from src.parsers.hevy_parser import parse_description
from src.analysis.readiness import compute_readiness

def build_session_record(activity, exercises, readiness):
    muscle_groups = list(set([e.get("muscle_group") for e in exercises if e.get("muscle_group")]))
    has_drop = any(any(s.get("tag") == "Drop" for s in e.get("sets", [])) for e in exercises)
    has_failure = any(any(s.get("tag") == "Failure" for s in e.get("sets", [])) for e in exercises)
    total_volume_kg = sum(e.get("total_volume_kg", 0) for e in exercises)
    
    local_date = activity.get("start_date_local", "")
    date_str = local_date[:10] if local_date else "1970-01-01"
    
    return {
        "date": date_str,
        "activity_id": activity.get("id"),
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
        "readiness_label": readiness.get("label")
    }

def build_dataset(n_days=30):
    try:
        strava_client = StravaClient()
        fitbit_client = FitbitClient()
    except Exception as e:
        print(f"Warning: Client init failed. Proceeding with empty dataset. Error: {e}")
        return pd.DataFrame()
        
    try:
        activities = strava_client.get_activities(per_page=n_days)
    except Exception as e:
        print(f"Dataset warning: Could not fetch activities: {e}")
        return pd.DataFrame()
        
    dataset = []
    
    for activity in activities:
        if not activity.get("start_date_local"):
            continue
            
        date_str = activity["start_date_local"][:10]
        
        try:
            sleep_data = fitbit_client.get_sleep(date_str)
        except Exception:
            sleep_data = {}
            
        try:
            hrv_data = fitbit_client.get_hrv(date_str)
        except Exception:
            hrv_data = {}
            
        try:
            resting_hr = fitbit_client.get_resting_hr(date_str)
        except Exception:
            resting_hr = None
            
        try:
            detail = strava_client.get_activity_detail(activity["id"])
            description = detail.get("description", "")
        except Exception:
            detail = activity
            description = ""
            
        exercises = parse_description(description)
        readiness = compute_readiness(sleep_data, hrv_data, resting_hr)
        
        row = build_session_record(detail, exercises, readiness)
        dataset.append(row)
        
    return pd.DataFrame(dataset)

def get_session_for_date(date_str):
    df = build_dataset(n_days=60)
    if df.empty: 
        return None
    matches = df[df['date'] == date_str]
    if matches.empty: 
        return None
    return matches.iloc[0].to_dict()
