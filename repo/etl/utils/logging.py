from __future__ import annotations

import logging
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
_RESET_DONE = False


def _reset_log_family(log_name: str) -> None:
    pattern = f"{log_name}*"
    for path in LOG_DIR.glob(pattern):
        if not path.is_file():
            continue
        try:
            path.unlink()
        except OSError:
            continue


def _ensure_fresh_log_file() -> Path:
    global _RESET_DONE
    log_path = LOG_DIR / "etl.log"
    if not _RESET_DONE:
        _reset_log_family("etl.log")
        _RESET_DONE = True
    return log_path


def get_logger(name: str) -> logging.Logger:
    """Get a standard logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger.addHandler(console)
    file_path = _ensure_fresh_log_file()
    try:
        file_handler = logging.FileHandler(file_path, mode="w", encoding="utf-8")
    except OSError:
        file_handler = None
    else:
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    return logger
