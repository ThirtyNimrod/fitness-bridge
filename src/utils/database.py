import sqlite3
import os
import uuid
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
