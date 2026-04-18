# Scripts

Helper scripts for setting up and maintaining the Fitness Bridge AI application.

---

## Overview

| Script | When to run |
|---|---|
| [`SETUP.bat`](#setupbat) | **Once** — first-time Python environment setup |
| [`setup_tokens.py`](#setup_tokenspy) | **Once** — first-time API credential setup (saves to DB vault) |
| [`GET_TOKENS.ps1`](#get_tokensps1) | **Once** — legacy PowerShell OAuth setup (writes to `.env`) |
| [`REFRESH_STRAVA.ps1`](#refresh_stravaps1) | **As needed** — re-authorize Strava when tokens break |
| [`REFRESH_FITBIT.ps1`](#refresh_fitbitps1) | **As needed** — re-authorize Fitbit when tokens break |
| [`run_tests.py`](#run_testspy) | **Dev** — run all phase tests in order |
| [`clear_chats.py`](#clear_chatspy) | **Dev** — clear chat history from the database |

---

## SETUP.bat

**Run once after cloning the repo.**

Creates a `.venv` virtual environment, installs all dependencies from `requirements.txt`, and copies `.env.example` → `.env` if no `.env` exists yet.

```bat
scripts\SETUP.bat
```

---

## setup_tokens.py

**Recommended.** Run once after SETUP.bat to obtain your initial API tokens for Strava, Fitbit, and Spotify.

This Python script:
1. Opens your browser for each provider's OAuth flow
2. Runs a local callback server to capture the authorization code automatically
3. Saves all tokens directly to the **SQLite database vault** (`api_tokens` table)

```bash
python scripts/setup_tokens.py
```

No copy-pasting URLs required — the redirect is captured for you.

---

## GET_TOKENS.ps1 (Legacy)

**Alternative to `setup_tokens.py`.** PowerShell-native OAuth setup that writes tokens to `.env` instead of the database.

Use this only if you prefer PowerShell or encounter issues with the Python utility.

```powershell
.\scripts\GET_TOKENS.ps1
```

> **Note:** Tokens written to `.env` by this script will be picked up by the app as a fallback if the database vault is empty.

---

## REFRESH_STRAVA.ps1

**Run when Strava gives persistent `401 Unauthorized` errors** that don't resolve after restarting the app.

- Reads `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` automatically from `.env` — you only need to paste the OAuth code from the browser.
- Opens the Strava authorization URL in your default browser.
- Writes fresh `STRAVA_REFRESH_TOKEN`, `STRAVA_ACCESS_TOKEN`, and `STRAVA_TOKEN_EXPIRES_AT` to `.env`.
- The Strava **refresh token never expires** unless you revoke app access on Strava — so you should rarely need this.

```powershell
.\scripts\REFRESH_STRAVA.ps1
```

### When to run

| Symptom | Action |
|---|---|
| Persistent `401` on Strava API calls after app restart | Run this script |
| You revoked the app on [strava.com/settings/apps](https://www.strava.com/settings/apps) | Run this script |
| You changed your Strava password | Run this script |
| App refreshes tokens successfully but still gets `401` | Run this script |

### Variables written to `.env`

| Variable | Description |
|---|---|
| `STRAVA_REFRESH_TOKEN` | Long-lived — used by the app to auto-refresh access tokens |
| `STRAVA_ACCESS_TOKEN` | Short-lived (~6 hours) — refreshed automatically while app runs |
| `STRAVA_TOKEN_EXPIRES_AT` | Unix timestamp of access token expiry |

---

## REFRESH_FITBIT.ps1

**Run when Fitbit gives persistent `401 Unauthorized` errors** that don't resolve after restarting the app, or when your Fitbit refresh token has expired (~8 months of inactivity).

- Reads `FITBIT_CLIENT_ID` and `FITBIT_CLIENT_SECRET` automatically from `.env`.
- Opens the Fitbit authorization URL in your default browser.
- Writes fresh `FITBIT_ACCESS_TOKEN`, `FITBIT_REFRESH_TOKEN`, and `FITBIT_TOKEN_EXPIRES_AT` to `.env`.

```powershell
.\scripts\REFRESH_FITBIT.ps1
```

### When to run

| Symptom | Action |
|---|---|
| Persistent `401` on Fitbit API calls after app restart | Run this script |
| You revoked the app on [dev.fitbit.com](https://dev.fitbit.com/apps) | Run this script |
| Fitbit refresh token hasn't been used in ~8 months | Run this script |
| You changed your Fitbit account password | Run this script |

### Variables written to `.env`

| Variable | Description |
|---|---|
| `FITBIT_ACCESS_TOKEN` | Short-lived (~8 hours) — refreshed automatically while app runs |
| `FITBIT_REFRESH_TOKEN` | Long-lived (~8 months) — used to get new access tokens |
| `FITBIT_TOKEN_EXPIRES_AT` | Unix timestamp of access token expiry |

---

## How token refresh works (no script needed day-to-day)

The app manages tokens automatically while it's running:

```
App starts (python main.py)
  └─► StravaClient / FitbitClient load tokens from DB vault
       └─► (Falls back to .env if vault is empty)
        └─► If expired → call refresh endpoint → save new tokens to DB vault
              └─► Subsequent requests use the new access token
```

You only need to run a refresh script when:
- The **refresh token** itself is invalid (revoked, expired, or from a broken initial auth)
- You see `401` errors in the logs **after** the app has already attempted a token refresh

The `/api/tokens/status` endpoint shows the vault status for all providers.

---

## run_tests.py

**Runs all phase tests (Phase 00–08) in order**, stopping on the first failure. Uses `os.path.dirname(__file__)` to auto-resolve the project root, so it works correctly from the `scripts/` directory.

```bash
python scripts/run_tests.py
```

Equivalent to running each `pytest tests/phase-tests/test_phaseXX_*.py` in sequence, but stops immediately if a phase fails — preventing later phases from running against a broken foundation.

---

## check_app_log.py / test_log.py

**Development utilities** for verifying the logging system is initialised correctly. Both scripts write a test log entry through both `app_logger` and `ui_logger` and print the active log directory path.

```bash
# From project root:
python scripts/check_app_log.py
python scripts/test_log.py
```

Useful when debugging logging issues (missing log files, wrong directory, etc.).

---

## Troubleshooting

### "The auth code has expired"
Authorization codes from both Strava and Fitbit are **very short-lived** (30 seconds for Strava, ~10 minutes for Fitbit). The `setup_tokens.py` script captures them automatically via a local server, but if using the PowerShell scripts, paste the code immediately.

### "Python exchange failed" (Strava)
Make sure the `.venv` has been set up (`SETUP.bat`) before running the token script.

### Fitbit redirect URI mismatch
The redirect URI must match your [Fitbit app settings](https://dev.fitbit.com/apps). `setup_tokens.py` uses `http://127.0.0.1:8000/callback`.

### Still getting 401 after running the script?
Restart the FastAPI backend (`Ctrl+C` then `python main.py`). Check the database vault with `sqlite3 data/fitness_bridge.db "SELECT provider, CASE WHEN refresh_token IS NOT NULL THEN 'present' ELSE 'missing' END FROM api_tokens;"`
