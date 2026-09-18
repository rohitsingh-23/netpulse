"""Logging configuration for NetPulse.

Provides a reusable logger setup for a desktop application.
Logs to stderr by default, with optional file output.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from netpulse.utils.constants import APP_NAME

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s.%(module)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure application-wide logging.

    Safe to call multiple times — handlers are only added once.

    Args:
        level: Minimum log level for stderr output.
        log_file: Optional path to a log file. Parent dirs created automatically.

    Returns:
        The root application logger.
    """
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(level)
    logger.addHandler(stderr_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the application namespace.

    Args:
        name: Module or component name.

    Returns:
        Logger named ``NetPulse.<name>``.
    """
    return logging.getLogger(f"{APP_NAME}.{name}")
