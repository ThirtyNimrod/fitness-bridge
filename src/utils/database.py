import sqlite3
import os
import uuid
from datetime import datetime
from config import DB_PATH, SHORT_TERM_WINDOW

SCHEMA_VERSION = 3
DB_BUSY_TIMEOUT_MS = int(os.getenv("DB_BUSY_TIMEOUT_MS", "5000"))

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=max(1.0, DB_BUSY_TIMEOUT_MS / 1000.0))
    conn.execute(f"PRAGMA busy_timeout = {max(1000, DB_BUSY_TIMEOUT_MS)}")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _set_schema_version(conn, version: int):
    conn.execute(f"PRAGMA user_version = {int(version)}")


def _get_schema_version(conn) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _migrate_workouts_table_with_constraints(conn):
    """Rebuild workouts with domain constraints and copy only valid rows."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS workouts_v2 (
            activity_id      TEXT PRIMARY KEY,
            date             TEXT NOT NULL CHECK (length(date) = 10),
            workout_title    TEXT,
            duration_min     REAL CHECK (duration_min IS NULL OR duration_min >= 0),
            total_volume_kg  REAL CHECK (total_volume_kg IS NULL OR total_volume_kg >= 0),
            exercise_count   INTEGER CHECK (exercise_count IS NULL OR exercise_count >= 0),
            set_count        INTEGER CHECK (set_count IS NULL OR set_count >= 0),
            exercises_raw    TEXT,
            muscle_groups    TEXT,
            has_drop_sets    INTEGER CHECK (has_drop_sets IN (0, 1)),
            has_failure_sets INTEGER CHECK (has_failure_sets IN (0, 1)),
            sleep_hours      REAL CHECK (sleep_hours IS NULL OR sleep_hours >= 0),
            sleep_efficiency REAL CHECK (sleep_efficiency IS NULL OR (sleep_efficiency >= 0 AND sleep_efficiency <= 100)),
            hrv_ms           REAL CHECK (hrv_ms IS NULL OR hrv_ms >= 0),
            resting_hr       REAL CHECK (resting_hr IS NULL OR resting_hr >= 0),
            readiness_score  REAL CHECK (readiness_score IS NULL OR (readiness_score >= 0 AND readiness_score <= 100)),
            readiness_label  TEXT,
            synced_at        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        INSERT OR REPLACE INTO workouts_v2 (
            activity_id, date, workout_title, duration_min,
            total_volume_kg, exercise_count, set_count,
            exercises_raw, muscle_groups, has_drop_sets, has_failure_sets,
            sleep_hours, sleep_efficiency, hrv_ms, resting_hr,
            readiness_score, readiness_label, synced_at
        )
        SELECT
            activity_id,
            date,
            workout_title,
            duration_min,
            total_volume_kg,
            exercise_count,
            set_count,
            exercises_raw,
            muscle_groups,
            CASE WHEN has_drop_sets IN (1, '1', 'true', 'True') THEN 1 ELSE 0 END,
            CASE WHEN has_failure_sets IN (1, '1', 'true', 'True') THEN 1 ELSE 0 END,
            sleep_hours,
            sleep_efficiency,
            hrv_ms,
            resting_hr,
            readiness_score,
            readiness_label,
            COALESCE(synced_at, CURRENT_TIMESTAMP)
        FROM workouts
        WHERE activity_id IS NOT NULL
          AND date IS NOT NULL
          AND length(date) = 10
          AND (duration_min IS NULL OR duration_min >= 0)
          AND (total_volume_kg IS NULL OR total_volume_kg >= 0)
          AND (exercise_count IS NULL OR exercise_count >= 0)
          AND (set_count IS NULL OR set_count >= 0)
          AND (sleep_hours IS NULL OR sleep_hours >= 0)
          AND (sleep_efficiency IS NULL OR (sleep_efficiency >= 0 AND sleep_efficiency <= 100))
          AND (hrv_ms IS NULL OR hrv_ms >= 0)
          AND (resting_hr IS NULL OR resting_hr >= 0)
          AND (readiness_score IS NULL OR (readiness_score >= 0 AND readiness_score <= 100))
    ''')

    conn.execute('DROP TABLE workouts')
    conn.execute('ALTER TABLE workouts_v2 RENAME TO workouts')


def _migrate_workouts_v2_to_v3(conn):
    """Rebuild workouts with source, workout_type, calories, hr_zones, distance_km columns
    and a composite unique key on (source, activity_id)."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS workouts_v3 (
            activity_id      TEXT NOT NULL,
            source           TEXT NOT NULL DEFAULT 'strava',
            workout_type     TEXT,
            date             TEXT NOT NULL CHECK (length(date) = 10),
            workout_title    TEXT,
            duration_min     REAL CHECK (duration_min IS NULL OR duration_min >= 0),
            total_volume_kg  REAL CHECK (total_volume_kg IS NULL OR total_volume_kg >= 0),
            exercise_count   INTEGER CHECK (exercise_count IS NULL OR exercise_count >= 0),
            set_count        INTEGER CHECK (set_count IS NULL OR set_count >= 0),
            exercises_raw    TEXT,
            muscle_groups    TEXT,
            has_drop_sets    INTEGER CHECK (has_drop_sets IN (0, 1)),
            has_failure_sets INTEGER CHECK (has_failure_sets IN (0, 1)),
            sleep_hours      REAL CHECK (sleep_hours IS NULL OR sleep_hours >= 0),
            sleep_efficiency REAL CHECK (sleep_efficiency IS NULL OR (sleep_efficiency >= 0 AND sleep_efficiency <= 100)),
            hrv_ms           REAL CHECK (hrv_ms IS NULL OR hrv_ms >= 0),
            resting_hr       REAL CHECK (resting_hr IS NULL OR resting_hr >= 0),
            readiness_score  REAL CHECK (readiness_score IS NULL OR (readiness_score >= 0 AND readiness_score <= 100)),
            readiness_label  TEXT,
            calories         REAL CHECK (calories IS NULL OR calories >= 0),
            hr_zones         TEXT,
            distance_km      REAL CHECK (distance_km IS NULL OR distance_km >= 0),
            synced_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source, activity_id)
        )
    ''')

    conn.execute('''
        INSERT OR REPLACE INTO workouts_v3 (
            activity_id, source, workout_type, date, workout_title, duration_min,
            total_volume_kg, exercise_count, set_count,
            exercises_raw, muscle_groups, has_drop_sets, has_failure_sets,
            sleep_hours, sleep_efficiency, hrv_ms, resting_hr,
            readiness_score, readiness_label, synced_at
        )
        SELECT
            activity_id, 'strava', NULL, date, workout_title, duration_min,
            total_volume_kg, exercise_count, set_count,
            exercises_raw, muscle_groups, has_drop_sets, has_failure_sets,
            sleep_hours, sleep_efficiency, hrv_ms, resting_hr,
            readiness_score, readiness_label,
            COALESCE(synced_at, CURRENT_TIMESTAMP)
        FROM workouts
        WHERE activity_id IS NOT NULL
          AND date IS NOT NULL
          AND length(date) = 10
    ''')

    conn.execute('DROP TABLE workouts')
    conn.execute('ALTER TABLE workouts_v3 RENAME TO workouts')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_workouts_source ON workouts(source)')


def _run_migrations(conn):
    current = _get_schema_version(conn)
    if current < 2:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "workouts" in tables:
            _migrate_workouts_table_with_constraints(conn)
        _set_schema_version(conn, 2)
    if current < 3:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "workouts" in tables:
            _migrate_workouts_v2_to_v3(conn)
        _set_schema_version(conn, 3)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        cursor = conn.cursor()
        
        # Sessions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Messages Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        ''')
        
        # Semantic Facts Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS semantic_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Workouts cache table (v3: multi-source with composite PK)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                activity_id      TEXT NOT NULL,
                source           TEXT NOT NULL DEFAULT 'strava',
                workout_type     TEXT,
                date             TEXT NOT NULL CHECK (length(date) = 10),
                workout_title    TEXT,
                duration_min     REAL CHECK (duration_min IS NULL OR duration_min >= 0),
                total_volume_kg  REAL CHECK (total_volume_kg IS NULL OR total_volume_kg >= 0),
                exercise_count   INTEGER CHECK (exercise_count IS NULL OR exercise_count >= 0),
                set_count        INTEGER CHECK (set_count IS NULL OR set_count >= 0),
                exercises_raw    TEXT,
                muscle_groups    TEXT,
                has_drop_sets    INTEGER CHECK (has_drop_sets IN (0, 1)),
                has_failure_sets INTEGER CHECK (has_failure_sets IN (0, 1)),
                sleep_hours      REAL CHECK (sleep_hours IS NULL OR sleep_hours >= 0),
                sleep_efficiency REAL CHECK (sleep_efficiency IS NULL OR (sleep_efficiency >= 0 AND sleep_efficiency <= 100)),
                hrv_ms           REAL CHECK (hrv_ms IS NULL OR hrv_ms >= 0),
                resting_hr       REAL CHECK (resting_hr IS NULL OR resting_hr >= 0),
                readiness_score  REAL CHECK (readiness_score IS NULL OR (readiness_score >= 0 AND readiness_score <= 100)),
                readiness_label  TEXT,
                calories         REAL CHECK (calories IS NULL OR calories >= 0),
                hr_zones         TEXT,
                distance_km      REAL CHECK (distance_km IS NULL OR distance_km >= 0),
                synced_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source, activity_id)
            )
        ''')

        # Indexes (messages — safe before migration)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)')

        # Sync metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_meta (
                source         TEXT PRIMARY KEY,
                last_synced_at DATETIME
            )
        ''')

        _run_migrations(conn)

        # Workout indexes — created after migrations so the source column exists
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_workouts_source ON workouts(source)')

        conn.commit()


