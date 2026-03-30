"""
Test Suite: Phase 05 - Sync Engine
Coverage:
- Tests delta synchronization logic based on `last_synced` timestamps.
- Verifies edge cases for missing dates or malformed API responses safely skip.
- Confirms the correct behavior of the force synchronization flag (force=True).
- Mocks API network calls to ensure pure functional testing of upsert routing.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.sync.engine import SyncEngine
from src.utils.database import get_workouts, get_last_synced, init_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

@patch('src.sync.engine.StravaClient.__init__', return_value=None)
@patch('src.sync.engine.FitbitClient.__init__', return_value=None)
def test_sync_engine_first_run_skips_unparsable_date(mock_fitbit_init, mock_strava_init):
    engine = SyncEngine()
    engine.strava = MagicMock()
    engine.fitbit = MagicMock()
    
    # Mock Strava returning one valid, one invalid
    engine.strava.get_activities.return_value = [
        {"id": 1, "start_date_local": "2026-03-24T10:00:00Z"},
        {"id": 2, "start_date_local": ""} # Invalid/missing date
    ]
    
    engine.strava.get_activity_detail.return_value = {"id": 1, "description": "some workout"}
    engine.fitbit.get_sleep.return_value = {}
    engine.fitbit.get_hrv.return_value = {}
    engine.fitbit.get_resting_hr.return_value = None

    with patch('src.sync.engine.get_last_synced', return_value=None), \
         patch('src.sync.engine.upsert_workout') as mock_upsert, \
         patch('src.sync.engine.set_last_synced') as mock_set_synced:
        
        result = engine.sync()
        
        assert result["synced"] == 1
        assert result["errors"] == 0
        mock_upsert.assert_called_once()
        mock_set_synced.assert_called_once()
        assert mock_set_synced.call_args[0][0] == "strava"
        assert isinstance(mock_set_synced.call_args[0][1], datetime)


@patch('src.sync.engine.StravaClient.__init__', return_value=None)
@patch('src.sync.engine.FitbitClient.__init__', return_value=None)
def test_sync_engine_delta_logic(mock_fitbit_init, mock_strava_init):
    engine = SyncEngine()
    engine.strava = MagicMock()
    engine.fitbit = MagicMock()
    
    # Mock 3 activities
    # Two older than last_synced, one newer
    engine.strava.get_activities.return_value = [
        {"id": 100, "start_date_local": "2026-03-25T10:00:00Z"},  # Newer
        {"id": 99,  "start_date_local": "2026-03-23T10:00:00Z"},  # Older
        {"id": 98,  "start_date_local": "2026-03-22T10:00:00Z"},  # Older
    ]
    
    engine.strava.get_activity_detail.return_value = {"id": 100}
    engine.fitbit.get_sleep.return_value = {}
    engine.fitbit.get_hrv.return_value = {}
    engine.fitbit.get_resting_hr.return_value = None

    last_synced_dt = datetime.fromisoformat("2026-03-24T00:00:00+00:00")
    
    with patch('src.sync.engine.get_last_synced', return_value=last_synced_dt), \
         patch('src.sync.engine.upsert_workout') as mock_upsert, \
         patch('src.sync.engine.set_last_synced') as mock_set_synced:
        
        result = engine.sync(force=False)
        
        # Only the 25th should sync
        assert result["synced"] == 1
        assert result["errors"] == 0
        mock_upsert.assert_called_once()
        mock_set_synced.assert_called_once()
        
        # If force=True is passed, all 3 sync
        mock_upsert.reset_mock()
        mock_set_synced.reset_mock()
        result_force = engine.sync(force=True)
        assert result_force["synced"] == 3
        assert mock_upsert.call_count == 3
        mock_set_synced.assert_called_once()


@patch('src.sync.engine.StravaClient.__init__', return_value=None)
@patch('src.sync.engine.FitbitClient.__init__', return_value=None)
def test_sync_engine_skips_malformed_timestamp_with_warning(mock_fitbit_init, mock_strava_init):
    engine = SyncEngine()
    engine.strava = MagicMock()
    engine.fitbit = MagicMock()

    engine.strava.get_activities.return_value = [
        {"id": 100, "start_date_local": "2026-03-25T10:00:00Z"},
        {"id": 101, "start_date_local": "invalid-date"},
    ]
    engine.strava.get_activity_detail.return_value = {"id": 100, "description": "ok"}
    engine.fitbit.get_sleep.return_value = {}
    engine.fitbit.get_hrv.return_value = {}
    engine.fitbit.get_resting_hr.return_value = None

    with patch('src.sync.engine.get_last_synced', return_value=None), \
         patch('src.sync.engine.upsert_workout') as mock_upsert, \
         patch('src.sync.engine.set_last_synced'), \
         patch('src.sync.engine.app_logger.warning') as mock_warn:
        result = engine.sync()

    assert result["synced"] == 1
    assert result["errors"] == 0
    mock_upsert.assert_called_once()
    mock_warn.assert_any_call("Skipping activity 101 due to malformed timestamp: invalid-date")


@patch('src.sync.engine.StravaClient.__init__', return_value=None)
@patch('src.sync.engine.FitbitClient.__init__', return_value=None)
def test_sync_engine_handles_naive_last_synced_as_utc(mock_fitbit_init, mock_strava_init):
    engine = SyncEngine()
    engine.strava = MagicMock()
    engine.fitbit = MagicMock()

    engine.strava.get_activities.return_value = [
        {"id": 200, "start_date_local": "2026-03-24T00:00:00Z"},
        {"id": 201, "start_date_local": "2026-03-24T00:00:01Z"},
    ]
    engine.strava.get_activity_detail.return_value = {"id": 201, "description": "ok"}
    engine.fitbit.get_sleep.return_value = {}
    engine.fitbit.get_hrv.return_value = {}
    engine.fitbit.get_resting_hr.return_value = None

    # Naive value from DB should be interpreted as UTC.
    naive_last_synced = datetime.fromisoformat("2026-03-24T00:00:00")

    with patch('src.sync.engine.get_last_synced', return_value=naive_last_synced), \
         patch('src.sync.engine.upsert_workout') as mock_upsert, \
         patch('src.sync.engine.set_last_synced'):
        result = engine.sync(force=False)

    assert result["synced"] == 1
    assert result["errors"] == 0
    mock_upsert.assert_called_once()


@patch('src.sync.engine.StravaClient.__init__', return_value=None)
@patch('src.sync.engine.FitbitClient.__init__', return_value=None)
def test_sync_engine_counts_validation_errors(mock_fitbit_init, mock_strava_init):
    engine = SyncEngine()
    engine.strava = MagicMock()
    engine.fitbit = MagicMock()

    engine.strava.get_activities.return_value = [
        {"id": 300, "start_date_local": "2026-03-25T10:00:00Z"},
    ]
    engine.strava.get_activity_detail.return_value = {"id": 300, "description": "ok"}
    engine.fitbit.get_sleep.return_value = {}
    engine.fitbit.get_hrv.return_value = {}
    engine.fitbit.get_resting_hr.return_value = None

    with patch('src.sync.engine.get_last_synced', return_value=None), \
         patch('src.sync.engine.validate_workout_record', side_effect=ValueError("bad record")), \
         patch('src.sync.engine.upsert_workout') as mock_upsert, \
            patch('src.sync.engine.set_last_synced') as mock_set_synced, \
         patch('src.sync.engine.app_logger.warning') as mock_warn:
        result = engine.sync()

    assert result["synced"] == 0
    assert result["errors"] == 1
    mock_upsert.assert_not_called()
    assert mock_warn.call_count >= 1
    mock_set_synced.assert_not_called()
    mock_warn.assert_any_call("Sync validation skipped activity 300: bad record")


@patch('src.sync.engine.StravaClient.__init__', return_value=None)
@patch('src.sync.engine.FitbitClient.__init__', return_value=None)
def test_sync_engine_reports_successful_upserts_only(mock_fitbit_init, mock_strava_init):
    engine = SyncEngine()
    engine.strava = MagicMock()
    engine.fitbit = MagicMock()

    engine.strava.get_activities.return_value = [
        {"id": 400, "start_date_local": "2026-03-25T10:00:00Z"},
        {"id": 401, "start_date_local": "2026-03-25T11:00:00Z"},
    ]
    engine.fitbit.get_sleep.return_value = {}
    engine.fitbit.get_hrv.return_value = {}
    engine.fitbit.get_resting_hr.return_value = None

    details = {
        400: {"id": 400, "description": "ok"},
        401: {"id": 401, "description": "ok"},
    }
    engine.strava.get_activity_detail.side_effect = lambda activity_id: details[activity_id]

    validated_payloads = [{"activity_id": "400", "date": "2026-03-25"}, ValueError("invalid")]

    def fake_validate(_record):
        outcome = validated_payloads.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    with patch('src.sync.engine.get_last_synced', return_value=None), \
         patch('src.sync.engine.validate_workout_record', side_effect=fake_validate), \
         patch('src.sync.engine.upsert_workout') as mock_upsert, \
         patch('src.sync.engine.set_last_synced') as mock_set_synced:
        result = engine.sync()

    assert result["synced"] == 1
    assert result["errors"] == 1
    mock_upsert.assert_called_once()
    mock_set_synced.assert_called_once()


@patch('src.sync.engine.StravaClient.__init__', return_value=None)
@patch('src.sync.engine.FitbitClient.__init__', return_value=None)
def test_sync_engine_does_not_advance_watermark_when_no_success(mock_fitbit_init, mock_strava_init):
    engine = SyncEngine()
    engine.strava = MagicMock()
    engine.fitbit = MagicMock()

    engine.strava.get_activities.return_value = [
        {"id": 500, "start_date_local": "2026-03-25T10:00:00Z"},
    ]
    engine.strava.get_activity_detail.return_value = {"id": 500, "description": "ok"}
    engine.fitbit.get_sleep.return_value = {}
    engine.fitbit.get_hrv.return_value = {}
    engine.fitbit.get_resting_hr.return_value = None

    with patch('src.sync.engine.get_last_synced', return_value=None), \
         patch('src.sync.engine.validate_workout_record', side_effect=ValueError("bad")), \
         patch('src.sync.engine.upsert_workout') as mock_upsert, \
         patch('src.sync.engine.set_last_synced') as mock_set_synced:
        result = engine.sync()

    assert result["synced"] == 0
    assert result["errors"] == 1
    mock_upsert.assert_not_called()
    mock_set_synced.assert_not_called()

