from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable

from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


@dataclass
class AlertConfig:
    enabled: bool
    channel: str


def load_alert_config() -> AlertConfig:
    enabled = os.getenv("ALERT_ENABLED", "false").lower() in {"1", "true", "yes"}
    channel = os.getenv("ALERT_CHANNEL", "stdout")
    return AlertConfig(enabled=enabled, channel=channel)


def notify_error(title: str, message: str) -> None:
    config = load_alert_config()
    if not config.enabled:
        return
    LOGGER.error("ALERT[%s] %s: %s", config.channel, title, message)


def notify_batch(errors: Iterable[str]) -> None:
    config = load_alert_config()
    if not config.enabled:
        return
    for msg in errors:
        LOGGER.error("ALERT[%s] %s", config.channel, msg)
