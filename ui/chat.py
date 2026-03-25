import streamlit as st
import json
from langchain_core.messages import HumanMessage, AIMessage
from src.memory.manager import MemoryManager
from src.guardrails.input_guard import InputGuardrail
from src.guardrails.output_guard import OutputGuardrail
from src.agents.router import build_graph, llm
from src.agents.state import AgentState
from src.utils.logger import ui_logger

manager = MemoryManager()
input_guardrail = InputGuardrail()
output_guardrail = OutputGuardrail()

@st.cache_resource
def get_graph():
    return build_graph()

compiled_graph = get_graph()

def run_agent(query, session_id):
    # Step 1: Input guardrail
    allowed, reason = input_guardrail.check(query, llm=llm)
    if not allowed:
        return f"I can only help with fitness and training questions. ({reason})"

    # Step 2: Build memory context
    context = manager.build_context(session_id)

    # Step 3: Build initial state
    lc_messages = []
    for msg in context["recent_messages"]:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))
            
    lc_messages.append(HumanMessage(content=query))

    initial_state = AgentState(
        messages=lc_messages,
        session_id=session_id,
        intent=None,
        system_context=context["system_context"],
        tool_data={},
        final_response=None
    )

    try:
        # Step 4: Run agent graph
        result = compiled_graph.invoke(initial_state)
        response_text = result["messages"][-1].content
        tool_data = result.get("tool_data", {})

        # Step 5: Output guardrail
        valid, issue = output_guardrail.validate_response(response_text, tool_data)
        if not valid:
            ui_logger.warning(f"[GUARDRAIL WARNING] {issue}")

        # Step 6: Save turn + extract facts
        manager.save_turn(session_id, query, response_text)
        manager.maybe_summarise(session_id, llm)
        manager.extract_and_store_facts(response_text, llm)

        return response_text
    except Exception as e:
        return f"An error occurred while generating a response: {str(e)}"

def render_chat(session_id):
    history = manager.short_term.get(session_id)

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your training..."):
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            with st.spinner("Analyzing..."):
                response = run_agent(prompt, session_id)
            placeholder.markdown(response)
            st.rerun()
