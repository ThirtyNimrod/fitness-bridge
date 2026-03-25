from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from config import OLLAMA_MODEL, OLLAMA_BASE_URL
from src.agents.state import AgentState
from src.agents.tools.progress_tools import progress_tools

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.1)

PROGRESS_SYSTEM_PROMPT = """
You are a training progress analyst. You review workout history and load data.

You have access to:
- Recent workout sessions
- Weekly load and ACWR calculations
- Per-exercise progressive overload trends

Your job:
1. Fetch the relevant workout data using your tools.
2. Identify the key pattern in the data (trend, stagnation, spike).
3. State volume numbers accurately — never approximate.
4. Highlight one thing going well and one thing to watch.

Be specific. Reference actual exercises and actual numbers.
Never invent sets, reps, or weights not in the tool output.
"""

def progress_agent_node(state: AgentState):
    messages = state["messages"]
    system_context = state.get("system_context", "")

    system_msg = SystemMessage(content=PROGRESS_SYSTEM_PROMPT + "\n\n" + system_context)
    
    if not messages or getattr(messages[0], "type", "") != "system":
        messages_to_pass = [system_msg] + messages
    else:
        messages_to_pass = messages
        
    llm_with_tools = llm.bind_tools(progress_tools)
    response = llm_with_tools.invoke(messages_to_pass)
    
    return {"messages": [response], "tool_data": state.get("tool_data", {})}