def validate_workout_record(record: dict) -> dict:
    """Validate and normalize a workout record before DB upsert."""
    cleaned = dict(record or {})

    activity_id = str(cleaned.get("activity_id") or "").strip()
    if not activity_id:
        raise ValueError("workout record missing activity_id")

    date_value = str(cleaned.get("date") or "").strip()
    try:
        datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("workout record has invalid date") from exc

    cleaned["activity_id"] = activity_id
    cleaned["date"] = date_value

    # Source defaults to strava for backwards compatibility
    source = str(cleaned.get("source") or "strava").strip().lower()
    if source not in ("strava", "fitbit"):
        source = "strava"
    cleaned["source"] = source

    # workout_type is freeform but optional
    if cleaned.get("workout_type"):
        cleaned["workout_type"] = str(cleaned["workout_type"]).strip()[:50]

    for key in ["duration_min", "total_volume_kg", "sleep_hours", "sleep_efficiency",
                "hrv_ms", "resting_hr", "readiness_score", "calories", "distance_km"]:
        if cleaned.get(key) is None:
            continue
        cleaned[key] = float(cleaned[key])

    for key in ["exercise_count", "set_count"]:
        if cleaned.get(key) is None:
            continue
        cleaned[key] = int(cleaned[key])

    for key in ["has_drop_sets", "has_failure_sets"]:
        cleaned[key] = 1 if cleaned.get(key) else 0

    non_negative_fields = [
        "duration_min", "total_volume_kg", "exercise_count", "set_count",
        "sleep_hours", "sleep_efficiency", "hrv_ms", "resting_hr", "readiness_score",
    ]
    for field in non_negative_fields:
        value = cleaned.get(field)
        if value is not None and value < 0:
            raise ValueError(f"workout record has negative field: {field}")

    if cleaned.get("sleep_efficiency") is not None and cleaned["sleep_efficiency"] > 100:
        raise ValueError("workout record sleep_efficiency out of range")

    if cleaned.get("readiness_score") is not None and cleaned["readiness_score"] > 100:
        raise ValueError("workout record readiness_score out of range")

    return cleaned

