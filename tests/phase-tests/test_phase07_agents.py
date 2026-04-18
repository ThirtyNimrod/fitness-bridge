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
from langgraph.graph import END
from langchain_core.messages import AIMessage, AIMessageChunk

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
        for required in ["messages", "session_id", "intent", "tool_iterations", "system_context", "tool_data"]:
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


class TestRouterLoopGuard:
    def test_route_tools_stops_after_max_loops(self):
        from src.agents import router

        state = {
            "messages": [AIMessage(content="tool", tool_calls=[{"name": "x", "args": {}, "id": "1"}])],
            "tool_iterations": router.MAX_TOOL_LOOPS,
        }
        decision = router.route_tools(state)
        assert decision == END

    def test_route_after_tools_stops_after_max_loops(self):
        from src.agents import router

        state = {"intent": "coach", "tool_iterations": router.MAX_TOOL_LOOPS}
        decision = router.route_after_tools(state)
        assert decision == END

    def test_intercepting_tool_node_increments_tool_iterations(self):
        from src.agents.router import InterceptingToolNode

        node = InterceptingToolNode([])
        with patch('src.agents.router.ToolNode.invoke', return_value={"messages": []}):
            result = node.invoke({"tool_iterations": 2, "tool_data": {}})
        assert result["tool_iterations"] == 3


class TestRouterHeuristics:
    def test_heuristic_intent_detects_readiness(self):
        from src.agents.router import _heuristic_intent

        intent = _heuristic_intent("Should I train today? My sleep and HRV are low")
        assert intent == "readiness"

    def test_heuristic_intent_detects_progress(self):
        from src.agents.router import _heuristic_intent

        intent = _heuristic_intent("Show my workout history and volume trend")
        assert intent == "progress"

    def test_heuristic_intent_returns_none_when_ambiguous(self):
        from src.agents.router import _heuristic_intent

        intent = _heuristic_intent("How is my progress and what should I change")
        assert intent is None

    def test_router_node_uses_heuristic_without_llm_call(self):
        from src.agents import router

        state = {"messages": [AIMessage(content="Hi")], "tool_iterations": 0}
        llm_mock = MagicMock()
        with patch('src.agents.router.llm', llm_mock):
            result = router.router_node(state)

        assert result["intent"] == "general"
        assert result["tool_iterations"] == 0
        llm_mock.invoke.assert_not_called()


class TestRoutingMetrics:
    def setup_method(self):
        from src.agents.router import reset_routing_metrics
        reset_routing_metrics()

    def test_heuristic_hit_increments_counters(self):
        from src.agents.router import router_node, get_routing_metrics

        state = {"messages": [AIMessage(content="Hi")], "tool_iterations": 0}
        router_node(state)
        m = get_routing_metrics()
        assert m["total_routed"] == 1
        assert m["heuristic_hits"] == 1
        assert m["llm_fallbacks"] == 0

    def test_llm_fallback_increments_counters(self):
        from src.agents import router

        llm_mock = MagicMock()
        llm_mock.invoke.return_value = MagicMock(content="coach")
        # Ambiguous query so heuristic returns None → LLM fallback
        state = {
            "messages": [AIMessage(content="How do I balance stress and training loads")],
            "tool_iterations": 0,
        }
        with patch("src.agents.router.llm", llm_mock):
            router.router_node(state)
        m = router.get_routing_metrics()
        assert m["total_routed"] == 1
        assert m["llm_fallbacks"] == 1
        assert m["heuristic_hits"] == 0

    def test_reset_clears_counters(self):
        from src.agents.router import router_node, get_routing_metrics, reset_routing_metrics

        state = {"messages": [AIMessage(content="Hi")], "tool_iterations": 0}
        router_node(state)
        assert get_routing_metrics()["total_routed"] == 1
        reset_routing_metrics()
        m = get_routing_metrics()
        assert m["total_routed"] == 0
        assert m["heuristic_hits"] == 0
        assert m["llm_fallbacks"] == 0

    def test_multiple_calls_accumulate(self):
        from src.agents.router import router_node, get_routing_metrics

        # "Hi" → general (heuristic hit)
        state = {"messages": [AIMessage(content="Hi")], "tool_iterations": 0}
        router_node(state)
        router_node(state)
        m = get_routing_metrics()
        assert m["total_routed"] == 2
        assert m["heuristic_hits"] == 2

    def test_get_routing_metrics_returns_copy(self):
        from src.agents.router import get_routing_metrics

        m1 = get_routing_metrics()
        m1["total_routed"] = 999
        m2 = get_routing_metrics()
        assert m2["total_routed"] == 0  # original dict unchanged
# TestChatStreaming removed (legacy UI only)




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
