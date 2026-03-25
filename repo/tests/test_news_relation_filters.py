from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.models.base import Base
from app.models.news import News, NewsRelatedSector, NewsRelatedSymbol
from app.schemas.news import NewsCreate, NewsUpdate
from app.services.news_aggregate_service import list_news_aggregate
from app.services.news_service import create_news, list_news, update_news


class NewsRelationFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                News.__table__,
                NewsRelatedSymbol.__table__,
                NewsRelatedSector.__table__,
            ],
        )
        session_factory = sessionmaker(bind=engine)
        self.db = session_factory()

        self.cache_patches = [
            patch("app.services.news_service.get_json", return_value=None),
            patch("app.services.news_service.set_json"),
            patch("app.services.news_aggregate_service.get_json", return_value=None),
            patch("app.services.news_aggregate_service.set_json"),
        ]
        for patcher in self.cache_patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.db.close)

    def test_create_and_update_news_sync_relation_rows(self) -> None:
        created = create_news(
            self.db,
            NewsCreate(
                symbol="000001.SH",
                title="AI server demand remains strong",
                sentiment="positive",
                published_at=datetime(2026, 3, 24, 9, 0, 0),
                related_symbols=["NVDA.US", "AMD.US"],
                related_sectors="科技, 半导体",
            ),
        )

        self.assertEqual(created.related_symbols_csv, "NVDA.US,AMD.US")
        self.assertEqual(created.related_sectors_csv, "科技,半导体")
        self.assertEqual(
            [row.symbol for row in self.db.query(NewsRelatedSymbol).order_by(NewsRelatedSymbol.symbol).all()],
            ["AMD.US", "NVDA.US"],
        )
        self.assertEqual(
            [row.sector for row in self.db.query(NewsRelatedSector).order_by(NewsRelatedSector.sector).all()],
            ["半导体", "科技"],
        )

        updated = update_news(
            self.db,
            created.id,
            NewsUpdate(
                related_symbols=["TSLA.US"],
                related_sectors=["新能源"],
            ),
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.related_symbols, ["TSLA.US"])
        self.assertEqual(updated.related_sectors, ["新能源"])
        self.assertEqual(
            [row.symbol for row in self.db.query(NewsRelatedSymbol).order_by(NewsRelatedSymbol.symbol).all()],
            ["TSLA.US"],
        )
        self.assertEqual(
            [row.sector for row in self.db.query(NewsRelatedSector).order_by(NewsRelatedSector.sector).all()],
            ["新能源"],
        )

    def test_list_news_filters_by_related_symbol_rows_and_returns_arrays(self) -> None:
        create_news(
            self.db,
            NewsCreate(
                symbol="000001.SH",
                title="Chip cycle improved",
                sentiment="positive",
                published_at=datetime(2026, 3, 24, 8, 0, 0),
                related_symbols=["NVDA.US", "AMD.US"],
                related_sectors=["科技"],
            ),
        )
        create_news(
            self.db,
            NewsCreate(
                symbol="000001.SH",
                title="Bank earnings steady",
                sentiment="neutral",
                published_at=datetime(2026, 3, 24, 7, 0, 0),
                related_symbols=["JPM.US"],
                related_sectors=["金融"],
            ),
        )

        items, total = list_news(self.db, "000001.SH", related_symbols=["NVDA.US"])

        self.assertEqual(total, 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Chip cycle improved")
        self.assertEqual(items[0]["related_symbols"], ["AMD.US", "NVDA.US"])
        self.assertEqual(items[0]["related_sectors"], ["科技"])

    def test_list_news_aggregate_filters_by_related_sector_rows(self) -> None:
        create_news(
            self.db,
            NewsCreate(
                symbol="000001.SH",
                title="AI capex expands",
                sentiment="positive",
                published_at=datetime(2026, 3, 24, 10, 0, 0),
                related_symbols=["NVDA.US"],
                related_sectors=["科技"],
            ),
        )
        create_news(
            self.db,
            NewsCreate(
                symbol="00700.HK",
                title="Cloud demand supports internet names",
                sentiment="positive",
                published_at=datetime(2026, 3, 24, 11, 0, 0),
                related_symbols=["MSFT.US"],
                related_sectors=["科技"],
            ),
        )
        create_news(
            self.db,
            NewsCreate(
                symbol="600036.SH",
                title="Banks focus on margins",
                sentiment="neutral",
                published_at=datetime(2026, 3, 24, 12, 0, 0),
                related_symbols=["JPM.US"],
                related_sectors=["金融"],
            ),
        )

        items, total = list_news_aggregate(self.db, related_sectors=["科技"])

        self.assertEqual(total, 2)
        self.assertEqual([item["symbol"] for item in items], ["00700.HK", "000001.SH"])
        self.assertTrue(all(item["related_sectors"] == ["科技"] for item in items))


if __name__ == "__main__":
    unittest.main()
