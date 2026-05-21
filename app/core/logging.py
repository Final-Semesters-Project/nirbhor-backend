import logging
from types import FrameType
from typing import Optional
from loguru import logger
import sys
from app.core.config import settings


class InterceptHandler(logging.Handler):
    """
    Intercepts standard Python logging (FastAPI, SQLAlchemy, uvicorn)
    and routes everything through Loguru for unified formatting and color.
    """

    def emit(self, record: logging.LogRecord):
        # map standard logging level to Loguru level name
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where originated the logged message
        frame: Optional[FrameType] = logging.currentframe()
        depth: int = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Print message using Loguru
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage())


# call the setup_logging function at the top of the main.py (before app = FastAPI() call)
def setup_logging():
    # remove default loggers of Loguru
    logger.remove()

    is_dev = settings.APP_ENV == "development"

    # ── Custom level colors ────────────────────────────────────────────
    # Loguru allows overriding colors per level
    logger.level("DEBUG", color="<cyan>")
    logger.level("INFO", color="<blue>")
    logger.level("SUCCESS", color="<green><bold>")
    logger.level("WARNING", color="<yellow><bold>")
    logger.level("ERROR", color="<red><bold>")
    # white text, red background
    logger.level("CRITICAL", color="<WHITE><bold><red>")

    # ── Format ────────────────────────────────────────────────────────
    # {level: <8} = left-align level name, padded to 8 chars (keeps columns clean)
    dev_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Simpler format for production (no colors, structured for log aggregators)
    prod_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
        "{name}:{function}:{line} | {message}"
    )

    # set new format for terminal
    logger.add(
        sys.stderr,
        # colors only in dev (prod logs go to files/aggregators)
        colorize=True if is_dev else False,
        format=dev_format if is_dev else prod_format,
        level="DEBUG" if is_dev else "INFO",
        backtrace=is_dev,  # show full traceback in dev only
        diagnose=is_dev,  # show variable values in tracebacks in dev only
    )

    # ── File handler (production) -> doesn't need for render ────────────────────────────
    # if not is_dev:
    #     logger.add(
    #         "logs/app.log",
    #         rotation="10 MB",     # new file every 10MB
    #         retention="30 days",  # delete logs older than 30 days
    #         compression="zip",    # compress old logs
    #         colorize=False,
    #         format=prod_format,
    #         level="INFO",
    #         backtrace=False,
    #         diagnose=False,       # never expose variable values in prod logs
    #     )

    # ── Intercept standard library logging ────────────────────────────
    # This captures uvicorn, FastAPI, SQLAlchemy logs and routes to loguru
    logging.basicConfig(
        handlers=[InterceptHandler()],
        level=0,  # capture everything, loguru filters by its own level
        force=True  # override any existing handlers
    )

    # SQLAlchemy: WARNING only (we set echo=False in engine, this is the backup)
    # Change to INFO temporarily if you need to debug a specific query
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    # Uvicorn access logs — INFO in dev, WARNING in prod
    logging.getLogger("uvicorn.access").setLevel(
        logging.INFO if is_dev else logging.WARNING
    )
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    return logger


# use case in other files
"""
from loguru import logger

logger.debug("Debugging something")
logger.info("Server started")
logger.success("Student created successfully")   # ← loguru only
logger.warning("Rating is low")
logger.error("Database connection failed")
logger.critical("System is down")
"""
