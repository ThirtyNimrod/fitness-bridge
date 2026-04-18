# Setup Guide — Fitness Bridge AI

Follow these instructions to configure your environment and connect your fitness APIs.

## 1. Prerequisites

- **Python 3.13+**: Ensure Python is installed and in your PATH.
- **Node.js 18+**: Required for the Next.js frontend.
- **Ollama**: Download and install [Ollama](https://ollama.com/) for local LLM execution.
- **API Credentials**:
    - [Strava API Application](https://www.strava.com/settings/api)
    - [Fitbit Developer Application](https://dev.fitbit.com/apps/new) (Use **Personal** app type for HRV access)

## 2. Environment Setup

Run the automated setup script to create a virtual environment and install dependencies:

```bash
scripts\SETUP.bat
```

For the frontend, install NPM packages:

```bash
cd frontend
npm install
cd ..
```

## 3. API Configuration

1. Copy `.env.example` to `.env` (handled by `SETUP.bat`).
2. Fill in your `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `FITBIT_CLIENT_ID`, and `FITBIT_CLIENT_SECRET` in the `.env` file.

## 4. Token Acquisition

The system uses a persistent **Database Token Vault** to manage OAuth lifecycle. Use the Python utility to obtain your initial tokens:

```bash
python scripts/setup_tokens.py
```

**What it does:**
1. Starts a temporary local server.
2. Opens your browser for Strava and Fitbit authorization.
3. Automatically captures the redirect codes.
4. Saves tokens directly into the `api_tokens` table in your local database.

## 5. Configuration Reference

| Variable | Description |
|---|---|
| `DB_PATH` | Path to the SQLite database (default: `data/fitness_bridge.db`) |
| `OLLAMA_MODEL` | The LLM model name (default: `qwen3.5:4b`) |
| `BACKGROUND_SYNC_INTERVAL` | Seconds between background syncs (default: `7200`) |
| `CACHE_DIR` | Directory for API result caching |
| `LANGSMITH_API_KEY` | (Optional) For tracing agent interactions |
| `NEXT_PUBLIC_API_URL` | Frontend pointer to the FastAPI backend (default: `http://localhost:8000`) |
