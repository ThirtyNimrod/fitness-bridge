import json
import datetime
from langchain.tools import tool
from src.clients.hevy_client import HevyClient
from src.clients.fitbit_client import FitbitClient
import os

# Initialize clients globally or inside tools using env vars
# Ideally, we'd inject these, but for simplicity in Streamlit, we read env
def get_hevy():
    return HevyClient(os.getenv("HEVY_API_KEY"))

def get_fitbit():
    return FitbitClient(os.getenv("FITBIT_ACCESS_TOKEN"))

@tool
def get_recent_workouts(limit: int = 3):
    """Fetches the most recent completed workouts from Hevy. Use this to summarize past progress."""
    client = get_hevy()
    data = client.get_workouts(page_size=limit)
    # Simplify output for LLM token usage
    summaries = []
    if 'workouts' in data:
        for w in data['workouts']:
            summaries.append({
                "title": w.get('title'),
                "start_time": w.get('start_time'),
                "volume_kg": w.get('volume_kg'),
                "exercises_count": len(w.get('exercises', []))
            })
    return json.dumps(summaries)

@tool
def get_todays_readiness():
    """Fetches Fitbit sleep and heart rate data to determine readiness for training."""
    client = get_fitbit()
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    sleep = client.get_sleep_summary(today)
    # Mocking readiness logic since raw API data is complex
    sleep_summary = sleep.get('summary', {})
    total_minutes = sleep_summary.get('totalMinutesAsleep', 0)
    
    readiness = {
        "date": today,
        "sleep_minutes": total_minutes,
        "sleep_hours": round(total_minutes / 60, 1),
        "status": "Unknown"
    }
    
    if total_minutes > 420: # 7 hours
        readiness['status'] = "High Readiness"
    elif total_minutes > 300: # 5 hours
        readiness['status'] = "Moderate Fatigue"
    else:
        readiness['status'] = "High Fatigue - Caution Recommended"
        
    return json.dumps(readiness)

@tool
def get_routine_details(routine_name: str):
    """Fetches details of a specific workout routine by searching for its name."""
    client = get_hevy()
    data = client.get_routines(page_size=20) # Fetch more to search
    
    found_routine = None
    if 'routines' in data:
        for r in data['routines']:
            if routine_name.lower() in r['title'].lower():
                found_routine = r
                break
    
    if found_routine:
        # Strip IDs to make it readable for the LLM unless needed for update
        exercises = []
        for e in found_routine.get('exercises', []):
            exercises.append(f"{e['title']} ({len(e['sets'])} sets)")
        return json.dumps({"id": found_routine['id'], "title": found_routine['title'], "exercises": exercises})
    else:
        return "Routine not found."

# List of tools to export
fitness_tools = [get_recent_workouts, get_todays_readiness, get_routine_details]