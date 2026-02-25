"""
Logger — structured file + database logging with rotating file handler.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR  = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_logger_initialized = False
_app_logger: Optional[logging.Logger] = None


def _init_logger() -> logging.Logger:
    global _logger_initialized, _app_logger
    if _logger_initialized and _app_logger:
        return _app_logger

    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("SFAM")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Rotating file: 10 MB × 5 backups
        fh = RotatingFileHandler(
            LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console (INFO+)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    _logger_initialized = True
    _app_logger = logger
    return logger


class AppLogger:
    """Thin wrapper that writes to both rotating file and SQLite system_logs."""

    def __init__(self):
        self._logger = _init_logger()
        # Lazy DB import to avoid circular dependency on startup
        self._db = None

    def _get_db(self):
        if self._db is None:
            from database.db_manager import DatabaseManager
            self._db = DatabaseManager()
        return self._db

    def _db_log(self, level: str, message: str):
        try:
            self._get_db().add_log(level, message)
        except Exception:
            pass  # never crash the caller

    def debug(self, msg: str):
        self._logger.debug(msg)

    def info(self, msg: str):
        self._logger.info(msg)
        self._db_log("INFO", msg)

    def warning(self, msg: str):
        self._logger.warning(msg)
        self._db_log("WARNING", msg)

    def error(self, msg: str):
        self._logger.error(msg)
        self._db_log("ERROR", msg)

    def critical(self, msg: str):
        self._logger.critical(msg)
        self._db_log("CRITICAL", msg)


# Module-level singleton
logger = AppLogger()
