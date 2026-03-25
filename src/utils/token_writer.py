"""
token_writer.py
Writes refreshed API tokens back to .env so they survive restarts.
Called by client classes after a successful token refresh.
"""

from dotenv import find_dotenv
from src.utils.logger import app_logger


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

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(updated)

        app_logger.info(f"Token updated in .env: {key}")
    except OSError as e:
        app_logger.error(f"token_writer: could not write .env — {e}")
