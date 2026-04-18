import threading
import time
from src.sync.engine import SyncEngine
from src.utils.logger import app_logger
from config import BACKGROUND_SYNC_INTERVAL

_sync_lock = threading.Lock()

def run_sync_with_lock(force: bool = False):
    """Thread-safe sync execution."""
    with _sync_lock:
        return SyncEngine().sync(force=force)

def background_sync_loop():
    """Continuous background sync loop."""
    while True:
        time.sleep(BACKGROUND_SYNC_INTERVAL)
        try:
            run_sync_with_lock(force=False)
        except Exception as exc:
            app_logger.warning(f"Background sync failed: {exc}")
