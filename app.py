import requests
import json
import datetime
from typing import Dict, Any

# --- CONFIGURATION ---
# You would typically load these from environment variables for security
HEVY_API_KEY = "YOUR_HEVY_API_KEY"
FITBIT_CLIENT_ID = "YOUR_FITBIT_CLIENT_ID"
FITBIT_CLIENT_SECRET = "YOUR_FITBIT_CLIENT_SECRET"

# OpenAI or Anthropic API Key
LLM_API_KEY = "YOUR_LLM_API_KEY" 

# --- HEVY API CLIENT ---
class HevyClient:
    def __init__(self, api_key):
        self.base_url = "https://api.hevyapp.com/v1"
        self.headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }

    def get_routines(self, page=1, page_size=10):
        """Fetches your workout routines."""
        url = f"{self.base_url}/routines"
        params = {"page": page, "pageSize": page_size}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def update_routine(self, routine_id, payload):
        """Updates a specific routine with new exercises/sets/reps."""
        url = f"{self.base_url}/routines/{routine_id}"
        response = requests.put(url, headers=self.headers, json=payload)
        if response.status_code == 200:
            print(f"✅ Successfully updated routine: {routine_id}")
        else:
            print(f"❌ Error updating routine: {response.text}")

# --- FITBIT API CLIENT (Simplified) ---
# Note: Real implementation requires OAuth2 token exchange flow using 'fitbit' library.
# This class assumes you have an access_token for demonstration.
class FitbitClient:
    def __init__(self, access_token):
        self.base_url = "https://api.fitbit.com/1"
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def get_sleep_data(self, date_str):
        """Fetches sleep data for a specific date (YYYY-MM-DD)."""
        url = f"{self.base_url}/user/-/sleep/date/{date_str}.json"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def get_readiness(self):
        """Fetches Daily Readiness Score (Requires Fitbit Premium usually)."""
        # Fallback: Calculate a simple score based on sleep minutes
        # In a real app, you'd fetch the actual /1/user/-/scores/readiness.json
        return {"score": 75, "status": "Good"} 

# --- LLM INTEGRATION (Mock) ---
def ask_llm_to_optimize(routine_json, health_metrics):
    """
    Sends the routine and health data to an LLM to get an optimized version.
    In production, use openai.ChatCompletion.create() or anthropic.messages.create()
    """
    
    prompt = f"""
    You are an expert strength and conditioning coach.
    
    CONTEXT:
    My current physical state is: {json.dumps(health_metrics)}
    My planned workout routine is: {json.dumps(routine_json)}
    
    INSTRUCTION:
    - If my sleep/recovery is poor (sleep < 6 hours or readiness < 60), reduce the total volume (sets) by 30% and increase rep range to lower intensity.
    - If my recovery is great, keep the routine as is or suggest a 5% weight increase.
    - Output ONLY the JSON for the updated routine structure required by Hevy API.
    """
    
    print("\n--- PROMPT SENT TO LLM ---")
    print(prompt[:300] + "...") # Print partial prompt for debug
    
    # SIMULATED RESPONSE FROM LLM (Example: It detected poor sleep)
    # It reduces sets from 4 to 3 and changes reps from 5 to 8
    updated_routine_mock = routine_json.copy()
    updated_routine_mock['notes'] = "⚠️ AI Adjusted: Volume reduced due to poor sleep (5.5 hrs)."
    
    # Simulating a change in the first exercise of the routine
    if 'exercises' in updated_routine_mock and len(updated_routine_mock['exercises']) > 0:
        first_exercise = updated_routine_mock['exercises'][0]
        # Modify sets (mock logic)
        if len(first_exercise.get('sets', [])) > 2:
             first_exercise['sets'].pop() # Remove one set
             
    return updated_routine_mock

# --- MAIN WORKFLOW ---
def main():
    # 1. Initialize Clients
    hevy = HevyClient(HEVY_API_KEY)
    # fitbit = FitbitClient(ACCESS_TOKEN) # Requires OAuth token setup
    
    # 2. Get Biological Context (Mocking data for script runnable)
    print("📡 Fetching Fitbit Data...")
    today = datetime.date.today().strftime("%Y-%m-%d")
    # sleep_data = fitbit.get_sleep_data(today)
    health_context = {
        "date": today,
        "sleep_hours": 5.5,
        "sleep_efficiency": 78, # Low efficiency
        "resting_heart_rate": 65 # Slightly elevated
    }
    print(f"   Body Status: {health_context}")

    # 3. Get Target Routine from Hevy
    print("🏋️ Fetching Hevy Routines...")
    routines_data = hevy.get_routines()
    
    if not routines_data.get('routines'):
        print("   No routines found. Create one in Hevy first.")
        return

    # Let's assume we want to do the first routine found
    target_routine = routines_data['routines'][0]
    print(f"   Target Routine: {target_routine['title']}")

    # 4. Optimize with LLM
    print("🧠 AI Optimizing...")
    new_routine_payload = ask_llm_to_optimize(target_routine, health_context)

    # 5. Update Hevy (Optional: ask user for confirmation first)
    confirm = input(f"   AI suggests modifying '{target_routine['title']}' (See notes). Update? (y/n): ")
    if confirm.lower() == 'y':
        # Note: Hevy API requires specific payload structure for PUT. 
        # You generally send the 'exercises' array.
        update_payload = {
            "exercises": new_routine_payload.get('exercises', []),
            "notes": new_routine_payload.get('notes', "")
        }
        hevy.update_routine(target_routine['id'], update_payload)

if __name__ == "__main__":
    main()