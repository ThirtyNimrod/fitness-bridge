"""
Test Suite: Phase 07 - Agent Layer
Coverage:
- Tests successful compilation of the LangGraph AI routing core.
- Verifies that the AgentState structure dictates the expected schema (intent, session_id, tool_data).
- Confirms the correct categories and signatures are bound to the intent router (readiness, progress, coach).
- Asserts that all downstream data fetch tools contain valid Langchain schemas and proper LLM descriptions.
"""

import os
import sys
import pytest
import json
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

import config
from src.utils.database import init_db


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "DB_PATH", db_file)
    import src.utils.database as db_module
    monkeypatch.setattr(db_module, "DB_PATH", db_file)
    init_db()
    yield db_file


class TestGraphCompilation:
    def test_build_graph_compiles_without_error(self):
        from src.agents.router import build_graph
        app = build_graph()
        assert app is not None

    def test_compiled_graph_is_invocable(self):
        from src.agents.router import build_graph
        app = build_graph()
        assert callable(getattr(app, "invoke", None))


class TestAgentState:
    def test_state_typeddict_has_required_keys(self):
        from src.agents.state import AgentState
        keys = AgentState.__annotations__.keys()
        for required in ["messages", "session_id", "intent", "system_context", "tool_data"]:
            assert required in keys, f"AgentState is missing key: {required}"

    def test_intent_type_is_correct(self):
        from src.agents.state import IntentType
        import typing
        args = getattr(IntentType, "__args__", None)
        assert args is not None
        assert "readiness" in args
        assert "progress" in args
        assert "coach" in args
        assert "general" in args


class TestToolDefinitions:
    def test_readiness_tools_are_defined(self):
        from src.agents.tools.readiness_tools import readiness_tools
        assert isinstance(readiness_tools, list)
        assert len(readiness_tools) >= 2

    def test_progress_tools_are_defined(self):
        from src.agents.tools.progress_tools import progress_tools
        assert isinstance(progress_tools, list)
        assert len(progress_tools) >= 4

    def test_coach_tools_are_defined(self):
        from src.agents.tools.coach_tools import coach_tools
        assert isinstance(coach_tools, list)
        assert len(coach_tools) >= 1

    def test_all_tools_have_name_and_description(self):
        from src.agents.tools.readiness_tools import readiness_tools
        from src.agents.tools.progress_tools import progress_tools
        from src.agents.tools.coach_tools import coach_tools
        all_tools = readiness_tools + progress_tools + coach_tools
        for tool in all_tools:
            assert hasattr(tool, "name"), f"Tool missing .name"
            assert hasattr(tool, "description"), f"Tool {tool.name} missing .description"
            assert len(tool.description.strip()) > 10, f"Tool {tool.name} has empty description"


class TestSharedLLM:
    def test_shared_llm_factory_reuses_instance(self):
        from src.agents.llm import get_llm
        llm_a = get_llm(temperature=0.1)
        llm_b = get_llm(temperature=0.1)
        assert llm_a is llm_b


class TestDeterministicIntegration:
    @patch('src.sync.engine.StravaClient.__init__', return_value=None)
    @patch('src.sync.engine.FitbitClient.__init__', return_value=None)
    def test_sync_dataset_tools_contract(self, mock_fitbit_init, mock_strava_init):
        from src.sync.engine import SyncEngine
        from src.analysis.dataset import build_dataset
        from src.agents.tools.progress_tools import get_weekly_load
        from src.agents.tools.coach_tools import get_full_context

        engine = SyncEngine()
        engine.strava = MagicMock()
        engine.fitbit = MagicMock()

        engine.strava.get_activities.return_value = [
            {"id": 9001, "start_date_local": "2026-03-28T10:00:00Z", "elapsed_time": 3600, "name": "Strength Session"}
        ]
        engine.strava.get_activity_detail.return_value = {
            "id": 9001,
            "start_date_local": "2026-03-28T10:00:00Z",
            "elapsed_time": 3600,
            "name": "Strength Session",
            "description": "Squat\nSet 1: 100 kg x 5\nSet 2: 100 kg x 5"
        }
        engine.fitbit.get_sleep.return_value = {"summary": {"totalMinutesAsleep": 420, "efficiency": 90}}
        engine.fitbit.get_hrv.return_value = {"hrv": [{"value": {"dailyRmssd": 45.0}}]}
        engine.fitbit.get_resting_hr.return_value = 58

        with patch('src.sync.engine.get_last_synced', return_value=None), \
             patch('src.sync.engine.set_last_synced'):
            result = engine.sync(force=True)

        assert result["synced"] == 1
        assert result["errors"] == 0

        df = build_dataset(n_days=30)
        assert not df.empty

        weekly_payload = json.loads(get_weekly_load.invoke({}))
        assert "total_volume_kg" in weekly_payload
        assert "session_count" in weekly_payload

        coach_payload = json.loads(get_full_context.invoke({}))
        assert "readiness" in coach_payload
        assert "weekly_load" in coach_payload
        assert "acwr" in coach_payload
