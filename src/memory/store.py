from src.utils import database
from config import SHORT_TERM_WINDOW

class ShortTermStore:
    def get(self, session_id):
        return database.get_chat_history(session_id, limit=SHORT_TERM_WINDOW)

    def save(self, session_id, role, content):
        database.save_message(session_id, role, content)

class LongTermStore:
    def get(self, session_id):
        with database.get_connection() as conn:
            conn.row_factory = __import__('sqlite3').Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT content FROM messages 
                WHERE session_id = ? AND role = 'summary'
                ORDER BY created_at DESC LIMIT 1
            ''', (session_id,))
            row = cursor.fetchone()
            return row["content"] if row else None

    def save(self, session_id, summary_text):
        database.save_message(session_id, "summary", summary_text)

class SemanticStore:
    def get_all(self):
        return database.get_all_facts()

    def upsert(self, key, value):
        database.upsert_fact(key, value)

    def delete(self, key):
        database.delete_fact(key)

    def format_for_context(self):
        facts = self.get_all()
        if not facts: return ""
        lines = [f"- {k}: {v}" for k, v in facts.items()]
        return "Known facts about the user:\n" + "\n".join(lines)
