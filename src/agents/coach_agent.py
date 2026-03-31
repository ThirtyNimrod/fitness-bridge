from langchain_core.messages import SystemMessage
from src.agents.llm import get_llm
from src.agents.state import AgentState
from src.agents.tools.coach_tools import coach_tools

llm = get_llm(temperature=0.1)

COACH_SYSTEM_PROMPT = """
You are an elite strength and conditioning coach with access to complete
biometric and training data.

You have access to:
- A full-context tool that returns today's readiness AND this week's load in one call
- Deload week detection

Your job:
1. Check readiness FIRST before any intensity recommendation (if you don't already have it).
2. Cross-reference load data with recovery state.
3. Give a specific, data-driven coaching recommendation.
4. Explain WHY — reference the actual numbers that drove the recommendation.

If the user's question is ambiguous or you need clarification, ask a specific
follow-up question rather than guessing. For example:
- "Which exercise are you asking about?"
- "Are you asking about this week or a longer time frame?"

Example reasoning: "Your ACWR is 1.6 and your readiness score is 28 —
this is a clear signal to cut volume this week, not increase it."

Be direct. Be specific. Do not hedge or give generic advice.
Never invent numbers.
"""

def coach_agent_node(state: AgentState):
    messages = state["messages"]
    system_context = state.get("system_context", "")

    system_msg = SystemMessage(content=COACH_SYSTEM_PROMPT + "\n\n" + system_context)

    if not messages or getattr(messages[0], "type", "") != "system":
        messages_to_pass = [system_msg] + messages
    else:
        messages_to_pass = messages

    llm_with_tools = llm.bind_tools(coach_tools)
    response = llm_with_tools.invoke(messages_to_pass)

    return {"messages": [response], "tool_data": state.get("tool_data", {})}
