import logging
import os
import re
import sys
from datetime import datetime, timedelta

_RUN_DIR = None
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "14"))


class RedactionFilter(logging.Filter):
    """Redacts common secret/token values before logs are persisted."""

    _PATTERNS = [
        re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([A-Za-z0-9._\-]+)"),
        re.compile(r"(?i)(access_token\s*[=:]\s*)([^\s,;]+)"),
        re.compile(r"(?i)(refresh_token\s*[=:]\s*)([^\s,;]+)"),
        re.compile(r"(?i)(client_secret\s*[=:]\s*)([^\s,;]+)"),
    ]

    def filter(self, record):
        message = record.getMessage()
        redacted = self._redact(message)

        record.msg = redacted
        record.args = ()
        return True

    def _redact(self, message: str) -> str:
        output = message
        for pattern in self._PATTERNS:
            output = pattern.sub(r"\1[REDACTED]", output)
        return output

def is_test_environment():
    """Detect if we're running under pytest"""
    return "pytest" in sys.modules or "test" in sys.argv[0].lower() or "pytest" in sys.argv[0].lower()

def get_run_dir():
    global _RUN_DIR
    if _RUN_DIR is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if is_test_environment():
            logs_base = os.path.join(base_dir, "tests", "testing-logs")
        else:
            logs_base = os.path.join(base_dir, "logs")
        _cleanup_old_log_dirs(logs_base)
            
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        _RUN_DIR = os.path.join(logs_base, timestamp)
        os.makedirs(_RUN_DIR, exist_ok=True)
    return _RUN_DIR


def _cleanup_old_log_dirs(logs_base):
    if LOG_RETENTION_DAYS <= 0:
        return

    try:
        if not os.path.isdir(logs_base):
            return

        cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
        for dirname in os.listdir(logs_base):
            full_path = os.path.join(logs_base, dirname)
            if not os.path.isdir(full_path):
                continue
            try:
                dir_time = datetime.strptime(dirname, "%Y%m%d-%H%M")
            except ValueError:
                continue
            if dir_time < cutoff:
                import shutil
                shutil.rmtree(full_path, ignore_errors=True)
    except OSError:
        # Logging setup should never fail because cleanup couldn't run.
        return

def setup_logger(name):
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    redaction_filter = RedactionFilter()
    
    run_dir = get_run_dir()
    
    log_file = os.path.join(run_dir, f"{name}.log")
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redaction_filter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redaction_filter)
    logger.addHandler(console_handler)
    
    return logger

app_logger = setup_logger("app")
ui_logger = setup_logger("ui")
