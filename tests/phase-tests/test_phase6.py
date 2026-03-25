"""
Test Suite: Phase 6 - Agent Layer
Tests: graph compilation, router node, state structure, tool execution shape.
"""

import os
import sys
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))


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
