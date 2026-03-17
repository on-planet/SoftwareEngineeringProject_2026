from __future__ import annotations

import argparse

from etl.fetchers.market_client import sync_hk_stock_universe, warm_stock_basic_enrichment


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warm local stock basics cache, including HK universe sync.")
    parser.add_argument(
        "--symbols",
        type=str,
        default="",
        help="Optional comma-separated symbols. Default warms all cached stock basics.",
    )
    parser.add_argument(
        "--skip-hk-universe",
        action="store_true",
        help="Skip HK stock universe sync and only warm local A-share enrichment.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    symbols = [item.strip() for item in str(args.symbols or "").split(",") if item.strip()] or None
    hk_count = 0 if args.skip_hk_universe else sync_hk_stock_universe(force=True)
    enrichment_count = warm_stock_basic_enrichment(symbols)
    print({"hk_universe": hk_count, "a_share_enrichment": enrichment_count})


if __name__ == "__main__":
    main()
