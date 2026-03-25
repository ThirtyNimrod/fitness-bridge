"""
Test Suite: Phase 03 - Parsers (Hevy Integration)
Coverage:
- Tests extracting individual components from heavy lifting strings (reps, weight, RPE/tags).
- Validates the calculation algorithm for isolating set volume (e.g. 100kg x 5 = 500kg volume).
- Ensures different categories of strength training strings accurately map to major muscle groups (chest, back, legs).
- Tests parsing of large, multi-exercise workout descriptions directly from Hevy synchronizations.
"""

import os
import sys
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.parsers.hevy_parser import (
    parse_set_line, calculate_exercise_volume, tag_muscle_group, parse_description
)

SAMPLE_DESCRIPTION = """Bench Press (Barbell)
Set 1: 60 kg x 10
Set 2: 60 kg x 10
Set 3: 60 kg x 8 [Failure]

Pull Up
Set 1: 10 reps
Set 2: 8 reps [Drop]

Plank
Set 1: 1min 0s"""


class TestParseSetLine:
    def test_weighted_set(self):
        result = parse_set_line("Set 1: 60 kg x 10")
        assert result["type"] == "weighted"
        assert result["weight_kg"] == 60.0
        assert result["reps"] == 10
        assert result["tag"] is None

    def test_weighted_with_tag(self):
        result = parse_set_line("Set 2: 80 kg x 5 [Drop]")
        assert result["tag"] == "Drop"

    def test_bodyweight_set(self):
        result = parse_set_line("Set 1: 12 reps")
        assert result["type"] == "bodyweight"
        assert result["reps"] == 12

    def test_bodyweight_with_failure_tag(self):
        result = parse_set_line("Set 3: 8 reps [Failure]")
        assert result["tag"] == "Failure"

    def test_duration_set(self):
        result = parse_set_line("Set 1: 1min 0s")
        assert result["type"] == "duration"
        assert "1min" in result["duration_str"]

    def test_invalid_line_returns_none(self):
        assert parse_set_line("not a set line") is None

    def test_missing_colon_returns_none(self):
        assert parse_set_line("Set 1 60 kg x 10") is None


class TestVolumeCalculation:
    def test_weighted_sets_sum(self):
        sets = [
            {"type": "weighted", "weight_kg": 60, "reps": 10},
            {"type": "weighted", "weight_kg": 60, "reps": 8},
        ]
        assert calculate_exercise_volume(sets) == round(60 * 10 + 60 * 8, 2)

    def test_bodyweight_contributes_zero(self):
        sets = [{"type": "bodyweight", "reps": 12}]
        assert calculate_exercise_volume(sets) == 0

    def test_mixed_types(self):
        sets = [
            {"type": "weighted", "weight_kg": 100, "reps": 5},
            {"type": "bodyweight", "reps": 10},
            {"type": "duration", "duration_str": "1min 0s"},
        ]
        assert calculate_exercise_volume(sets) == 500.0


class TestMuscleGroupTagging:
    @pytest.mark.parametrize("name,expected", [
        ("Bench Press (Barbell)", "chest"),
        ("Pull Up", "back"),
        ("Squat (Barbell)", "legs"),
        ("Bicep Curl", "biceps"),
        ("Plank", "core"),
        ("Something Obscure", "other"),
    ])
    def test_muscle_group_mapping(self, name, expected):
        assert tag_muscle_group(name) == expected


class TestParseDescription:
    def test_returns_list(self):
        result = parse_description(SAMPLE_DESCRIPTION)
        assert isinstance(result, list)

    def test_correct_exercise_count(self):
        result = parse_description(SAMPLE_DESCRIPTION)
        assert len(result) == 3

    def test_bench_press_details(self):
        result = parse_description(SAMPLE_DESCRIPTION)
        bench = result[0]
        assert bench["name"] == "Bench Press (Barbell)"
        assert bench["muscle_group"] == "chest"
        assert bench["set_count"] == 3
        assert bench["total_volume_kg"] == pytest.approx(1680.0)

    def test_failure_tag_captured(self):
        result = parse_description(SAMPLE_DESCRIPTION)
        bench_sets = result[0]["sets"]
        assert bench_sets[2]["tag"] == "Failure"

    def test_pull_up_is_bodyweight(self):
        result = parse_description(SAMPLE_DESCRIPTION)
        pullup = result[1]
        assert pullup["sets"][0]["type"] == "bodyweight"
        assert pullup["sets"][1]["tag"] == "Drop"

    def test_plank_is_duration(self):
        result = parse_description(SAMPLE_DESCRIPTION)
        plank = result[2]
        assert plank["sets"][0]["type"] == "duration"

    def test_empty_description_returns_empty_list(self):
        assert parse_description("") == []
        assert parse_description(None) == []
