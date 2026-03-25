import logging
import os
import sys
from datetime import datetime

_RUN_DIR = None

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
            
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        _RUN_DIR = os.path.join(logs_base, timestamp)
        os.makedirs(_RUN_DIR, exist_ok=True)
    return _RUN_DIR

def setup_logger(name):
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    run_dir = get_run_dir()
    
    log_file = os.path.join(run_dir, f"{name}.log")
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

app_logger = setup_logger("app")
ui_logger = setup_logger("ui")
