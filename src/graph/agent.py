import os
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from src.tools.fitness_tools import fitness_tools

# --- 1. Define State ---
class AgentState(TypedDict):
    messages: List[BaseMessage]
    user_id: str

# --- 2. Initialize LLM ---
# Ensure your .env has AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION
llm = AzureChatOpenAI(
    azure_deployment="gpt-4o",  # specific to your Azure setup
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    temperature=0
)

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(fitness_tools)

# --- 3. Define Nodes ---

def chatbot(state: AgentState):
    """The main LLM node."""
    messages = state['messages']
    
    # Add system prompt if it's the start of conversation
    if not isinstance(messages[0], SystemMessage):
        sys_msg = SystemMessage(content="""
            You are an elite Strength & Conditioning AI Coach using Hevy and Fitbit data.
            
            Your Goal: Optimize the user's training based on their biological state.
            
            Guidelines:
            1. ALWAYS check biological data (Fitbit) before suggesting high-intensity modifications.
            2. Use the 'get_recent_workouts' tool to understand context.
            3. If updating a routine, explain WHY based on the data (e.g., "Sleep was low, so I reduced volume").
            4. Be concise and encouraging.
        """)
        messages = [sys_msg] + messages
        
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# --- 4. Define Graph ---
from langgraph.prebuilt import ToolNode

graph_builder = StateGraph(AgentState)

# Nodes
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(fitness_tools))

# Edges
graph_builder.set_entry_point("chatbot")

def route_tools(state: AgentState):
    """Conditional edge to determine if tools should be called."""
    if state["messages"][-1].tool_calls:
        return "tools"
    return END

graph_builder.add_conditional_edges("chatbot", route_tools, {"tools": "tools", END: END})
graph_builder.add_edge("tools", "chatbot")

# Compile
fitness_agent = graph_builder.compile()