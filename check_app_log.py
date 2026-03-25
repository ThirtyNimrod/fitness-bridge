from src.utils.logger import ui_logger, app_logger, get_run_dir
print("App run dir is:", get_run_dir())
app_logger.info("Initializing app logger test")
ui_logger.info("Initializing ui logger test")
