# Scripts

Helper scripts for setting up and maintaining the Fitness Bridge AI application.

---

## Overview

| Script | When to run |
|---|---|
| [`SETUP.bat`](#setupbat) | **Once** — first-time Python environment setup |
| [`GET_TOKENS.ps1`](#get_tokensps1) | **Once** — first-time API credential setup (both services) |
| [`REFRESH_STRAVA.ps1`](#refresh_stravaps1) | **As needed** — re-authorize Strava when tokens break |
| [`REFRESH_FITBIT.ps1`](#refresh_fitbitps1) | **As needed** — re-authorize Fitbit when tokens break |
| [`run_tests.py`](#run_testspy) | **Dev** — run all phase tests in order |
| [`check_app_log.py`](#check_app_logpy--test_logpy) | **Dev** — verify logger is working |
| [`test_log.py`](#check_app_logpy--test_logpy) | **Dev** — print the active log directory path |

---

## SETUP.bat

**Run once after cloning the repo.**

Creates a `.venv` virtual environment, installs all dependencies from `requirements.txt`, and copies `.env.example` → `.env` if no `.env` exists yet.

```bat
scripts\SETUP.bat
```

---

## GET_TOKENS.ps1

**Run once after SETUP.bat** to obtain your initial API tokens for both Strava and Fitbit.

Guides you step-by-step through:
1. Entering your Strava Client ID + Secret → opens browser for OAuth → saves `STRAVA_REFRESH_TOKEN`
2. Entering your Fitbit Client ID + Secret → opens browser for OAuth → saves `FITBIT_ACCESS_TOKEN` + `FITBIT_REFRESH_TOKEN`

```powershell
.\scripts\GET_TOKENS.ps1
```

After it completes, it prints the exact expiry times for your access tokens and tells you when you'd need to re-authorize.

> **Note:** You should not need to run this again unless you want to start completely fresh. For day-to-day token issues, use the individual `REFRESH_*.ps1` scripts below.

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
App starts
  └─► StravaClient / FitbitClient check token expiry
        └─► If expired → call refresh endpoint → write new tokens to .env + os.environ
              └─► Subsequent requests use the new access token
```

You only need to run a refresh script when:
- The **refresh token** itself is invalid (revoked, expired, or from a broken initial auth)
- You see `401` errors in the logs **after** the app has already attempted a token refresh

The **Settings → 🔑 Token Expiry** section in the UI shows live expiry status for both services.

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
Authorization codes from both Strava and Fitbit are **very short-lived** (30 seconds for Strava, ~10 minutes for Fitbit). Once the browser redirects, copy the code from the URL immediately and paste it before doing anything else.

### "Python exchange failed" (Strava)
Make sure the `.venv` has been set up (`SETUP.bat`) before running the token script. The Strava script uses the venv Python to avoid TLS issues with PowerShell's `Invoke-WebRequest`.

### Fitbit redirect URI mismatch
The redirect URI must be **exactly** `http://localhost:8501/` (with trailing slash) in your [Fitbit app settings](https://dev.fitbit.com/apps). If it doesn't match, the OAuth flow will fail.

### Still getting 401 after running the script?
Restart the Streamlit app completely (`Ctrl+C` then `streamlit run app.py`). The updated tokens in `.env` are loaded at startup and kept live in `os.environ` during the run.
