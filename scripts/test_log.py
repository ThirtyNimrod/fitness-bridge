from src.utils.logger import app_logger, ui_logger, get_run_dir
print("Run dir is:", get_run_dir())
app_logger.info("Test app logger")
ui_logger.info("Test ui logger")
