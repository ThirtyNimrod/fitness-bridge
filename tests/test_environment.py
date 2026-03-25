"""
Test Suite: Environment Setup Validation
Validates that all required packages are installed and the .env file
contains the necessary configuration keys. Run this FIRST.
"""

import sys
import os
import importlib
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

REQUIRED_PACKAGES = [
    "streamlit",
    "langchain",
    "langgraph",
    "langchain_ollama",
    "pandas",
    "diskcache",
    "tenacity",
    "pydantic",
    "requests",
    "dotenv",
]

REQUIRED_ENV_KEYS = [
    "STRAVA_CLIENT_ID",
    "STRAVA_CLIENT_SECRET",
    "STRAVA_REFRESH_TOKEN",
    "FITBIT_CLIENT_ID",
    "FITBIT_CLIENT_SECRET",
    "FITBIT_ACCESS_TOKEN",
    "FITBIT_REFRESH_TOKEN",
]

OPTIONAL_ENV_KEYS = [
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
]

class TestEnvironmentPackages:
    @pytest.mark.parametrize("package", REQUIRED_PACKAGES)
    def test_package_installed(self, package):
        """Verify all required Python packages can be imported."""
        try:
            importlib.import_module(package)
        except ImportError:
            pytest.fail(f"Required package '{package}' is not installed. Run: pip install -r requirements.txt")

class TestEnvironmentDotenv:
    @pytest.fixture(autouse=True)
    def load_env(self):
        from dotenv import load_dotenv
        env_path = os.path.join(BASE_DIR, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)

    def test_env_file_exists(self):
        """Verify a .env file exists (not just .env.example)."""
        env_path = os.path.join(BASE_DIR, ".env")
        assert os.path.exists(env_path), (
            ".env file is missing. Copy .env.example to .env and fill in your API credentials."
        )

    @pytest.mark.parametrize("key", REQUIRED_ENV_KEYS)
    def test_required_env_key_set(self, key):
        """Verify each required environment variable is populated."""
        value = os.getenv(key)
        assert value, f"Required env var '{key}' is not set or is empty in your .env file."

    @pytest.mark.parametrize("key", OPTIONAL_ENV_KEYS)
    def test_optional_env_key_set(self, key):
        """Verify optional env vars have fallback values if missing."""
        from dotenv import load_dotenv
        load_dotenv(os.path.join(BASE_DIR, ".env"))
        import config
        val = getattr(config, key, None)
        assert val is not None, f"Config key '{key}' has no fallback value in config.py."

class TestProjectStructure:
    @pytest.mark.parametrize("path", [
        "config.py",
        "app.py",
        "requirements.txt",
        ".env.example",
        "src/utils/cache.py",
        "src/utils/database.py",
        "src/clients/strava_client.py",
        "src/clients/fitbit_client.py",
        "src/parsers/hevy_parser.py",
        "src/analysis/readiness.py",
        "src/analysis/load.py",
        "src/analysis/dataset.py",
        "src/memory/store.py",
        "src/memory/manager.py",
        "src/guardrails/input_guard.py",
        "src/guardrails/output_guard.py",
        "src/agents/state.py",
        "src/agents/router.py",
        "src/agents/readiness_agent.py",
        "src/agents/progress_agent.py",
        "src/agents/coach_agent.py",
        "src/agents/tools/readiness_tools.py",
        "src/agents/tools/progress_tools.py",
        "src/agents/tools/coach_tools.py",
        "ui/dashboard.py",
        "ui/chat.py",
    ])
    def test_file_exists(self, path):
        """Verify all expected implementation files exist."""
        full_path = os.path.join(BASE_DIR, path)
        assert os.path.exists(full_path), f"Expected file is missing: {path}"
