from __future__ import annotations

from datetime import date


def download_buyback_file(as_of: date) -> str:
    """Download HKEX buyback disclosure file for the given date.

    Placeholder implementation returns a fake local path.
    """
    return f"/tmp/hkex_buyback_{as_of.isoformat()}.csv"
