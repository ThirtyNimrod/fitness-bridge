"""
Shared pytest configuration.
Adds the project root to sys.path so all imports resolve correctly
regardless of which directory pytest is invoked from.
"""

import sys
import os
import json
from datetime import date, timedelta

import pytest
import streamlit as st

# Insert the project root (parent of this tests/ dir) into the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.utils.database import init_db, upsert_workout


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
	db_file = str(tmp_path / "test.db")
	monkeypatch.setattr(config, "DB_PATH", db_file)
	import src.utils.database as db_module
	monkeypatch.setattr(db_module, "DB_PATH", db_file)
	st.cache_data.clear()
	st.cache_resource.clear()
	init_db()
	yield db_file


@pytest.fixture
def workout_factory():
	def _create(**overrides):
		workout_date = overrides.pop("date", date.today().isoformat())
		base_record = {
			"activity_id": overrides.pop("activity_id", f"activity-{workout_date}"),
			"date": workout_date,
			"workout_title": overrides.pop("workout_title", "Upper Strength"),
			"duration_min": overrides.pop("duration_min", 60.0),
			"total_volume_kg": overrides.pop("total_volume_kg", 2500.0),
			"exercise_count": overrides.pop("exercise_count", 2),
			"set_count": overrides.pop("set_count", 6),
			"exercises_raw": overrides.pop(
				"exercises_raw",
				json.dumps([
					{
						"name": "Bench Press",
						"muscle_group": "chest",
						"sets": [
							{"set_number": 1, "type": "weighted", "weight_kg": 60, "reps": 10, "tag": None},
							{"set_number": 2, "type": "weighted", "weight_kg": 65, "reps": 8, "tag": "Drop"},
						],
					},
					{
						"name": "Push Up",
						"muscle_group": "chest",
						"sets": [
							{"set_number": 1, "type": "bodyweight", "reps": 20, "tag": None},
						],
					},
				]),
			),
			"muscle_groups": overrides.pop("muscle_groups", json.dumps(["chest", "triceps"])),
			"has_drop_sets": overrides.pop("has_drop_sets", 1),
			"has_failure_sets": overrides.pop("has_failure_sets", 0),
			"sleep_hours": overrides.pop("sleep_hours", 7.5),
			"sleep_efficiency": overrides.pop("sleep_efficiency", 90.0),
			"hrv_ms": overrides.pop("hrv_ms", 65.0),
			"resting_hr": overrides.pop("resting_hr", 52.0),
			"readiness_score": overrides.pop("readiness_score", 81.0),
			"readiness_label": overrides.pop("readiness_label", "Ready"),
		}
		base_record.update(overrides)
		upsert_workout(base_record)
		return base_record

	return _create


@pytest.fixture
def workout_batch_factory(workout_factory):
	def _create(count: int, title_prefix: str = "Workout"):
		created = []
		for index in range(count):
			created.append(
				workout_factory(
					activity_id=f"activity-{index}",
					date=(date.today() - timedelta(days=index)).isoformat(),
					workout_title=f"{title_prefix} {index}",
					total_volume_kg=1000.0 + index * 100,
				)
			)
		return created

	return _create
