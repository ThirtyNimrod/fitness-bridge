import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Upstash Redis Config
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

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
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL", "gemma3:270m")

# System Paths and Thresholds
CACHE_DIR        = "data/cache"
CACHE_TTL_SECS   = 3600          # 1 hour default TTL
DB_PATH          = "data/fitness_bridge.db"

# Memory & Analysis Constants
SHORT_TERM_WINDOW   = 8           # Last N messages kept verbatim
READINESS_HIGH      = 420         # Minutes (7h sleep)
READINESS_MODERATE  = 300         # Minutes (5h sleep)
LOAD_OVERREACH_PCT  = 150         # % of baseline weekly volume

# Background sync interval (seconds)
BACKGROUND_SYNC_INTERVAL = int(os.getenv("BACKGROUND_SYNC_INTERVAL", str(2 * 60 * 60)))


def validate_config() -> list[str]:
    """Check required environment variables at startup. Returns list of warnings."""
    warnings = []
    # Strava — required for workout sync
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET:
        warnings.append("Strava client credentials (STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET) not set — workout sync will fail.")
    if not STRAVA_REFRESH_TOKEN:
        warnings.append("STRAVA_REFRESH_TOKEN not set — Strava token refresh will fail.")
    # Fitbit — required for biometrics + activity sync
    if not FITBIT_CLIENT_ID or not FITBIT_CLIENT_SECRET:
        warnings.append("Fitbit client credentials (FITBIT_CLIENT_ID, FITBIT_CLIENT_SECRET) not set — biometric sync will fail.")
    if not FITBIT_REFRESH_TOKEN:
        warnings.append("FITBIT_REFRESH_TOKEN not set — Fitbit token refresh will fail.")
    return warnings
