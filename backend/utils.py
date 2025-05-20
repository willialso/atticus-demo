# backend/utils.py
import logging
import sys
from backend import config # Import from the same package

def setup_logger(name, level_str=config.LOG_LEVEL):
    """Sets up a configured logger."""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    level = level_map.get(level_str.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if logger already has them
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(config.LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Example usage (will be used in other files):
# from backend.utils import setup_logger
# logger = setup_logger(__name__)
# logger.info("This is an info message from utils.")
