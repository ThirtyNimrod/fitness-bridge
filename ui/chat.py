import streamlit as st
import re
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk
from src.memory.manager import MemoryManager
from src.guardrails.input_guard import InputGuardrail
from src.guardrails.output_guard import OutputGuardrail
from src.agents.router import build_graph, llm
from src.agents.state import AgentState
from src.utils.logger import ui_logger

manager = MemoryManager()
input_guardrail = InputGuardrail()
output_guardrail = OutputGuardrail()

MAX_CHAT_INPUT_CHARS = 1000
MAX_RESPONSE_CHARS = 6000

# Agent node names that may stream LLM tokens.
_AGENT_NODES = {"readiness_agent", "progress_agent", "coach_agent"}


def _sanitize_text(value: str, max_len: int) -> str:
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value or "")
    return cleaned[:max_len].strip()


@st.cache_resource
def get_graph():
    return build_graph()

compiled_graph = get_graph()


def _build_initial_state(query: str, session_id: str) -> AgentState:
    context = manager.build_context(session_id)
    lc_messages = []
    for msg in context["recent_messages"]:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))
    lc_messages.append(HumanMessage(content=query))
    return AgentState(
        messages=lc_messages,
        session_id=session_id,
        intent=None,
        tool_iterations=0,
        system_context=context["system_context"],
        tool_data={},
        final_response=None,
    )


def run_agent(query: str, session_id: str) -> str:
    """Non-streaming path — returns the full response as a string."""
    query = _sanitize_text(query, MAX_CHAT_INPUT_CHARS)
    if not query:
        return "Please enter a valid fitness-related question."

    allowed, reason = input_guardrail.check(query, llm=llm)
    if not allowed:
        return f"I can only help with fitness and training questions. ({reason})"

    initial_state = _build_initial_state(query, session_id)

    try:
        result = compiled_graph.invoke(initial_state)
        response_text = _sanitize_text(result["messages"][-1].content, MAX_RESPONSE_CHARS)
        tool_data = result.get("tool_data", {})

        valid, issue = output_guardrail.validate_response(response_text, tool_data)
        if not valid:
            ui_logger.warning(f"[GUARDRAIL WARNING] {issue}")

        manager.save_turn(session_id, query, response_text)
        manager.maybe_summarise(session_id, llm)
        if manager.should_extract_facts(session_id):
            manager.extract_and_store_facts(response_text, llm)

        return response_text
    except Exception as e:
        ui_logger.exception(f"Chat generation failure for session {session_id}: {e}")
        return "An internal error occurred while generating your response. Please try again."


def stream_agent(query: str, session_id: str, placeholder):
    """
    Streaming path — drives compiled_graph.stream() and pushes tokens to *placeholder*
    as each agent node emits AIMessageChunk objects.

    Returns the final complete response string so callers can still access it for
    post-processing (guardrails, memory save, fact extraction).
    """
    query = _sanitize_text(query, MAX_CHAT_INPUT_CHARS)
    if not query:
        placeholder.markdown("Please enter a valid fitness-related question.")
        return "Please enter a valid fitness-related question."

    allowed, reason = input_guardrail.check(query, llm=llm)
    if not allowed:
        msg = f"I can only help with fitness and training questions. ({reason})"
        placeholder.markdown(msg)
        return msg

    initial_state = _build_initial_state(query, session_id)

    accumulated = ""
    final_tool_data: dict = {}
    final_state = None

    try:
        # Use both stream modes in a single pass:
        # - "messages": token chunks for live UI updates
        # - "values": final state snapshot for tool_data/guardrails
        for mode, data in compiled_graph.stream(
            initial_state,
            stream_mode=["messages", "values"],
        ):
            if mode == "messages":
                chunk, metadata = data
                if (
                    isinstance(chunk, AIMessageChunk)
                    and metadata.get("langgraph_node") in _AGENT_NODES
                    and chunk.content
                ):
                    accumulated += chunk.content
                    safe = _sanitize_text(accumulated, MAX_RESPONSE_CHARS)
                    placeholder.markdown(safe + "▌")
            elif mode == "values" and isinstance(data, dict):
                final_state = data

        if final_state is None:
            # Safety fallback if stream values are unavailable.
            final_state = compiled_graph.invoke(initial_state)

        final_tool_data = final_state.get("tool_data", {})

        # If streaming produced no tokens (e.g. tool-only response), fall back to
        # the full response from the final state.
        if not accumulated.strip():
            accumulated = final_state["messages"][-1].content

        response_text = _sanitize_text(accumulated, MAX_RESPONSE_CHARS)
        placeholder.markdown(response_text)

        valid, issue = output_guardrail.validate_response(response_text, final_tool_data)
        if not valid:
            ui_logger.warning(f"[GUARDRAIL WARNING] {issue}")

        manager.save_turn(session_id, query, response_text)
        manager.maybe_summarise(session_id, llm)
        if manager.should_extract_facts(session_id):
            manager.extract_and_store_facts(response_text, llm)

        return response_text

    except Exception as e:
        ui_logger.exception(f"Streaming generation failure for session {session_id}: {e}")
        # Gracefully fall back to non-streaming invoke on any stream failure.
        try:
            fallback = run_agent(query, session_id)
            placeholder.markdown(fallback)
            return fallback
        except Exception:
            err = "An internal error occurred while generating your response. Please try again."
            placeholder.markdown(err)
            return err


def render_chat(session_id):
    history = manager.short_term.get(session_id)

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your training..."):
        prompt = _sanitize_text(prompt, MAX_CHAT_INPUT_CHARS)
        if not prompt:
            st.warning("Please enter a valid message.")
            return

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            with st.spinner("Analyzing..."):
                stream_agent(prompt, session_id, placeholder)
            st.rerun()
