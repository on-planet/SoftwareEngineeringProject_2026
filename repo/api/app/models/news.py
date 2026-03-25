from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


def _split_csv_values(value: str | None) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for raw in str(value or "").split(","):
        text = raw.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    title = Column(String)
    sentiment = Column(String)
    published_at = Column(DateTime)
    link = Column(String)
    source = Column(String)
    source_site = Column(String)
    source_category = Column(String)
    topic_category = Column(String)
    time_bucket = Column(String)
    related_symbols_csv = Column("related_symbols", String)
    related_sectors_csv = Column("related_sectors", String)

    related_symbol_rows = relationship(
        "NewsRelatedSymbol",
        back_populates="news",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="NewsRelatedSymbol.symbol",
    )
    related_sector_rows = relationship(
        "NewsRelatedSector",
        back_populates="news",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="NewsRelatedSector.sector",
    )

    @property
    def related_symbols(self) -> list[str]:
        if self.related_symbol_rows:
            return [item.symbol for item in self.related_symbol_rows if item.symbol]
        return _split_csv_values(self.related_symbols_csv)

    @property
    def related_sectors(self) -> list[str]:
        if self.related_sector_rows:
            return [item.sector for item in self.related_sector_rows if item.sector]
        return _split_csv_values(self.related_sectors_csv)


class NewsRelatedSymbol(Base):
    __tablename__ = "news_related_symbols"

    news_id = Column(Integer, ForeignKey("news.id", ondelete="CASCADE"), primary_key=True)
    symbol = Column(String(32), primary_key=True, index=True)

    news = relationship("News", back_populates="related_symbol_rows")


class NewsRelatedSector(Base):
    __tablename__ = "news_related_sectors"

    news_id = Column(Integer, ForeignKey("news.id", ondelete="CASCADE"), primary_key=True)
    sector = Column(String(64), primary_key=True, index=True)

    news = relationship("News", back_populates="related_sector_rows")
