from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class EtlConfig:
    postgres_url: str
    redis_url: str
    timezone: str
    t1_offset_days: int
    raw: dict
    postgres_pool_size: int = 5
    postgres_max_overflow: int = 5


def load_config(path: str | Path) -> EtlConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return EtlConfig(
        postgres_url=raw["postgres"]["url"],
        redis_url=raw["redis"]["url"],
        timezone=raw["market"]["timezone"],
        t1_offset_days=raw["market"]["t1_offset_days"],
        raw=raw,
        postgres_pool_size=raw["postgres"].get("pool_size", 5),
        postgres_max_overflow=raw["postgres"].get("max_overflow", 5),
    )
