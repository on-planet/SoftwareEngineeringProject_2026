from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.loaders.pg_loader import _get_loader


A_SHARE_INDEX_SYMBOLS = ("000016.SH", "000300.SH", "000688.SH", "899050.BJ")


def run() -> list[dict]:
    loader = _get_loader()
    quoted = ", ".join(f"'{symbol}'" for symbol in A_SHARE_INDEX_SYMBOLS)
    loader.execute(
        f"""
        UPDATE index_constituents
        SET weight = weight / 100.0
        WHERE index_symbol IN ({quoted})
          AND weight IS NOT NULL
          AND weight != 0
        """
    )
    return loader.query_all(
        """
        SELECT index_symbol,
               COUNT(*) AS n,
               MIN(weight) AS min_w,
               MAX(weight) AS max_w,
               SUM(weight) AS sum_w
        FROM index_constituents
        GROUP BY index_symbol
        ORDER BY index_symbol
        """
    )


if __name__ == "__main__":
    for row in run():
        print(row)
