import streamlit as st

from src.utils.database import create_session, get_sessions, delete_session, rename_session
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

    # Session selector with rename/delete controls
    col_select, col_rename, col_delete = st.columns([6, 1, 1])
    with col_select:
        selected_id = st.selectbox(
            "Chat session",
            options=session_ids,
            format_func=lambda value: session_dict[value],
            index=selected_index,
        )
        st.session_state.session_id = selected_id

    with col_rename:
        if st.button("✏️", help="Rename session", use_container_width=True):
            st.session_state["show_rename"] = True

    with col_delete:
        if st.button("🗑️", help="Delete session", use_container_width=True):
            st.session_state["show_delete_confirm"] = True

    # Rename flow
    if st.session_state.get("show_rename"):
        current_title = session_dict.get(st.session_state.session_id, "")
        new_title = st.text_input("New name", value=current_title, max_chars=100, key="rename_input")
        rename_col1, rename_col2 = st.columns(2)
        with rename_col1:
            if st.button("Save", use_container_width=True):
                if new_title.strip():
                    rename_session(st.session_state.session_id, new_title.strip())
                    ui_logger.info(f"Renamed session {st.session_state.session_id} to '{new_title.strip()}'")
                st.session_state["show_rename"] = False
                st.rerun()
        with rename_col2:
            if st.button("Cancel", use_container_width=True, key="cancel_rename"):
                st.session_state["show_rename"] = False
                st.rerun()

    # Delete confirmation flow
    if st.session_state.get("show_delete_confirm"):
        st.warning(f"Delete **{session_dict.get(st.session_state.session_id, 'this session')}** and all its messages?")
        del_col1, del_col2 = st.columns(2)
        with del_col1:
            if st.button("Yes, delete", type="primary", use_container_width=True):
                delete_session(st.session_state.session_id)
                ui_logger.info(f"Deleted session {st.session_state.session_id}")
                st.session_state["show_delete_confirm"] = False
                # Switch to another session or create a new one
                remaining = get_sessions()
                if remaining:
                    st.session_state.session_id = remaining[0]["id"]
                else:
                    st.session_state.session_id = create_session("New Session")
                st.rerun()
        with del_col2:
            if st.button("Cancel", use_container_width=True, key="cancel_delete"):
                st.session_state["show_delete_confirm"] = False
                st.rerun()

    st.caption(session_dict.get(st.session_state.session_id, "Session"))
    if st.button("+ New Chat", use_container_width=True):
        st.session_state.session_id = create_session("New Session")
        ui_logger.info(f"Created new chat session: {st.session_state.session_id}")
        st.rerun()

    st.divider()

    return st.session_state.session_id


render_chat(_render_session_controls())