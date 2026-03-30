import os
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DASHBOARD_PAGE = os.path.join(BASE_DIR, "ui", "pages", "dashboard.py")


class TestDashboardPage:
    def test_dashboard_loads_no_data(self, fresh_db):
        at = AppTest.from_file(DASHBOARD_PAGE, default_timeout=10)
        at.run()
        assert not at.exception
        assert at.header[0].value == "Your Training Overview"
        assert len(at.info) == 1
        assert any(button.label == "Clear Cache" for button in at.button)

    def test_dashboard_loads_with_data(self, fresh_db, workout_factory):
        workout_factory()
        with patch("ui.dashboard._get_todays_readiness_payload", return_value={"score": 84, "label": "Ready"}):
            at = AppTest.from_file(DASHBOARD_PAGE, default_timeout=10)
            at.run()

        assert not at.exception
        labels = {metric.label for metric in at.metric}
        assert "⚡ Today's Readiness" in labels
        assert "🏋️ This Week's Volume" in labels
        assert "📊 ACWR" in labels
        assert "🗓️ Sessions This Week" in labels

    def test_dashboard_shows_last_workout_expanders(self, fresh_db, workout_factory):
        workout_factory(workout_title="Upper A")
        with patch("ui.dashboard._get_todays_readiness_payload", return_value={"score": 80, "label": "Ready"}):
            at = AppTest.from_file(DASHBOARD_PAGE, default_timeout=10)
            at.run()

        assert not at.exception
        assert any(expander.label.startswith("Bench Press") for expander in at.expander)
