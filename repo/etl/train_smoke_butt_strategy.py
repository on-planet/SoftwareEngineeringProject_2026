from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from etl.utils.env import load_project_env

load_project_env()

from app.core.db import SessionLocal
from app.services.smoke_butt_strategy_service import train_smoke_butt_strategy


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train AutoGluon smoke-butt strategy and persist ranked scores.")
    parser.add_argument("--as-of", type=str, default=None, help="Strategy anchor date in YYYY-MM-DD format.")
    parser.add_argument("--horizon-days", type=int, default=60, help="Forward return horizon in trading days.")
    parser.add_argument("--sample-step", type=int, default=21, help="Training sample spacing in trading days.")
    parser.add_argument("--time-limit-seconds", type=int, default=120, help="AutoGluon fit time budget.")
    parser.add_argument("--force-retrain", action="store_true", help="Ignore existing same-day run and retrain.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    target_date = date.fromisoformat(args.as_of) if args.as_of else None
    with SessionLocal() as db:
        run, items = train_smoke_butt_strategy(
            db,
            as_of=target_date,
            horizon_days=args.horizon_days,
            sample_step=args.sample_step,
            time_limit_seconds=args.time_limit_seconds,
            force_retrain=args.force_retrain,
        )
    print(f"run_id={run['id']} as_of={run['as_of']} train_rows={run['train_rows']} scored_rows={run['scored_rows']}")
    for item in items[:10]:
        print(
            f"{item['rank']:>3} {item['symbol']:<12} score={item['score']:.2f} "
            f"expected_return={(item['expected_return'] or 0.0):.4f}"
        )


if __name__ == "__main__":
    main()
