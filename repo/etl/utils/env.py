from __future__ import annotations

import os
from pathlib import Path


def load_project_env() -> None:
    project_root = Path(__file__).resolve().parents[3]
    env_file = project_root / ".env.local"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value and key not in os.environ:
            os.environ[key] = value

    if "XUEQIUTOKEN" not in os.environ and "SNOWBALL_TOKEN" in os.environ:
        os.environ["XUEQIUTOKEN"] = os.environ["SNOWBALL_TOKEN"]
    if "SNOWBALL_TOKEN" not in os.environ and "XUEQIUTOKEN" in os.environ:
        os.environ["SNOWBALL_TOKEN"] = os.environ["XUEQIUTOKEN"]
