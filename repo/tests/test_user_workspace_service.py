from __future__ import annotations

from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.models.base import Base
from app.models.user_stock_pool import UserStockPool, UserStockPoolItem
from app.schemas.user_workspace import StockPoolCreateIn, StockPoolUpdateIn
from app.services.user_workspace_service import (
    create_stock_pool,
    delete_stock_pool,
    list_stock_pools,
    update_stock_pool,
)


class UserWorkspaceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                UserStockPool.__table__,
                UserStockPoolItem.__table__,
            ],
        )
        session_factory = sessionmaker(bind=engine)
        self.db = session_factory()
        self.addCleanup(self.db.close)

    def test_create_stock_pool_persists_relation_rows(self) -> None:
        created = create_stock_pool(
            self.db,
            9,
            StockPoolCreateIn(
                name="growth-pool",
                market="A",
                symbols=["300750.SZ", "300750.sz", " 600000.sh "],
                note="watch",
            ),
        )

        self.assertEqual(created.symbols, ["300750.SZ", "600000.SH"])
        rows = self.db.query(UserStockPoolItem).order_by(UserStockPoolItem.position).all()
        self.assertEqual([(row.symbol, row.position) for row in rows], [("300750.SZ", 0), ("600000.SH", 1)])

    def test_list_stock_pools_falls_back_to_legacy_symbols_json(self) -> None:
        self.db.add(
            UserStockPool(
                user_id=9,
                name="legacy-pool",
                market="A",
                symbols_json='["300750.sz", "300750.SZ", "600000.sh"]',
                note="legacy",
            )
        )
        self.db.commit()

        pools = list_stock_pools(self.db, 9)

        self.assertEqual(len(pools), 1)
        self.assertEqual(pools[0].symbols, ["300750.SZ", "600000.SH"])

    def test_update_stock_pool_replaces_relation_rows_and_clears_legacy_shadow(self) -> None:
        created = create_stock_pool(
            self.db,
            9,
            StockPoolCreateIn(name="rotation-pool", market="A", symbols=["000001.SZ", "600000.SH"]),
        )

        updated = update_stock_pool(
            self.db,
            9,
            created.id,
            StockPoolUpdateIn(symbols=["600000.SH", "000333.SZ", "600000.SH"]),
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.symbols if updated else [], ["600000.SH", "000333.SZ"])
        rows = self.db.query(UserStockPoolItem).order_by(UserStockPoolItem.position).all()
        self.assertEqual([(row.symbol, row.position) for row in rows], [("600000.SH", 0), ("000333.SZ", 1)])
        shadow = self.db.query(UserStockPool).filter(UserStockPool.id == created.id).first()
        self.assertIsNotNone(shadow)
        self.assertEqual(shadow.symbols_json if shadow else None, "[]")

    def test_delete_stock_pool_removes_relation_rows(self) -> None:
        created = create_stock_pool(
            self.db,
            9,
            StockPoolCreateIn(name="delete-pool", market="A", symbols=["000001.SZ", "000333.SZ"]),
        )

        ok = delete_stock_pool(self.db, 9, created.id)

        self.assertTrue(ok)
        self.assertEqual(self.db.query(UserStockPool).count(), 0)
        self.assertEqual(self.db.query(UserStockPoolItem).count(), 0)


if __name__ == "__main__":
    unittest.main()
