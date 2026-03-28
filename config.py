import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Strava API Config
STRAVA_ACCESS_TOKEN    = os.getenv("STRAVA_ACCESS_TOKEN")
STRAVA_CLIENT_ID      = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET  = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN  = os.getenv("STRAVA_REFRESH_TOKEN")
STRAVA_TOKEN_EXPIRES_AT = os.getenv("STRAVA_TOKEN_EXPIRES_AT")

# Fitbit API Config
FITBIT_ACCESS_TOKEN   = os.getenv("FITBIT_ACCESS_TOKEN")
FITBIT_CLIENT_ID      = os.getenv("FITBIT_CLIENT_ID")
FITBIT_CLIENT_SECRET  = os.getenv("FITBIT_CLIENT_SECRET")
FITBIT_REFRESH_TOKEN  = os.getenv("FITBIT_REFRESH_TOKEN")
FITBIT_TOKEN_EXPIRES_AT = os.getenv("FITBIT_TOKEN_EXPIRES_AT")

# Ollama LLM Config
OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "qwen2.5:4b")

# System Paths and Thresholds
CACHE_DIR        = "data/cache"
CACHE_TTL_SECS   = 3600          # 1 hour default TTL
DB_PATH          = "data/fitness_bridge.db"

# Memory & Analysis Constants
SHORT_TERM_WINDOW   = 8           # Last N messages kept verbatim
READINESS_HIGH      = 420         # Minutes (7h sleep)
READINESS_MODERATE  = 300         # Minutes (5h sleep)
LOAD_OVERREACH_PCT  = 150         # % of baseline weekly volume
