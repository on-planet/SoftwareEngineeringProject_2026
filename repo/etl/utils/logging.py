from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Get a standard logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_DIR / "etl.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    return logger
