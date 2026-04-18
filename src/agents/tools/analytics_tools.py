from langchain_core.tools import tool
import json
from src.analysis.readiness import compute_hrv_z_score
from src.analysis.load import compute_fatigue_index
from src.analysis.strength import detect_strength_plateaus
from src.analysis.dataset import build_dataset
from src.utils.database import get_workouts


def _sanitize_exercise_name(value: str):
    clean = (value or "").strip()
    return clean[:80]


@tool
def get_hrv_z_score():
    """
    Returns the statistical Z-score of today's HRV relative to the 30-day baseline.
    Z-score < -1.5 indicates significant physiological stress/fatigue.
    Z-score > 1.0 indicates excellent recovery.
    """
    # Get today's workout to find current HRV
    workouts = get_workouts(n_days=1)
    if not workouts:
        return json.dumps({"error": "No HRV data for today."})
    
    current_hrv = workouts[0].get("hrv_ms")
    if current_hrv is None:
        return json.dumps({"error": "No HRV data for today."})
        
    z_score = compute_hrv_z_score(float(current_hrv))
    return json.dumps({
        "z_score": z_score,
        "interpret": "Stressed" if z_score < -1.5 else "Optimal" if z_score > 0.5 else "Neutral"
    })

@tool
def get_fatigue_index():
    """
    Calculates the ratio of 7-day volume to 28-day volume (normalized).
    Index > 1.2 indicates elevated fatigue risk.
    """
    df = build_dataset(n_days=30)
    result = compute_fatigue_index(df)
    return json.dumps(result)

@tool
def audit_exercise_plateau(exercise_name: str):
    """
    Audits a specific exercise for performance plateaus over the last 5 sessions.
    Useful for queries like 'Why is my bench press not moving?'
    """
    safe_name = _sanitize_exercise_name(exercise_name)
    df = build_dataset(n_days=90)
    result = detect_strength_plateaus(df, safe_name)
    return json.dumps(result)

@tool
def fetch_30day_summary():
    """
    Returns a condensed text summary of high-level volume and recovery 
    trends for the last 30 days. Useful for pattern discovery.
    """
    df = build_dataset(n_days=30)
    if df.empty:
        return "No data available."
        
    summary = []
    for _, row in df.sort_values(by="date").iterrows():
        summary.append(f"Date: {row['date']} | Vol: {row['total_volume_kg']}kg | Readiness: {row['readiness_score']} | Sleep: {row['sleep_hours']}h")
    
    return "\n".join(summary)

analytics_tools = [get_hrv_z_score, get_fatigue_index, audit_exercise_plateau, fetch_30day_summary]
