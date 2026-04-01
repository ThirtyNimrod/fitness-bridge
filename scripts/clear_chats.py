"""
clear_chats.py
Removes all chat sessions and messages from the local SQLite database.

Run from the project root:
    python scripts/clear_chats.py

Options:
    --force    Skip the confirmation prompt (useful for automation)
"""

import os
import sys
import argparse

# Resolve project root (one level above scripts/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.utils.database import get_connection  # noqa: E402


def clear_all_chats(force: bool = False) -> None:
    with get_connection() as conn:
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    if session_count == 0 and msg_count == 0:
        print("✅ Database is already empty — nothing to clear.")
        return

    print(f"\n  Found {session_count} session(s) and {msg_count} message(s).")

    if not force:
        answer = input("\n  ⚠️  This will permanently delete all chat history. Type 'yes' to confirm: ")
        if answer.strip().lower() != "yes":
            print("\n  Aborted — no changes made.")
            return

    with get_connection() as conn:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.commit()

    print(f"\n  ✅ Cleared {session_count} session(s) and {msg_count} message(s) from the database.")
    print("     Restart the app to start with a fresh chat history.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear all chat sessions from the Fitness Bridge database.")
    parser.add_argument("--force", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()

    clear_all_chats(force=args.force)
