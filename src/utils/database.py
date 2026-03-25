import sqlite3
import os
import uuid
import json
from datetime import datetime
from config import DB_PATH, SHORT_TERM_WINDOW

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
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
        # Workouts cache table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                activity_id      TEXT PRIMARY KEY,
                date             TEXT NOT NULL,
                workout_title    TEXT,
                duration_min     REAL,
                total_volume_kg  REAL,
                exercise_count   INTEGER,
                set_count        INTEGER,
                exercises_raw    TEXT,
                muscle_groups    TEXT,
                has_drop_sets    INTEGER,
                has_failure_sets INTEGER,
                sleep_hours      REAL,
                sleep_efficiency REAL,
                hrv_ms           REAL,
                resting_hr       REAL,
                readiness_score  REAL,
                readiness_label  TEXT,
                synced_at        DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Sync metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_meta (
                source         TEXT PRIMARY KEY,
                last_synced_at DATETIME
            )
        ''')

        conn.commit()

def create_session(title="New Session"):
    session_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute('INSERT INTO sessions (id, title) VALUES (?, ?)', (session_id, title))
        conn.commit()
    return session_id

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
    """Insert or update a workout row keyed on activity_id."""
    fields = [
        "activity_id", "date", "workout_title", "duration_min",
        "total_volume_kg", "exercise_count", "set_count",
        "exercises_raw", "muscle_groups", "has_drop_sets", "has_failure_sets",
        "sleep_hours", "sleep_efficiency", "hrv_ms", "resting_hr",
        "readiness_score", "readiness_label",
    ]
    values = [record.get(f) for f in fields]
    placeholders = ", ".join(["?"] * len(fields))
    updates = ", ".join([f"{f}=excluded.{f}" for f in fields if f != "activity_id"])
    sql = f"""
        INSERT INTO workouts ({', '.join(fields)}, synced_at)
        VALUES ({placeholders}, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
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

def set_last_synced(source: str):
    """Upsert sync timestamp to now for the given source."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO sync_meta (source, last_synced_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(source) DO UPDATE SET last_synced_at=CURRENT_TIMESTAMP
        """, (source,))
        conn.commit()
