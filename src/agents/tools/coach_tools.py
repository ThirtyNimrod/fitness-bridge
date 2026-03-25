from langchain_core.tools import tool
from datetime import date
import json
from src.clients.fitbit_client import FitbitClient
from src.analysis.readiness import compute_readiness
from src.analysis.load import compute_weekly_load, compute_acwr, detect_overreach
from src.analysis.dataset import build_dataset

@tool
def get_full_context():
    """
    Returns a combined view of today's readiness and this week's
    training load. Use this for holistic coaching recommendations.
    """
    today = date.today().isoformat()
    try:
        fitbit = FitbitClient()
        sleep = fitbit.get_sleep(today)
        hrv = fitbit.get_hrv(today)
        rhr = fitbit.get_resting_hr(today)
        readiness = compute_readiness(sleep, hrv, rhr)
    except Exception as e:
        readiness = {"error": str(e)}

    df = build_dataset(n_days=35)
    weekly = compute_weekly_load(df)
    acwr = compute_acwr(df)
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