def create_session(title="New Session"):
    session_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute('INSERT INTO sessions (id, title) VALUES (?, ?)', (session_id, title))
        conn.commit()
    return session_id

def delete_session(session_id: str) -> bool:
    """Delete a chat session and all its messages."""
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    return True

def rename_session(session_id: str, title: str) -> bool:
    """Rename a chat session."""
    safe_title = (title or "").strip()[:100]
    if not safe_title:
        return False
    with get_connection() as conn:
        conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (safe_title, session_id))
        conn.commit()
    return True

def get_sessions():
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]

def save_message(session_id, role, content):
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)',
            (session_id, role, content)
        )
        conn.commit()

def get_chat_history(session_id, limit=SHORT_TERM_WINDOW):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Excludes summary messages by fetching only user/assistant
        cursor.execute('''
            SELECT role, content FROM (
                SELECT role, content, created_at 
                FROM messages 
                WHERE session_id = ? AND role IN ('user', 'assistant') 
                ORDER BY created_at DESC 
                LIMIT ?
            ) ORDER BY created_at ASC
        ''', (session_id, limit))
        return [dict(row) for row in cursor.fetchall()]

def get_full_history(session_id):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content 
            FROM messages 
            WHERE session_id = ? AND role IN ('user', 'assistant') 
            ORDER BY created_at ASC
        ''', (session_id,))
        return [dict(row) for row in cursor.fetchall()]

def upsert_fact(key, value):
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO semantic_facts (key, value) 
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET 
                value=excluded.value,
                updated_at=CURRENT_TIMESTAMP
        ''', (key, value))
        conn.commit()

