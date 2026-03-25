def score_sleep(sleep_data):
    try:
        total_minutes = sleep_data.get("summary", {}).get("totalMinutesAsleep", 0)
        efficiency = sleep_data.get("summary", {}).get("efficiency", 0)
    except Exception:
        return 5

    if total_minutes >= 480: time_score = 40
    elif total_minutes >= 420: time_score = 35
    elif total_minutes >= 360: time_score = 25
    elif total_minutes >= 300: time_score = 15
    else: time_score = 5

    efficiency_bonus = (efficiency / 100) * 10
    return min(40, round(time_score + efficiency_bonus))


def score_hrv(hrv_data):
    try:
        hrv_value = hrv_data.get("hrv", [])[0].get("value", {}).get("dailyRmssd")
    except Exception:
        hrv_value = None
        
    baseline = 45.0  # In a complete app, we'd pull rolling 30-day avg
    if hrv_value is None: 
        return 20

    ratio = hrv_value / baseline
    if ratio >= 1.10: return 40
    elif ratio >= 0.95: return 35
    elif ratio >= 0.80: return 20
    elif ratio >= 0.65: return 10
    else: return 0


def score_resting_hr(resting_hr, baseline_hr):
    if resting_hr is None: 
        return 10

    delta = resting_hr - baseline_hr
    if delta <= -2: return 20
    elif delta <= 2: return 17
    elif delta <= 5: return 10
    elif delta <= 8: return 5
    else: return 0


def get_readiness_label(score):
    if score >= 75: return "High readiness — train hard"
    elif score >= 50: return "Moderate readiness — train normally"
    elif score >= 30: return "Low readiness — consider deload"
    else: return "Poor readiness — rest or active recovery only"


def derive_recommendation(score):
    if score >= 75: return "Good day for a heavy session or a PR attempt."
    elif score >= 50: return "Normal training. Avoid maximal efforts."
    elif score >= 30: return "Reduce intensity by 20-30%. Prioritize form."
    else: return "Full rest or light mobility work only."


def compute_readiness(sleep_data, hrv_data, resting_hr):
    sleep_score = score_sleep(sleep_data)
    hrv_score = score_hrv(hrv_data)
    
    # Derive from history ideally; hardcoded to 60 for MVP math
    hr_score = score_resting_hr(resting_hr, baseline_hr=60)
    
    total = sleep_score + hrv_score + hr_score
    
    try:
        sleep_minutes = sleep_data.get("summary", {}).get("totalMinutesAsleep", 0)
        sleep_efficiency = sleep_data.get("summary", {}).get("efficiency", 0)
    except Exception:
        sleep_minutes = 0
        sleep_efficiency = 0
        
    try:
        hrv_ms = hrv_data.get("hrv", [])[0].get("value", {}).get("dailyRmssd")
    except Exception:
        hrv_ms = None

    return {
        "score": total,
        "label": get_readiness_label(total),
        "sleep_minutes": sleep_minutes,
        "sleep_hours": round(sleep_minutes / 60, 1),
        "sleep_efficiency": sleep_efficiency,
        "hrv_ms": hrv_ms,
        "resting_hr": resting_hr,
        "components": {
            "sleep": sleep_score,
            "hrv": hrv_score,
            "resting_hr": hr_score
        },
        "recommendation": derive_recommendation(total)
    }
