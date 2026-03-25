import pandas as pd
from datetime import date, timedelta
import json

def compute_weekly_load(sessions_df):
    if sessions_df.empty:
        return {"total_volume_kg": 0, "total_duration_min": 0, "session_count": 0, "avg_volume_per_session": 0}
        
    sessions_df = sessions_df.copy()
    sessions_df['date_obj'] = pd.to_datetime(sessions_df['date']).dt.date
    seven_days_ago = date.today() - timedelta(days=7)
    
    this_week = sessions_df[sessions_df['date_obj'] > seven_days_ago]
    
    vol = float(this_week['total_volume_kg'].sum())
    dur = float(this_week['duration_min'].sum())
    count = len(this_week)
    
    return {
        "total_volume_kg": vol,
        "total_duration_min": dur,
        "session_count": count,
        "avg_volume_per_session": float(this_week['total_volume_kg'].mean()) if count > 0 else 0
    }

def compute_acwr(sessions_df):
    if sessions_df.empty: 
        return None
    
    sessions_df = sessions_df.copy()
    sessions_df['date_obj'] = pd.to_datetime(sessions_df['date']).dt.date
    today = date.today()
    
    acute_start = today - timedelta(days=7)
    chronic_start = today - timedelta(days=28)
    
    acute_load = sessions_df[(sessions_df['date_obj'] > acute_start) & (sessions_df['date_obj'] <= today)]['total_volume_kg'].sum()
    chronic_load_total = sessions_df[(sessions_df['date_obj'] > chronic_start) & (sessions_df['date_obj'] <= today)]['total_volume_kg'].sum()
    chronic_load = chronic_load_total / 4.0
    
    if chronic_load == 0: 
        return None
    
    ratio = acute_load / chronic_load
    
    def classify_acwr_zone(r):
        if r < 0.8: return "undertrained"
        elif r <= 1.3: return "optimal"
        elif r <= 1.5: return "caution"
        else: return "overreach_risk"
        
    return {
        "acute_load": float(acute_load),
        "chronic_load": float(chronic_load),
        "ratio": round(float(ratio), 2),
        "zone": classify_acwr_zone(ratio)
    }

def detect_overreach(sessions_df):
    acwr = compute_acwr(sessions_df)
    if acwr is None: 
        return False, "Insufficient history"
    
    if acwr["ratio"] > 1.5:
        return True, f"ACWR is {acwr['ratio']} — training load spiked significantly this week"
    return False, "Load looks manageable"

def progressive_overload_check(sessions_df, exercise_name):
    if sessions_df.empty or 'exercises_raw' not in sessions_df.columns:
        return {"exercise": exercise_name, "trend": "insufficient_data", "pct_change": 0, "recent_avg_volume": 0}
        
    appearances = []
    df_sorted = sessions_df.sort_values(by="date")
    
    for _, row in df_sorted.iterrows():
        try:
            exs = json.loads(row['exercises_raw'])
            for ex in exs:
                if ex['name'].lower() == exercise_name.lower():
                    appearances.append({
                        "date": row['date'],
                        "volume": ex.get('total_volume_kg', 0)
                    })
        except Exception:
            pass
            
    if len(appearances) < 2:
        return {"exercise": exercise_name, "trend": "insufficient_data", "pct_change": 0, "recent_avg_volume": 0}
        
    last_6 = appearances[-6:]
    if len(last_6) < 2:
        return {"exercise": exercise_name, "trend": "insufficient_data", "pct_change": 0, "recent_avg_volume": 0}
        
    mid = len(last_6) // 2
    first_half = last_6[:mid]
    second_half = last_6[mid:]
    
    first_avg = sum(a['volume'] for a in first_half) / len(first_half)
    last_avg = sum(a['volume'] for a in second_half) / len(second_half)
    
    if first_avg == 0:
        pct_change = 0
    else:
        pct_change = (last_avg - first_avg) / first_avg * 100
        
    if pct_change >= 5: trend = "progressing"
    elif pct_change >= -5: trend = "maintaining"
    else: trend = "regressing"
    
    return {
        "exercise": exercise_name,
        "trend": trend,
        "pct_change": round(pct_change, 1),
        "recent_avg_volume": round(last_avg, 2)
    }