def get_all_facts():
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM semantic_facts')
        return {row['key']: row['value'] for row in cursor.fetchall()}

def delete_fact(key):
    with get_connection() as conn:
        conn.execute('DELETE FROM semantic_facts WHERE key = ?', (key,))
        conn.commit()

# ── Workout cache helpers ─────────────────────────────────────────────────────

def upsert_workout(record: dict):
    """Insert or update a workout row keyed on (source, activity_id)."""
    record = validate_workout_record(record)
    fields = [
        "activity_id", "source", "workout_type", "date", "workout_title", "duration_min",
        "total_volume_kg", "exercise_count", "set_count",
        "exercises_raw", "muscle_groups", "has_drop_sets", "has_failure_sets",
        "sleep_hours", "sleep_efficiency", "hrv_ms", "resting_hr",
        "readiness_score", "readiness_label",
        "calories", "hr_zones", "distance_km",
    ]
    values = [record.get(f) for f in fields]
    placeholders = ", ".join(["?"] * len(fields))
    updates = ", ".join([f"{f}=excluded.{f}" for f in fields if f not in ("activity_id", "source")])
    sql = f"""
        INSERT INTO workouts ({', '.join(fields)}, synced_at)
        VALUES ({placeholders}, CURRENT_TIMESTAMP)
        ON CONFLICT(source, activity_id) DO UPDATE SET
            {updates},
            synced_at=CURRENT_TIMESTAMP
    """
    with get_connection() as conn:
        conn.execute(sql, values)
        conn.commit()

def get_workouts(n_days: int = 30) -> list:
    """Return workouts from the last N days, newest first."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM workouts
            WHERE date >= date('now', ?)
            ORDER BY date DESC
        """, (f'-{n_days} days',))
        rows = cursor.fetchall()
    return [dict(r) for r in rows]


def get_workouts_filtered(
    start_date: str | None = None,
    end_date: str | None = None,
    title_query: str | None = None,
    min_volume: float | None = None,
    max_volume: float | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list:
    """Return workouts filtered by date, title, and volume, newest first."""
    clauses = []
    params: list[object] = []

    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)
    if title_query:
        clauses.append("LOWER(COALESCE(workout_title, '')) LIKE ?")
        params.append(f"%{title_query.strip().lower()}%")
    if min_volume is not None:
        clauses.append("COALESCE(total_volume_kg, 0) >= ?")
        params.append(float(min_volume))
    if max_volume is not None:
        clauses.append("COALESCE(total_volume_kg, 0) <= ?")
        params.append(float(max_volume))

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_clause = ""
    if limit is not None:
        limit_clause = " LIMIT ? OFFSET ?"
        params.extend([int(limit), max(0, int(offset))])

    sql = f"""
        SELECT * FROM workouts
        {where_clause}
        ORDER BY date DESC, synced_at DESC
        {limit_clause}
    """

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    return [dict(r) for r in rows]

def get_workout_by_date(date_str: str):
    """Return a single workout row for a specific date, or None."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workouts WHERE date = ? LIMIT 1", (date_str,))
        row = cursor.fetchone()
    return dict(row) if row else None

def get_last_synced(source: str):
    """Return last sync timestamp (datetime) for the given source, or None."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT last_synced_at FROM sync_meta WHERE source = ?", (source,))
        row = cursor.fetchone()
    if row and row["last_synced_at"]:
        try:
            return datetime.fromisoformat(row["last_synced_at"])
        except (ValueError, TypeError):
            return None
    return None

def set_last_synced(source: str, synced_at: datetime | None = None):
    """Upsert sync timestamp for the given source.

    If synced_at is None, stores CURRENT_TIMESTAMP. Otherwise stores the provided
    datetime in UTC ISO format to align watermark semantics with ingested data.
    """
    with get_connection() as conn:
        if synced_at is None:
            conn.execute("""
                INSERT INTO sync_meta (source, last_synced_at)
                VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(source) DO UPDATE SET last_synced_at=CURRENT_TIMESTAMP
            """, (source,))
        else:
            if synced_at.tzinfo is None:
                synced_at = synced_at.replace(tzinfo=datetime.UTC)
            synced_at_str = synced_at.astimezone(datetime.UTC).isoformat()
            conn.execute("""
                INSERT INTO sync_meta (source, last_synced_at)
                VALUES (?, ?)
                ON CONFLICT(source) DO UPDATE SET last_synced_at=excluded.last_synced_at
            """, (source, synced_at_str))
        conn.commit()
