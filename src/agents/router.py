import json
import os
import threading
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage
from src.agents.llm import get_llm
from src.agents.state import AgentState
from src.agents.readiness_agent import readiness_agent_node
from src.agents.progress_agent import progress_agent_node
from src.agents.coach_agent import coach_agent_node

from src.agents.tools.readiness_tools import readiness_tools
from src.agents.tools.progress_tools import progress_tools
from src.agents.tools.coach_tools import coach_tools

llm = get_llm(temperature=0.0)
MAX_TOOL_LOOPS = max(1, int(os.getenv("AGENT_MAX_TOOL_LOOPS", "5")))

# ── Routing metrics ───────────────────────────────────────────────────────────
_metrics_lock = threading.Lock()
_routing_metrics: dict[str, int] = {
    "heuristic_hits": 0,
    "llm_fallbacks": 0,
    "total_routed": 0,
}


def get_routing_metrics() -> dict:
    """Return a snapshot of routing counter values (thread-safe copy)."""
    with _metrics_lock:
        return dict(_routing_metrics)


def reset_routing_metrics() -> None:
    """Reset all routing counters to zero (useful for testing)."""
    with _metrics_lock:
        for k in _routing_metrics:
            _routing_metrics[k] = 0

_READINESS_HINTS = {
    "readiness", "recover", "recovery", "sleep", "hrv", "resting hr", "resting heart",
    "fatigue", "tired", "train today", "should i train", "deload",
}
_PROGRESS_HINTS = {
    "progress", "trend", "history", "volume", "acwr", "workout history", "past workouts",
    "exercise progress", "plateau", "stagnat",
}
_COACH_HINTS = {
    "coach", "advice", "improve", "plan", "program", "what should i do", "recommend",
    "increase", "reduce", "change",
}
_GENERAL_HINTS = {"hello", "hi", "hey", "thanks", "thank you"}

ROUTER_PROMPT = """
You are a routing classifier for a fitness coaching app.
Classify the user's intent into exactly one category:

- readiness: questions about today's recovery, sleep quality, whether to train
- progress: questions about past workouts, volume trends, exercise history
- coach: requests for coaching advice, what to change, how to improve
- general: greetings, clarifications, anything else

User query: {query}

Respond with only the category name. Nothing else.
"""

def router_node(state: AgentState):
    query = state["messages"][-1].content

    intent_str = _heuristic_intent(query)
    with _metrics_lock:
        _routing_metrics["total_routed"] += 1
        if intent_str is None:
            _routing_metrics["llm_fallbacks"] += 1
        else:
            _routing_metrics["heuristic_hits"] += 1

    if intent_str is None:
        intent_str = llm.invoke(ROUTER_PROMPT.format(query=query)).content.strip().lower()

    if intent_str not in ["readiness", "progress", "coach", "general"]:
        intent_str = "general"

    # Compute the target agent name for UI visibility
    _agent_map = {
        "readiness": "Readiness Specialist",
        "progress": "Progress Analyst",
        "coach": "Coach",
        "general": "Coach",
    }
    routed_to = _agent_map.get(intent_str, "Coach")

    return {"intent": intent_str, "tool_iterations": 0, "routed_to": routed_to}


def _heuristic_intent(query: str):
    """Fast deterministic routing for common intents; returns None if ambiguous."""
    text = (query or "").strip().lower()
    if not text:
        return "general"

    # Keep short conversational messages away from unnecessary router LLM calls.
    if len(text.split()) <= 3 and any(token in text for token in _GENERAL_HINTS):
        return "general"

    readiness_hits = sum(1 for hint in _READINESS_HINTS if hint in text)
    progress_hits = sum(1 for hint in _PROGRESS_HINTS if hint in text)
    coach_hits = sum(1 for hint in _COACH_HINTS if hint in text)

    scores = {
        "readiness": readiness_hits,
        "progress": progress_hits,
        "coach": coach_hits,
    }
    top_intent = max(scores, key=scores.get)
    top_score = scores[top_intent]

    if top_score == 0:
        return None

    # If two categories tie at the same confidence, fall back to LLM classifier.
    if list(scores.values()).count(top_score) > 1:
        return None

    return top_intent

def route_to_agent(state: AgentState):
    intent = state.get("intent", "general")
    mapping = {
        "readiness": "readiness_agent",
        "progress":  "progress_agent",
        "coach":     "coach_agent",
        "general":   "coach_agent" 
    }
    agent = mapping.get(intent, "coach_agent")
    return agent

def route_tools(state: AgentState):
    if int(state.get("tool_iterations", 0)) >= MAX_TOOL_LOOPS:
        return END

    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END

def route_after_tools(state: AgentState):
    if int(state.get("tool_iterations", 0)) >= MAX_TOOL_LOOPS:
        return END

    intent = state.get("intent", "general")
    mapping = {
        "readiness": "readiness_agent",
        "progress":  "progress_agent",
        "coach":     "coach_agent",
        "general":   "coach_agent"
    }
    return mapping.get(intent, "coach_agent")

class InterceptingToolNode(ToolNode):
    def invoke(self, input, config=None, **kwargs):
        result = super().invoke(input, config=config, **kwargs)
        prior_iterations = 0
        if isinstance(input, dict):
            prior_iterations = int(input.get("tool_iterations", 0) or 0)
        result["tool_iterations"] = prior_iterations + 1
        
        new_data = {}
        if "messages" in result:
            for m in result["messages"]:
                if isinstance(m, ToolMessage):
                    try:
                        parsed = json.loads(m.content)
                        new_data[m.name] = parsed
                    except Exception:
                        pass
        
        if new_data:
            existing = input.get("tool_data", {}) if isinstance(input, dict) else {}
            updated = existing.copy()
            updated.update(new_data)
            result["tool_data"] = updated
            
        return result

def build_graph():
    graph = StateGraph(AgentState)

    all_tools = readiness_tools + progress_tools + coach_tools

    graph.add_node("router", router_node)
    graph.add_node("readiness_agent", readiness_agent_node)
    graph.add_node("progress_agent", progress_agent_node)
    graph.add_node("coach_agent", coach_agent_node)
    graph.add_node("tools", InterceptingToolNode(all_tools))

    graph.set_entry_point("router")
    
    graph.add_conditional_edges("router", route_to_agent, {
        "readiness_agent": "readiness_agent",
        "progress_agent":  "progress_agent",
        "coach_agent":     "coach_agent"
    })

    for agent in ["readiness_agent", "progress_agent", "coach_agent"]:
        graph.add_conditional_edges(agent, route_tools, {
            "tools": "tools",
            END: END
        })
        
    graph.add_conditional_edges("tools", route_after_tools, {
        "readiness_agent": "readiness_agent",
        "progress_agent":  "progress_agent",
        "coach_agent":     "coach_agent",
        END: END,
    })

    return graph.compile()
