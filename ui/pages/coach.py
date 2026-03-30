import streamlit as st

from src.utils.database import create_session, get_sessions
from src.utils.logger import ui_logger
from ui.chat import render_chat


def _ensure_session() -> str:
    if "session_id" not in st.session_state:
        st.session_state.session_id = create_session("Initial Session")
    return st.session_state.session_id


def _render_session_controls():
    current_session_id = _ensure_session()
    sessions = get_sessions()

    if not sessions:
        st.session_state.session_id = create_session("Initial Session")
        return st.session_state.session_id

    session_dict = {session["id"]: session["title"] for session in sessions}
    session_ids = list(session_dict.keys())
    selected_index = session_ids.index(current_session_id) if current_session_id in session_dict else 0

    st.header("AI Coach")
    selected_id = st.selectbox(
        "Chat session",
        options=session_ids,
        format_func=lambda value: session_dict[value],
        index=selected_index,
    )
    st.session_state.session_id = selected_id
    st.caption(session_dict.get(st.session_state.session_id, "Session"))
    if st.button("+ New Chat", use_container_width=True):
        st.session_state.session_id = create_session("New Session")
        ui_logger.info(f"Created new chat session: {st.session_state.session_id}")
        st.rerun()

    st.divider()

    return st.session_state.session_id


render_chat(_render_session_controls())