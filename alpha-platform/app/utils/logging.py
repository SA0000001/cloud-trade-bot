"""
Logging configuration for the platform.
Call setup_logging() once at application startup.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configure root logger with a clean, structured format.

    Format: [TIMESTAMP] LEVEL     module_name — message

    Args:
        level: Logging level string ("DEBUG", "INFO", "WARNING", etc.)
        log_file: Optional file path to also write logs to.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)-35s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(fmt)
    root_logger.addHandler(console)

    # File handler (optional)
    if log_file:
        from pathlib import Path
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)

    # Quiet noisy third-party loggers
    for noisy in ["httpx", "httpcore", "sqlalchemy.engine", "urllib3"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialized. level=%s file=%s", level, log_file or "none"
    )
