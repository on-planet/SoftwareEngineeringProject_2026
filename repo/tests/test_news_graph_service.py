from __future__ import annotations

from datetime import date, datetime
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
from app.models.events import Event
from app.models.news import News, NewsRelatedSector, NewsRelatedSymbol
from app.models.stocks import Stock
from app.schemas.news import NewsCreate
from app.services.news_graph_service import build_news_focus_graph, build_stock_news_graph
from app.services.news_service import create_news


class NewsGraphServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                Stock.__table__,
                News.__table__,
                NewsRelatedSymbol.__table__,
                NewsRelatedSector.__table__,
                Event.__table__,
            ],
        )
        session_factory = sessionmaker(bind=engine)
        self.db = session_factory()
        self.addCleanup(self.db.close)

        self.db.add(Stock(symbol="000001.SH", name="平安银行", market="A", sector="金融"))
        self.db.add(Stock(symbol="600036.SH", name="招商银行", market="A", sector="金融"))
        self.db.add(
            Event(
                id=101,
                symbol="000001.SH",
                type="earnings",
                title="平安银行发布业绩预告",
                date=date(2026, 3, 24),
                link="https://example.com/event",
                source="exchange",
            )
        )
        self.db.commit()

        create_news(
            self.db,
            NewsCreate(
                symbol="000001.SH",
                title="平安银行回购计划带动银行板块走强",
                sentiment="positive",
                published_at=datetime(2026, 3, 24, 9, 0, 0),
                source="Example Feed",
                related_symbols=["000001.SH", "600036.SH"],
                related_sectors=["金融"],
                event_type="buyback",
                event_tags=["buyback", "shareholder_return"],
                themes=["银行"],
                impact_direction="positive",
                nlp_confidence=0.82,
                nlp_version="rule-nlp-v1",
                keywords=["回购", "银行板块"],
            ),
        )
        create_news(
            self.db,
            NewsCreate(
                symbol="ALL",
                title="银行股受政策支持集体上涨",
                sentiment="positive",
                published_at=datetime(2026, 3, 25, 10, 0, 0),
                source="Example Feed",
                related_symbols=["000001.SH", "600036.SH"],
                related_sectors=["金融"],
                event_type="policy",
                event_tags=["policy_support"],
                themes=["银行"],
                impact_direction="positive",
                nlp_confidence=0.74,
                nlp_version="rule-nlp-v1",
                keywords=["政策支持", "银行"],
            ),
        )

    def test_build_stock_news_graph_links_news_sector_event_and_theme(self) -> None:
        with patch("app.services.news_graph_service.chat_completion", return_value=None):
            payload = build_stock_news_graph(self.db, "000001.SH", days=7, limit=10)

        node_types = {item.type for item in payload.nodes}
        edge_types = {item.type for item in payload.edges}
        self.assertEqual(payload.center_type, "stock")
        self.assertEqual(payload.center_id, "000001.SH")
        self.assertIn("stock", node_types)
        self.assertIn("news", node_types)
        self.assertIn("sector", node_types)
        self.assertIn("event", node_types)
        self.assertIn("theme", node_types)
        self.assertIn("mentions", edge_types)
        self.assertIn("event_of", edge_types)
        self.assertEqual(payload.explanation.generated_by, "template")
        self.assertGreaterEqual(len(payload.related_news), 2)
        self.assertEqual(payload.related_events[0].id, 101)

    def test_build_news_focus_graph_uses_llm_when_available(self) -> None:
        with patch(
            "app.services.news_graph_service.chat_completion",
            return_value='{"headline":"银行主题传播持续扩散","evidence":["同主题新闻继续增加","板块和个股节点同时被激活"],"risk_hint":"若政策预期降温，传播强度可能回落"}',
        ):
            payload = build_news_focus_graph(self.db, 1, days=7, limit=5)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload.center_type, "news")
        self.assertEqual(payload.explanation.generated_by, "llm")
        self.assertEqual(payload.explanation.headline, "银行主题传播持续扩散")
        self.assertTrue(payload.explanation.evidence)


    def test_build_stock_news_graph_prefers_direct_symbol_news_over_sector_only_fillers(self) -> None:
        create_news(
            self.db,
            NewsCreate(
                symbol="ALL",
                title="Sector only filler",
                sentiment="neutral",
                published_at=datetime(2026, 3, 26, 9, 0, 0),
                source="Example Feed",
                related_symbols=["601398.SH"],
                related_sectors=["閲戣瀺"],
                event_type="roundup",
                event_tags=["roundup"],
                themes=["market"],
                impact_direction="neutral",
                nlp_confidence=0.52,
                nlp_version="rule-nlp-v1",
                keywords=["sector"],
            ),
        )

        with patch("app.services.news_graph_service.chat_completion", return_value=None):
            payload = build_stock_news_graph(self.db, "000001.SH", days=7, limit=2)

        titles = [item.title for item in payload.related_news]
        self.assertEqual(len(titles), 2)
        self.assertNotIn("Sector only filler", titles)

    def test_build_news_focus_graph_filters_related_news_by_real_overlap(self) -> None:
        create_news(
            self.db,
            NewsCreate(
                symbol="600036.SH",
                title="Second symbol overlap",
                sentiment="positive",
                published_at=datetime(2026, 3, 26, 11, 0, 0),
                source="Example Feed",
                related_symbols=["600036.SH"],
                related_sectors=["Brokerage"],
                event_type="buyback",
                event_tags=["buyback"],
                themes=["expansion"],
                impact_direction="positive",
                nlp_confidence=0.76,
                nlp_version="rule-nlp-v1",
                keywords=["peer"],
            ),
        )
        create_news(
            self.db,
            NewsCreate(
                symbol="ALL",
                title="Weak sector overlap",
                sentiment="neutral",
                published_at=datetime(2026, 3, 26, 10, 30, 0),
                source="Example Feed",
                related_symbols=["601398.SH"],
                related_sectors=["閲戣瀺"],
                event_type="roundup",
                event_tags=["roundup"],
                themes=["opening"],
                impact_direction="neutral",
                nlp_confidence=0.4,
                nlp_version="rule-nlp-v1",
                keywords=["opening"],
            ),
        )

        with patch("app.services.news_graph_service.chat_completion", return_value=None):
            payload = build_news_focus_graph(self.db, 1, days=7, limit=5)

        self.assertIsNotNone(payload)
        assert payload is not None
        titles = [item.title for item in payload.related_news]
        self.assertIn("Second symbol overlap", titles)
        self.assertNotIn("Weak sector overlap", titles)
        self.assertNotIn("骞冲畨閾惰鍥炶喘璁″垝甯﹀姩閾惰鏉垮潡璧板己", titles)

if __name__ == "__main__":
    unittest.main()
