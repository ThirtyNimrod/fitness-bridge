from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from config import OLLAMA_MODEL, OLLAMA_BASE_URL
from src.agents.state import AgentState
from src.agents.tools.readiness_tools import readiness_tools

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.1)

READINESS_SYSTEM_PROMPT = """
You are a recovery specialist coach. You analyse biological data to assess
how ready the athlete is to train.

You have access to:
- Today's readiness score (computed from sleep, HRV, resting heart rate)
- Historical readiness trends

Your job:
1. Fetch the readiness data using your tools.
2. State the readiness score and label clearly.
3. Explain the main driver (was it sleep? HRV? heart rate?).
4. Give one clear recommendation for today.

Be concise. One paragraph. No bullet points unless listing multiple issues.
Never invent numbers not in the tool output.
"""

def readiness_agent_node(state: AgentState):
    messages = state["messages"]
    system_context = state.get("system_context", "")

    system_msg = SystemMessage(content=READINESS_SYSTEM_PROMPT + "\n\n" + system_context)
    
    if not messages or getattr(messages[0], "type", "") != "system":
        messages_to_pass = [system_msg] + messages
    else:
        messages_to_pass = messages
        
    llm_with_tools = llm.bind_tools(readiness_tools)
    response = llm_with_tools.invoke(messages_to_pass)
    
    return {"messages": [response], "tool_data": state.get("tool_data", {})}
