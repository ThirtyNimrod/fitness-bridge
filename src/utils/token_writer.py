"""
token_writer.py
Writes refreshed API tokens back to .env so they survive restarts.
Called by client classes after a successful token refresh.
"""

import os
import tempfile
import threading

from dotenv import find_dotenv

from src.utils.logger import app_logger

_ENV_WRITE_LOCK = threading.Lock()


def write_token_to_env(key: str, value: str) -> None:
    """
    Read .env, replace the line KEY=... with KEY=new_value, write back.
    Creates the key if it doesn't exist yet.
    """
    env_path = find_dotenv()
    if not env_path:
        app_logger.warning("token_writer: .env file not found — token not persisted.")
        return

    try:
        with _ENV_WRITE_LOCK:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            updated = []
            found = False
            for line in lines:
                if line.startswith(f"{key}="):
                    updated.append(f"{key}={value}\n")
                    found = True
                else:
                    updated.append(line)

            if not found:
                updated.append(f"{key}={value}\n")

            env_dir = os.path.dirname(env_path) or "."
            fd, temp_path = tempfile.mkstemp(prefix=".env.tmp.", dir=env_dir)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as tmp_f:
                    tmp_f.writelines(updated)
                    tmp_f.flush()
                    os.fsync(tmp_f.fileno())
                os.replace(temp_path, env_path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        app_logger.info(f"Token updated in .env: {key}")
    except OSError as e:
        app_logger.error(f"token_writer: could not write .env — {e}")
