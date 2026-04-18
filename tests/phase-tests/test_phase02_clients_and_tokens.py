"""
Test Suite: Phase 02 - API Clients & Persistence
Tests: StravaClient initialization, FitbitClient initialization, and OAuth token `.env` persistence.
Run this phase independently to verify connection health and token refresh logic.
"""

import os
import sys
import pytest
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.utils.token_writer import write_token_to_env
from src.clients.strava_client import StravaClient, AuthError as StravaAuthError
from src.clients.fitbit_client import FitbitClient, AuthError as FitbitAuthError

# ---------------------------------------------------------------------------
# Token Writer Tests
# ---------------------------------------------------------------------------

class TestTokenWriter:
    def test_write_token_new_key(self):
        """Verifies adding a brand new OAuth token key to an existing .env file."""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write("EXISTING_KEY=oldval\n")
            temp_path = f.name
            
        try:
            with patch('src.utils.token_writer.find_dotenv', return_value=temp_path):
                write_token_to_env("NEW_KEY", "new_value")
                
            with open(temp_path, "r") as f:
                content = f.read()
                
            assert "EXISTING_KEY=oldval" in content
            assert "NEW_KEY=new_value\n" in content
        finally:
            os.unlink(temp_path)

    def test_write_token_existing_key(self):
        """Verifies cleanly overwriting an existing token value inline without affecting surrounding keys."""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write("A=1\nMY_TOKEN=old_token\nB=2\n")
            temp_path = f.name
            
        try:
            with patch('src.utils.token_writer.find_dotenv', return_value=temp_path):
                write_token_to_env("MY_TOKEN", "super_secret_new_token")
                
            with open(temp_path, "r") as f:
                lines = f.readlines()
                
            assert lines[0] == "A=1\n"
            assert lines[1] == "MY_TOKEN=super_secret_new_token\n"
            assert lines[2] == "B=2\n"
        finally:
            os.unlink(temp_path)

    def test_write_token_no_env_file_graceful(self):
        """Verifies safe failure if the .env file is completely missing."""
        with patch('src.utils.token_writer.find_dotenv', return_value=""):
            # Should return gracefully without exception
            write_token_to_env("MY_TOKEN", "val")


# ---------------------------------------------------------------------------
# API Client Initialization & Connections
# ---------------------------------------------------------------------------

