import os

from streamlit.testing.v1 import AppTest


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_PAGE = os.path.join(BASE_DIR, "ui", "pages", "settings.py")


class CacheStub:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class TestSettingsPage:
    def test_settings_page_loads(self, fresh_db, monkeypatch):
        monkeypatch.setattr("ui.shared.get_connection_statuses", lambda: {
            "strava": {"connected": True, "error": None},
            "fitbit": {"connected": False, "error": None},
        })
        at = AppTest.from_file(SETTINGS_PAGE, default_timeout=10)
        at.run()
        assert not at.exception
        assert at.header[0].value == "Settings"
        labels = {button.label for button in at.button}
        assert "Sync Workouts" in labels
        assert "Clear Cache" in labels

    def test_settings_sync_button_triggers_sync(self, fresh_db, monkeypatch):
        calls = []

        monkeypatch.setattr("ui.shared.get_connection_statuses", lambda: {
            "strava": {"connected": True, "error": None},
            "fitbit": {"connected": True, "error": None},
        })
        monkeypatch.setattr("ui.shared.run_sync_with_lock", lambda force=False: calls.append(force) or {"synced": 2})

        at = AppTest.from_file(SETTINGS_PAGE, default_timeout=10)
        at.run()
        next(button for button in at.button if button.label == "Sync Workouts").click().run()

        assert calls == [True]

    def test_settings_cache_clear_calls_cache(self, fresh_db, monkeypatch):
        cache = CacheStub()
        monkeypatch.setattr("ui.shared.get_connection_statuses", lambda: {
            "strava": {"connected": True, "error": None},
            "fitbit": {"connected": True, "error": None},
        })
        monkeypatch.setattr("src.utils.cache.get_cache", lambda: cache)

        at = AppTest.from_file(SETTINGS_PAGE, default_timeout=10)
        at.run()
        next(button for button in at.button if button.label == "Clear Cache").click().run()

        assert cache.cleared is True