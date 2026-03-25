import json
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage
from langchain_ollama import ChatOllama
from config import OLLAMA_MODEL, OLLAMA_BASE_URL
from src.agents.state import AgentState
from src.agents.readiness_agent import readiness_agent_node
from src.agents.progress_agent import progress_agent_node
from src.agents.coach_agent import coach_agent_node

from src.agents.tools.readiness_tools import readiness_tools
from src.agents.tools.progress_tools import progress_tools
from src.agents.tools.coach_tools import coach_tools

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.0)

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
    intent_str = llm.invoke(ROUTER_PROMPT.format(query=query)).content.strip().lower()

    if intent_str not in ["readiness", "progress", "coach", "general"]:
        intent_str = "general"

    return {"intent": intent_str}

def route_to_agent(state: AgentState):
    intent = state.get("intent", "general")
    mapping = {
        "readiness": "readiness_agent",
        "progress":  "progress_agent",
        "coach":     "coach_agent",
        "general":   "coach_agent" 
    }
    return mapping.get(intent, "coach_agent")

def route_tools(state: AgentState):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END

def route_after_tools(state: AgentState):
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
        "coach_agent":     "coach_agent"
    })

    return graph.compile()