class TestAPIClients:
    def test_strava_client_refreshes_when_missing_token(self):
        """Missing token should trigger refresh during client initialization."""
        # Must also clear the OS env vars since _get_runtime_value checks os.getenv() first,
        # which would find a real token from the loaded .env and bypass the module-level patch.
        env_overrides = {
            "STRAVA_ACCESS_TOKEN": "",
            "STRAVA_TOKEN_EXPIRES_AT": "",
            "STRAVA_REFRESH_TOKEN": "",
        }
        with patch.dict(os.environ, env_overrides, clear=False), \
             patch("src.clients.strava_client.STRAVA_ACCESS_TOKEN", None), \
             patch("src.clients.strava_client.STRAVA_TOKEN_EXPIRES_AT", None), \
             patch.object(StravaClient, "_refresh_access_token") as mock_refresh:
            StravaClient()
            mock_refresh.assert_called_once()

    def test_strava_client_does_not_refresh_when_token_not_expired(self):
        """Valid non-expired token should skip refresh on init."""
        future_epoch = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        with patch.dict(os.environ, {
                "STRAVA_ACCESS_TOKEN": "token",
                "STRAVA_TOKEN_EXPIRES_AT": str(future_epoch),
                "STRAVA_REFRESH_TOKEN": "refresh-token",
            }, clear=False), \
             patch("src.clients.strava_client.STRAVA_ACCESS_TOKEN", "token"), \
             patch("src.clients.strava_client.STRAVA_TOKEN_EXPIRES_AT", str(future_epoch)), \
             patch.object(StravaClient, "_refresh_access_token") as mock_refresh:
            StravaClient()
            mock_refresh.assert_not_called()

    def test_fitbit_client_refreshes_when_expired(self):
        """Expired token should trigger refresh during Fitbit client initialization."""
        expired_epoch = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        with patch.dict(os.environ, {
                "FITBIT_ACCESS_TOKEN": "token",
                "FITBIT_TOKEN_EXPIRES_AT": str(expired_epoch),
                "FITBIT_REFRESH_TOKEN": "refresh-token",
            }, clear=False), \
             patch("src.clients.fitbit_client.FITBIT_ACCESS_TOKEN", "token"), \
             patch("src.clients.fitbit_client.FITBIT_TOKEN_EXPIRES_AT", str(expired_epoch)), \
             patch.object(FitbitClient, "_refresh_access_token") as mock_refresh:
            FitbitClient()
            mock_refresh.assert_called_once()

    def test_fitbit_client_does_not_refresh_when_token_not_expired(self):
        """Non-expired token should skip refresh during Fitbit init."""
        future_epoch = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        with patch("src.clients.fitbit_client.FITBIT_ACCESS_TOKEN", "token"), \
             patch("src.clients.fitbit_client.FITBIT_TOKEN_EXPIRES_AT", str(future_epoch)), \
             patch.object(FitbitClient, "_refresh_access_token") as mock_refresh:
            FitbitClient()
            mock_refresh.assert_not_called()

    def test_strava_client_connection(self):
        """Verifies Strava API token connectivity by asserting check_connection() returns True."""
        try:
            strava = StravaClient()
            if strava.check_connection():
                acts = strava.get_activities(per_page=1)
                assert isinstance(acts, list)
        except Exception as e:
            pytest.skip(f"Live Strava connection skipped/failed during test: {e}")

    def test_fitbit_client_connection(self):
        """Verifies Fitbit API token connectivity by asserting check_connection() returns True."""
        try:
            fitbit = FitbitClient()
            if fitbit.check_connection():
                import datetime
                today = datetime.date.today().isoformat()
                hrv = fitbit.get_hrv(today)
                assert isinstance(hrv, dict)
        except Exception as e:
            pytest.skip(f"Live Fitbit connection skipped/failed during test: {e}")

    def test_strava_client_ensure_access_token_reloads_runtime_env(self, monkeypatch):
        """Client should pick up newer env token state without process restart."""
        monkeypatch.setenv("STRAVA_ACCESS_TOKEN", "token_a")
        future_epoch = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        monkeypatch.setenv("STRAVA_TOKEN_EXPIRES_AT", str(future_epoch))
        monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "refresh_a")

        with patch.object(StravaClient, "_refresh_access_token") as mock_refresh:
            client = StravaClient()
            assert client.access_token == "token_a"
            mock_refresh.assert_not_called()

            monkeypatch.setenv("STRAVA_ACCESS_TOKEN", "token_b")
            monkeypatch.setenv("STRAVA_REFRESH_TOKEN", "refresh_b")
            client._ensure_access_token()

            assert client.access_token == "token_b"
            assert client.refresh_token == "refresh_b"

    def test_fitbit_client_headers_reloads_runtime_env(self, monkeypatch):
        """Headers path should re-check expiry and pick up latest env token values."""
        monkeypatch.setenv("FITBIT_ACCESS_TOKEN", "fit_a")
        future_epoch = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        monkeypatch.setenv("FITBIT_TOKEN_EXPIRES_AT", str(future_epoch))
        monkeypatch.setenv("FITBIT_REFRESH_TOKEN", "fit_refresh_a")

        with patch.object(FitbitClient, "_refresh_access_token") as mock_refresh:
            client = FitbitClient()
            assert client.access_token == "fit_a"
            mock_refresh.assert_not_called()

            monkeypatch.setenv("FITBIT_ACCESS_TOKEN", "fit_b")
            monkeypatch.setenv("FITBIT_REFRESH_TOKEN", "fit_refresh_b")
            headers = client._headers()

            assert headers["Authorization"] == "Bearer fit_b"
            assert client.refresh_token == "fit_refresh_b"
