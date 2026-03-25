from loguru import logger
import sys
import os
import time
import logging

# Set timezone to IST
os.environ['TZ'] = 'Asia/Kolkata'
if hasattr(time, 'tzset'):
    time.tzset()

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add(
    os.path.join(LOG_DIR, "app_{time:YYYY-MM-DD}.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="00:00",
    retention="7 days",
    compression="zip",
    level="DEBUG",
    encoding="utf-8",
)

# Intercept standard logging
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# Intercept Uvicorn loggers explicitly to ensure they use our format and timezone
for log_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
    logging_logger = logging.getLogger(log_name)
    logging_logger.handlers = [InterceptHandler()]
    logging_logger.propagate = False
