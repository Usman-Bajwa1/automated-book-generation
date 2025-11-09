from loguru import logger as my_logger

def get_logger():
    my_logger.add("app.log", rotation="1 MB", level="INFO", format="{time} {level} {message}", backtrace=True, diagnose=True)
    return my_logger

logger = get_logger()