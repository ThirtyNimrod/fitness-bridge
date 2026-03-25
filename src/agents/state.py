from typing import TypedDict, Annotated, Literal, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

IntentType = Literal["readiness", "progress", "coach", "general"]

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    intent: Optional[IntentType]
    system_context: str
    tool_data: dict
    final_response: Optional[str]
