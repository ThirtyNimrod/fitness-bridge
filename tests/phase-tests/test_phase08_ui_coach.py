import os

from streamlit.testing.v1 import AppTest

from src.utils.database import create_session, get_sessions


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COACH_PAGE = os.path.join(BASE_DIR, "ui", "pages", "coach.py")


class TestCoachPage:
    def test_coach_page_loads_with_session(self, fresh_db):
        create_session("Morning Session")
        at = AppTest.from_file(COACH_PAGE, default_timeout=10)
        at.run()
        assert not at.exception
        assert at.header[0].value == "AI Coach"
        assert len(at.selectbox) == 1
        assert len(at.chat_input) == 1

    def test_coach_new_session_creates_row(self, fresh_db):
        create_session("Existing Session")
        at = AppTest.from_file(COACH_PAGE, default_timeout=10)
        at.run()
        before = len(get_sessions())
        # "New Chat" button is after ✏️ rename and 🗑️ delete buttons
        new_chat_btn = None
        for btn in at.button:
            if btn.label == "+ New Chat":
                new_chat_btn = btn
                break
        if new_chat_btn is None:
            # Fallback: last button in the list
            new_chat_btn = at.button[-1]
        new_chat_btn.click().run()
        after = len(get_sessions())
        assert after == before + 1

    def test_coach_session_picker_shows_all_sessions(self, fresh_db):
        first = create_session("Session One")
        second = create_session("Session Two")
        third = create_session("Session Three")

        at = AppTest.from_file(COACH_PAGE, default_timeout=10)
        at.run()

        options = set(at.selectbox[0].options)
        assert {"Session One", "Session Two", "Session Three"}.issubset(options)
