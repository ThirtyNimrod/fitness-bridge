import os
import sys
import webbrowser
import requests
import base64
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.database import upsert_api_token, init_db
from src.utils.logger import app_logger

load_dotenv()

REDIRECT_PORT = 8000
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}"

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        if "code" in query_components:
            self.server.auth_code = query_components["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Success!</h1><p>You can close this window now.</p>")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        return # Silence logging for cleaner CLI

def get_auth_code(auth_url):
    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), OAuthCallbackHandler)
    server.auth_code = None
    
    print(f"\nOpening browser for authentication...")
    print(f"URL: {auth_url}")
    webbrowser.open(auth_url)
    
    while server.auth_code is None:
        server.handle_request()
    
    return server.auth_code

def setup_fitbit():
    print("\n--- Fitbit OAuth Setup ---")
    client_id = os.getenv("FITBIT_CLIENT_ID")
    client_secret = os.getenv("FITBIT_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("Skipping Fitbit: Missing credentials in .env")
        return

    scope = "activity heartrate profile sleep"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": REDIRECT_URI,
        "expires_in": 604800
    }
    auth_url = f"https://www.fitbit.com/oauth2/authorize?{urlencode(params)}"
    
    code = get_auth_code(auth_url)
    
    token_url = "https://api.fitbit.com/oauth2/token"
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    
    res = requests.post(token_url, headers=headers, data=data)
    if res.status_code == 200:
        tokens = res.json()
        upsert_api_token(
            "fitbit",
            tokens["access_token"],
            tokens["refresh_token"],
            int(time.time() + tokens["expires_in"])
        )
        print("✅ Fitbit tokens saved to database vault!")
    else:
        print(f"❌ Fitbit setup failed: {res.text}")

def setup_strava():
    print("\n--- Strava OAuth Setup ---")
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("Skipping Strava: Missing credentials in .env")
        return

    scope = "read,activity:read_all"
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": scope
    }
    auth_url = f"https://www.strava.com/oauth/authorize?{urlencode(params)}"
    
    code = get_auth_code(auth_url)
    
    token_url = "https://www.strava.com/oauth/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code"
    }
    
    res = requests.post(token_url, data=data)
    if res.status_code == 200:
        tokens = res.json()
        upsert_api_token(
            "strava",
            tokens["access_token"],
            tokens["refresh_token"],
            tokens["expires_at"]
        )
        print("✅ Strava tokens saved to database vault!")
    else:
        print(f"❌ Strava setup failed: {res.text}")


def main():
    print("=======================================")
    print("Fitness Bridge — OAuth Setup Utility")
    print("=======================================")
    
    init_db()
    
    providers = []
    if "fitbit" in providers: setup_fitbit()
    if "strava" in providers: setup_strava()
    
    print("\nAll done! Your tokens are safely stored in the database vault.")

if __name__ == "__main__":
    main()
