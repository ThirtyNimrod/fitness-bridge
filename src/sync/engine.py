"""
sync/engine.py
Delta sync engine: pulls new Strava activities + matching Fitbit biometrics,
builds unified session records, and upserts them into the local SQLite cache.
"""

from datetime import datetime
from src.clients.strava_client import StravaClient
from src.clients.fitbit_client import FitbitClient
from src.parsers.hevy_parser import parse_description
from src.analysis.readiness import compute_readiness
from src.analysis.dataset import build_session_record
from src.utils.database import (
    upsert_workout,
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
        last_synced = get_last_synced("strava")  # None on very first run
        app_logger.info(
            f"SyncEngine.sync() starting — last_synced={last_synced}, force={force}"
        )

        activities = safe_fetch(self.strava.get_activities, 50) or []

        new_activities = []
        for activity in activities:
            raw_date = activity.get("start_date_local", "")
            if not raw_date:
                continue
            if not force and last_synced:
                try:
                    activity_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                    # Make last_synced timezone-aware if activity_dt is
                    if activity_dt.tzinfo and last_synced.tzinfo is None:
                        from datetime import timezone
                        last_synced_aware = last_synced.replace(tzinfo=timezone.utc)
                    else:
                        last_synced_aware = last_synced
                    if activity_dt <= last_synced_aware:
                        continue  # already synced
                except (ValueError, TypeError):
                    pass  # parse failure → process anyway
            new_activities.append((activity, raw_date[:10]))

        app_logger.info(f"Sync: {len(new_activities)} new activities to process")

        errors = 0
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
                upsert_workout(record)
            except Exception as e:
                errors += 1
                app_logger.error(
                    f"Sync error for activity {activity.get('id')}: {e}"
                )

        set_last_synced("strava")
        result = {
            "synced": len(new_activities),
            "errors": errors,
            "last_synced_at": datetime.now(),
        }
        app_logger.info(f"Sync complete: {result}")
        return result
