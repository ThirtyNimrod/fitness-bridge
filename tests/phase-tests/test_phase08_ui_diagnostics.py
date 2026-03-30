import os

from streamlit.testing.v1 import AppTest


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIAGNOSTICS_PAGE = os.path.join(BASE_DIR, "ui", "pages", "diagnostics.py")


class TestDiagnosticsPage:
    def test_diagnostics_page_loads(self, fresh_db, monkeypatch):
        monkeypatch.setattr("src.agents.router.get_routing_metrics", lambda: {
            "total_routed": 12,
            "heuristic_hits": 9,
            "llm_fallbacks": 3,
        })

        at = AppTest.from_file(DIAGNOSTICS_PAGE, default_timeout=10)
        at.run()

        assert not at.exception
        assert at.header[0].value == "Diagnostics"
        metric_labels = {metric.label for metric in at.metric}
        assert "Total Routed" in metric_labels
        assert "Heuristic Hits" in metric_labels
        assert "LLM Fallbacks" in metric_labels
        assert "Heuristic Rate" in metric_labels

    def test_diagnostics_reset_button_calls_router_reset(self, fresh_db, monkeypatch):
        calls = []
        monkeypatch.setattr("src.agents.router.get_routing_metrics", lambda: {
            "total_routed": 5,
            "heuristic_hits": 4,
            "llm_fallbacks": 1,
        })
        monkeypatch.setattr("src.agents.router.reset_routing_metrics", lambda: calls.append(True))

        at = AppTest.from_file(DIAGNOSTICS_PAGE, default_timeout=10)
        at.run()
        next(button for button in at.button if button.label == "Reset Router Metrics").click().run()

        assert calls == [True]