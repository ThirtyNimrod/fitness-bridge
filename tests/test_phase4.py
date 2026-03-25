"""
Test Suite: Phase 4 - Analysis Algorithms
Tests: readiness scoring, load computation, ACWR, progressive overload detection.
"""

import os
import sys
import pytest
import pandas as pd
import json
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.analysis.readiness import (
    score_sleep, score_hrv, score_resting_hr,
    get_readiness_label, derive_recommendation, compute_readiness
)
from src.analysis.load import (
    compute_weekly_load, compute_acwr, detect_overreach,
    progressive_overload_check
)


# ---------------------------------------------------------------------------
# Readiness Tests
# ---------------------------------------------------------------------------

class TestSleepScoring:
    def test_8h_sleep_gets_max_sleep_score(self):
        data = {"summary": {"totalMinutesAsleep": 480, "efficiency": 100}}
        assert score_sleep(data) == 40

    def test_7h_sleep_score(self):
        data = {"summary": {"totalMinutesAsleep": 420, "efficiency": 90}}
        assert score_sleep(data) >= 35

    def test_5h_sleep_score(self):
        data = {"summary": {"totalMinutesAsleep": 300, "efficiency": 70}}
        assert score_sleep(data) == pytest.approx(22.0, abs=1)

    def test_empty_data_returns_safe_value(self):
        assert score_sleep({}) >= 0


class TestHRVScoring:
    def test_hrv_above_baseline_gets_max(self):
        data = {"hrv": [{"value": {"dailyRmssd": 50.0}}]}  # 50 / 45 baseline > 1.10
        assert score_hrv(data) == 40

    def test_hrv_missing_returns_neutral(self):
        assert score_hrv({}) == 20

    def test_hrv_half_baseline_returns_zero(self):
        data = {"hrv": [{"value": {"dailyRmssd": 20.0}}]}  # 20/45 < 0.65
        assert score_hrv(data) == 0


class TestRestingHRScoring:
    def test_below_baseline_gets_max(self):
        assert score_resting_hr(55, 60) == 20   # delta = -5

    def test_at_baseline_gets_normal(self):
        assert score_resting_hr(60, 60) == 17

    def test_elevated_reduces_score(self):
        assert score_resting_hr(65, 60) <= 10

    def test_none_returns_neutral(self):
        assert score_resting_hr(None, 60) == 10


class TestReadinessLabels:
    @pytest.mark.parametrize("score,keyword", [
        (80, "High"),
        (60, "Moderate"),
        (35, "Low"),
        (15, "Poor"),
    ])
    def test_label_matches_score(self, score, keyword):
        assert keyword in get_readiness_label(score)

    def test_derive_recommendation_for_all_bands(self):
        for score in [80, 60, 35, 10]:
            rec = derive_recommendation(score)
            assert isinstance(rec, str) and len(rec) > 0


class TestComputeReadiness:
    def test_full_readiness_output_shape(self):
        sleep = {"summary": {"totalMinutesAsleep": 450, "efficiency": 90}}
        hrv = {"hrv": [{"value": {"dailyRmssd": 46.0}}]}
        result = compute_readiness(sleep, hrv, 58)
        assert "score" in result
        assert "label" in result
        assert "components" in result
        assert "recommendation" in result
        assert 0 <= result["score"] <= 100


# ---------------------------------------------------------------------------
# Load Tests
# ---------------------------------------------------------------------------

def _make_df(n_days=28, volume_per_day=1000):
    today = date.today()
    return pd.DataFrame({
        "date": [(today - timedelta(days=i)).isoformat() for i in range(n_days)],
        "total_volume_kg": [float(volume_per_day)] * n_days,
        "duration_min": [60.0] * n_days
    })


class TestWeeklyLoad:
    def test_returns_7_days_of_volume(self):
        df = _make_df(28, 1000)
        result = compute_weekly_load(df)
        assert result["total_volume_kg"] == pytest.approx(7000.0, abs=1)

    def test_empty_df_returns_zeros(self):
        result = compute_weekly_load(pd.DataFrame())
        assert result["total_volume_kg"] == 0
        assert result["session_count"] == 0


class TestACWR:
    def test_constant_volume_gives_ratio_near_one(self):
        df = _make_df(28, 1000)
        result = compute_acwr(df)
        assert result is not None
        assert result["ratio"] == pytest.approx(1.0, abs=0.05)
        assert result["zone"] == "optimal"

    def test_empty_df_returns_none(self):
        assert compute_acwr(pd.DataFrame()) is None

    def test_overreach_detected_when_ratio_exceeds_1_5(self):
        today = date.today()
        # Spike last 7 days compared to prior 21
        dates = (
            [(today - timedelta(days=i)).isoformat() for i in range(7)] +
            [(today - timedelta(days=7 + i)).isoformat() for i in range(21)]
        )
        volumes = [5000.0] * 7 + [500.0] * 21
        df = pd.DataFrame({"date": dates, "total_volume_kg": volumes, "duration_min": [60.0] * 28})
        flagged, msg = detect_overreach(df)
        assert flagged is True


class TestProgressiveOverload:
    def _make_progress_df(self, volumes):
        today = date.today()
        rows = []
        for i, v in enumerate(volumes):
            rows.append({
                "date": (today - timedelta(days=len(volumes) - i)).isoformat(),
                "exercises_raw": json.dumps([{"name": "Squat", "total_volume_kg": v}])
            })
        return pd.DataFrame(rows)

    def test_increasing_volume_is_progressing(self):
        df = self._make_progress_df([500, 520, 540, 560, 580, 600])
        result = progressive_overload_check(df, "Squat")
        assert result["trend"] == "progressing"
        assert result["pct_change"] > 0

    def test_stable_volume_is_maintaining(self):
        df = self._make_progress_df([1000, 1000, 1000, 1000, 1000, 1000])
        result = progressive_overload_check(df, "Squat")
        assert result["trend"] == "maintaining"

    def test_insufficient_data_returns_safe_message(self):
        df = self._make_progress_df([500])
        result = progressive_overload_check(df, "Squat")
        assert result["trend"] == "insufficient_data"
