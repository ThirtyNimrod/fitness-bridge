"""
sync/engine.py
Delta sync engine: pulls new Strava activities + matching Fitbit biometrics,
pulls Fitbit activity log entries (Pixel Watch workouts),
builds unified session records, and upserts them into the local SQLite cache.
"""

from datetime import datetime, timezone
from src.clients.strava_client import StravaClient
from src.clients.fitbit_client import FitbitClient, ACTIVITY_TYPE_MAP
from src.parsers.hevy_parser import parse_description
from src.analysis.readiness import compute_readiness
from src.analysis.dataset import build_session_record, build_fitbit_session_record
from src.utils.database import (
    upsert_workout,
    validate_workout_record,
    get_last_synced,
    set_last_synced,
)
from src.utils.logger import app_logger


def safe_fetch(fn, *args):
    """Call fn(*args) and return None on any exception, logging a warning."""
    try:
        return fn(*args)
    except Exception as e:
        app_logger.warning(f"safe_fetch failed for {fn.__name__}: {e}")
        return None


def _parse_activity_timestamp(raw_date: str):
    """Parse Strava timestamps to aware UTC datetimes, returning None when invalid."""
    try:
        parsed = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_utc_aware(dt: datetime):
    """Normalize DB and API datetimes to aware UTC for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SyncEngine:
    """
    Orchestrates delta synchronisation from Strava + Fitbit into the local DB.

    Usage:
        result = SyncEngine().sync()
        result = SyncEngine().sync(force=True)  # re-fetch all on first run
    """

    def __init__(self):
        self.strava = StravaClient()
        self.fitbit = FitbitClient()

    def sync(self, force: bool = False) -> dict:
        """
        Delta sync: only fetch activities newer than last_synced_at.
        If force=True, re-processes all returned activities regardless.

        Returns:
            {"synced": N, "errors": M, "last_synced_at": datetime}
        """
        last_synced = _to_utc_aware(get_last_synced("strava"))  # None on very first run
        app_logger.info(
            f"SyncEngine.sync() starting — last_synced={last_synced}, force={force}"
        )

        activities = safe_fetch(self.strava.get_activities, 50) or []

        new_activities = []
        for activity in activities:
            raw_date = activity.get("start_date_local", "")
            if not raw_date:
                app_logger.warning(
                    f"Skipping activity {activity.get('id')} due to missing start_date_local"
                )
                continue

            activity_dt = _parse_activity_timestamp(raw_date)
            if activity_dt is None:
                app_logger.warning(
                    f"Skipping activity {activity.get('id')} due to malformed timestamp: {raw_date}"
                )
                continue

            if not force and last_synced:
                if activity_dt <= last_synced:
                    continue  # already synced
            new_activities.append((activity, raw_date[:10]))

        app_logger.info(f"Sync: {len(new_activities)} new activities to process")

        synced = 0
        errors = 0
        latest_synced_activity_dt = None
        for activity, date in new_activities:
            try:
                sleep_data = safe_fetch(self.fitbit.get_sleep, date)
                hrv_data   = safe_fetch(self.fitbit.get_hrv, date)
                resting_hr = safe_fetch(self.fitbit.get_resting_hr, date)

                detail      = safe_fetch(self.strava.get_activity_detail, activity["id"])
                description = (detail or {}).get("description", "")

                exercises = parse_description(description)
                readiness = compute_readiness(
                    sleep_data or {},
                    hrv_data   or {},
                    resting_hr,
                )
                record = build_session_record(detail or activity, exercises, readiness)
                validated = validate_workout_record(record)
                upsert_workout(validated)
                synced += 1

                activity_dt = _parse_activity_timestamp(activity.get("start_date_local", ""))
                if activity_dt is not None:
                    if latest_synced_activity_dt is None or activity_dt > latest_synced_activity_dt:
                        latest_synced_activity_dt = activity_dt
            except ValueError as e:
                errors += 1
                app_logger.warning(
                    f"Sync validation skipped activity {activity.get('id')}: {e}"
                )
            except Exception as e:
                errors += 1
                app_logger.error(
                    f"Sync error for activity {activity.get('id')}: {e}"
                )

        if synced > 0:
            set_last_synced("strava", latest_synced_activity_dt)

        # ── Fitbit activity sync ──────────────────────────────────────────
        fitbit_synced, fitbit_errors = self._sync_fitbit_activities(force=force)
        synced += fitbit_synced
        errors += fitbit_errors

        result = {
            "synced": synced,
            "errors": errors,
            "last_synced_at": datetime.now(timezone.utc),
        }
        app_logger.info(f"Sync complete: {result}")
        return result

    def _sync_fitbit_activities(self, force: bool = False) -> tuple[int, int]:
        """Sync Fitbit activity log entries (Pixel Watch workouts) alongside Strava."""
        last_synced = _to_utc_aware(get_last_synced("fitbit_activities"))
        app_logger.info(
            f"Fitbit activity sync starting — last_synced={last_synced}, force={force}"
        )

        activities = safe_fetch(self.fitbit.get_activities, None, 50) or []
        if not activities:
            app_logger.info("Fitbit activity sync: no activities returned")
            return 0, 0

        synced = 0
        errors = 0
        latest_dt = None

        for activity in activities:
            try:
                start_time = activity.get("startTime", "")
                if not start_time:
                    continue

                activity_dt = _parse_activity_timestamp(start_time)
                if activity_dt is None:
                    continue

                if not force and last_synced and activity_dt <= last_synced:
                    continue

                record = build_fitbit_session_record(activity, ACTIVITY_TYPE_MAP)
                validated = validate_workout_record(record)
                upsert_workout(validated)
                synced += 1

                if latest_dt is None or activity_dt > latest_dt:
                    latest_dt = activity_dt
            except ValueError as e:
                errors += 1
                app_logger.warning(
                    f"Fitbit sync validation skipped activity {activity.get('logId')}: {e}"
                )
            except Exception as e:
                errors += 1
                app_logger.error(
                    f"Fitbit sync error for activity {activity.get('logId')}: {e}"
                )

        if synced > 0 and latest_dt:
            set_last_synced("fitbit_activities", latest_dt)

        app_logger.info(f"Fitbit activity sync: {synced} synced, {errors} errors")
        return synced, errors
