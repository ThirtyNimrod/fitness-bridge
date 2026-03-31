import pandas as pd
from datetime import date, timedelta
import json


def _prepare_sessions_df(sessions_df):
    df = sessions_df.copy()
    df['date_obj'] = pd.to_datetime(df['date'], errors='coerce').dt.date
    df['total_volume_kg'] = pd.to_numeric(df.get('total_volume_kg', 0), errors='coerce').fillna(0.0)
    df['duration_min'] = pd.to_numeric(df.get('duration_min', 0), errors='coerce').fillna(0.0)
    return df.dropna(subset=['date_obj'])


def compute_weekly_load(sessions_df):
    if sessions_df.empty:
        return {"total_volume_kg": 0, "total_duration_min": 0, "session_count": 0, "avg_volume_per_session": 0}
        
    sessions_df = _prepare_sessions_df(sessions_df)
    seven_days_ago = date.today() - timedelta(days=6)
    
    this_week = sessions_df[sessions_df['date_obj'] >= seven_days_ago]
    
    vol = float(this_week['total_volume_kg'].sum())
    dur = float(this_week['duration_min'].sum())
    count = len(this_week)
    
    return {
        "total_volume_kg": vol,
        "total_duration_min": dur,
        "session_count": count,
        "avg_volume_per_session": float(this_week['total_volume_kg'].mean()) if count > 0 else 0
    }


def detect_deload_weeks(sessions_df: pd.DataFrame) -> list[dict]:
    """Flag weeks where volume dropped >30% from the prior week.

    Returns list of dicts: {week, volume, prev_volume, drop_pct}
    """
    if sessions_df.empty:
        return []

    df = _prepare_sessions_df(sessions_df)
    if df.empty:
        return []

    df["iso_week"] = pd.to_datetime(df["date"]).dt.strftime("%G-W%V")
    weekly = df.groupby("iso_week")["total_volume_kg"].sum().sort_index()

    deloads = []
    prev_vol = None
    for week, vol in weekly.items():
        if prev_vol is not None and prev_vol > 0:
            drop_pct = round((prev_vol - vol) / prev_vol * 100, 1)
            if drop_pct > 30:
                deloads.append({
                    "week": week,
                    "volume": round(vol, 1),
                    "prev_volume": round(prev_vol, 1),
                    "drop_pct": drop_pct,
                })
        prev_vol = vol

    return deloads

def compute_acwr(sessions_df):
    if sessions_df.empty: 
        return None
    
    sessions_df = _prepare_sessions_df(sessions_df)
    if sessions_df.empty:
        return None

    today = date.today()

    acute_start = today - timedelta(days=6)
    acute_mask = (sessions_df['date_obj'] >= acute_start) & (sessions_df['date_obj'] <= today)
    acute_load = float(sessions_df[acute_mask]['total_volume_kg'].sum())

    # Chronic load: prior 28 days excluding the acute week for cleaner comparison.
    chronic_end = acute_start - timedelta(days=1)
    chronic_start = chronic_end - timedelta(days=27)
    chronic_mask = (sessions_df['date_obj'] >= chronic_start) & (sessions_df['date_obj'] <= chronic_end)
    chronic_window = sessions_df[chronic_mask]

    chronic_divisor_weeks = None
    if len(chronic_window) > 0:
        span_days = (chronic_window['date_obj'].max() - chronic_window['date_obj'].min()).days + 1
        chronic_divisor_weeks = max(1.0, span_days / 7.0)

    if len(chronic_window) == 0:
        # Fallback for sparse history: use up to 28 days including acute data.
        fallback_start = today - timedelta(days=27)
        chronic_window = sessions_df[(sessions_df['date_obj'] >= fallback_start) & (sessions_df['date_obj'] <= today)]
        chronic_divisor_weeks = 4.0

    chronic_load_total = float(chronic_window['total_volume_kg'].sum())
    chronic_load = chronic_load_total / float(chronic_divisor_weeks or 4.0)
    
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
        "ratio_raw": float(ratio),
        "ratio": round(float(ratio), 2),
        "zone": classify_acwr_zone(ratio)
    }

def detect_overreach(sessions_df):
    acwr = compute_acwr(sessions_df)
    if acwr is None: 
        return False, "Insufficient history"
    
    if acwr["zone"] == "overreach_risk":
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
