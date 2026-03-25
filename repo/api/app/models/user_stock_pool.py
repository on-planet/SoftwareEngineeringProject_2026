from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


def _normalize_legacy_symbols(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        symbol = str(raw or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return result


def _deserialize_legacy_symbols(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    return _normalize_legacy_symbols([str(item or "") for item in payload])


class UserStockPool(Base):
    __tablename__ = "user_stock_pools"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    market = Column(String(16), nullable=False, default="A")
    symbols_json = Column(Text, nullable=False, default="[]")
    note = Column(String(512), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    symbol_rows = relationship(
        "UserStockPoolItem",
        back_populates="pool",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="UserStockPoolItem.position, UserStockPoolItem.symbol",
    )

    @property
    def symbols(self) -> list[str]:
        if self.symbol_rows:
            return [item.symbol for item in self.symbol_rows if item.symbol]
        return _deserialize_legacy_symbols(self.symbols_json)


class UserStockPoolItem(Base):
    __tablename__ = "user_stock_pool_items"

    pool_id = Column(Integer, ForeignKey("user_stock_pools.id", ondelete="CASCADE"), primary_key=True)
    symbol = Column(String(32), primary_key=True, index=True)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    pool = relationship("UserStockPool", back_populates="symbol_rows")
