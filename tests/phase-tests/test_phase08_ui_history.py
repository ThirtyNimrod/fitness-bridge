import os

from streamlit.testing.v1 import AppTest


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_PAGE = os.path.join(BASE_DIR, "ui", "pages", "history.py")


class TestHistoryPage:
    def test_history_page_loads_empty(self, fresh_db):
        at = AppTest.from_file(HISTORY_PAGE, default_timeout=10)
        at.run()
        assert not at.exception
        assert at.header[0].value == "Workout History"
        assert len(at.info) == 1

    def test_history_filters_by_title(self, fresh_db, workout_factory):
        workout_factory(activity_id="alpha", workout_title="Upper Strength")
        workout_factory(activity_id="beta", workout_title="Lower Strength")

        at = AppTest.from_file(HISTORY_PAGE, default_timeout=10)
        at.run()
        at.text_input[0].set_value("Upper").run()

        assert not at.exception
        assert len(at.expander) == 1
        assert "Upper Strength" in at.expander[0].label

    def test_history_pagination(self, fresh_db, workout_batch_factory):
        workout_batch_factory(15, title_prefix="History")

        at = AppTest.from_file(HISTORY_PAGE, default_timeout=10)
        at.run()
        assert len(at.expander) == 10

        next_button = next(button for button in at.button if button.label == "Next")
        next_button.click().run()

        labels = [expander.label for expander in at.expander]
        assert any("History 10" in label for label in labels)
        assert any("History 14" in label for label in labels)
        assert all("History 0" not in label for label in labels)
