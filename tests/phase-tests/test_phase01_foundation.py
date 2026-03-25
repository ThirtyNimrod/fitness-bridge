"""
Test Suite: Phase 01 - Foundation & Local Storage
Coverage: 
- Validates core configurations (DB_PATH, CACHE_DIR, variables) are loaded correctly.
- Tests SQLite database initialization and local persistence (sessions, chat history, semantic facts).
- Validates that the DiskCache singleton mechanism properly caches intensive function calls.
These tests verify that the project can accurately read, write, and memorize its own functional states.
"""

import os
import sys
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

import config
from src.utils.database import (
    init_db, create_session, get_sessions, save_message,
    get_chat_history, get_full_history, upsert_fact, get_all_facts, delete_fact
)
from src.utils.cache import cached, get_cache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test gets its own isolated SQLite file."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "DB_PATH", db_file)
    import src.utils.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_file)
    init_db()
    yield db_file


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------

class TestConfig:
    def test_cache_dir_defined(self):
        assert config.CACHE_DIR is not None and len(config.CACHE_DIR) > 0

    def test_db_path_defined(self):
        assert config.DB_PATH is not None and len(config.DB_PATH) > 0

    def test_short_term_window_positive(self):
        assert config.SHORT_TERM_WINDOW > 0

    def test_ollama_model_defined(self):
        assert config.OLLAMA_MODEL is not None


# ---------------------------------------------------------------------------
# Database Tests
# ---------------------------------------------------------------------------

class TestDatabase:
    def test_db_file_created(self, fresh_db):
        assert os.path.exists(fresh_db)

    def test_create_and_retrieve_session(self):
        sid = create_session("My Workout Log")
        sessions = get_sessions()
        assert len(sessions) == 1
        assert sessions[0]["title"] == "My Workout Log"
        assert sessions[0]["id"] == sid

    def test_save_and_retrieve_messages(self):
        sid = create_session("S1")
        save_message(sid, "user", "How was my sleep?")
        save_message(sid, "assistant", "You slept 7.5 hours.")
        history = get_chat_history(sid, limit=10)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_summary_excluded_from_history(self):
        sid = create_session("S2")
        save_message(sid, "user", "Hi")
        save_message(sid, "assistant", "Hello")
        save_message(sid, "summary", "A summary row")
        history = get_chat_history(sid, limit=10)
        roles = [m["role"] for m in history]
        assert "summary" not in roles
        assert len(history) == 2

    def test_short_term_window_limit(self):
        sid = create_session("S3")
        for i in range(20):
            save_message(sid, "user", f"msg {i}")
        history = get_chat_history(sid, limit=config.SHORT_TERM_WINDOW)
        assert len(history) == config.SHORT_TERM_WINDOW

    def test_upsert_and_retrieve_fact(self):
        upsert_fact("goal", "hypertrophy")
        facts = get_all_facts()
        assert facts["goal"] == "hypertrophy"

    def test_upsert_overwrites_existing_fact(self):
        upsert_fact("goal", "strength")
        upsert_fact("goal", "endurance")
        facts = get_all_facts()
        assert facts["goal"] == "endurance"

    def test_delete_fact(self):
        upsert_fact("injury", "left shoulder")
        delete_fact("injury")
        facts = get_all_facts()
        assert "injury" not in facts


# ---------------------------------------------------------------------------
# Cache Tests
# ---------------------------------------------------------------------------

_call_count = 0

@cached(ttl=60)
def _cached_fn(x):
    global _call_count
    _call_count += 1
    return x * 3


class TestCache:
    def setup_method(self):
        global _call_count
        _call_count = 0
        get_cache().clear()

    def test_cache_returns_correct_value(self):
        assert _cached_fn(4) == 12

    def test_cache_hit_on_repeated_call(self):
        _cached_fn(7)
        _cached_fn(7)
        assert _call_count == 1

    def test_cache_miss_on_different_arg(self):
        _cached_fn(1)
        _cached_fn(2)
        assert _call_count == 2

    def test_get_cache_returns_instance(self):
        cache = get_cache()
        assert cache is not None
