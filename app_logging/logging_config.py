import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logging():

    os.makedirs("logs/", exist_ok=True)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    file_handler = RotatingFileHandler(
        'logs/app_yam-indexing.log',
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=15,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().handlers.clear()  # important in Docker
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().addHandler(console_handler)

if __name__ == "__main__":
    # Test the configuration
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")