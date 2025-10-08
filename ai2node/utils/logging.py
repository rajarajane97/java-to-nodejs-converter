import logging
import sys
from pathlib import Path
from typing import Optional

"""Logging helper.

Creates a namespaced logger that writes to stdout with a concise, structured
format. We keep logging setup centralized to avoid duplicate handlers and to
ensure consistent formatting across the application.
"""


def get_logger(level: Optional[str] = None, file_path: Optional[str] = None) -> logging.Logger:
    """Return a configured application logger.

    If called multiple times, returns the same logger without adding duplicate
    handlers. Level defaults to INFO and can be overridden via config/env.
    """
    logger = logging.getLogger("ai2node")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    # Optional file handler
    if file_path:
        try:
            log_path = Path(file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception:
            # Fail open to stdout-only logging
            pass
    logger.setLevel(getattr(logging, (level or "INFO").upper(), logging.INFO))
    logger.propagate = False
    return logger


