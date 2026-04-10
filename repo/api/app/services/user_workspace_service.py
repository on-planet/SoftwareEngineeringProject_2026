from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session, selectinload

from app.models.user_saved_stock_filter import UserSavedStockFilter
from app.models.user_stock_pool import UserStockPool, UserStockPoolItem, _deserialize_legacy_symbols
from app.schemas.user_workspace import (
    StockFilterCreateIn,
    StockFilterOut,
    StockFilterUpdateIn,
    StockPoolCreateIn,
    StockPoolOut,
    StockPoolUpdateIn,
)


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def normalize_symbols(symbols: list[str] | None) -> list[str]:
    unique = set()
    result: list[str] = []
    for raw in symbols or []:
        symbol = normalize_symbol(raw)
        if not symbol or symbol in unique:
            continue
        unique.add(symbol)
        result.append(symbol)
        if len(result) >= 200:
            break
    return result


def _build_pool_symbol_rows(symbols: list[str]) -> list[UserStockPoolItem]:
    return [UserStockPoolItem(symbol=symbol, position=index) for index, symbol in enumerate(symbols)]


# 模块级缓存，避免重复检查表是否存在
_table_checked = False

def _ensure_stock_pool_item_table(db: Session) -> None:
    global _table_checked
    if _table_checked:
        return
    
    bind = db.get_bind()
    if inspect(bind).has_table(UserStockPoolItem.__tablename__):
        _table_checked = True
        return

    UserStockPoolItem.__table__.create(bind=bind, checkfirst=True)

    # 优化：使用 selectinload 预加载关联数据，避免 N+1 查询
    legacy_rows = []
    pools = db.query(UserStockPool).options(selectinload(UserStockPool.symbol_rows)).all()
    for pool in pools:
        symbols = normalize_symbols(_deserialize_legacy_symbols(pool.symbols_json))
        for position, symbol in enumerate(symbols):
            legacy_rows.append(UserStockPoolItem(pool_id=int(pool.id), symbol=symbol, position=position))
    if legacy_rows:
        db.bulk_save_objects(legacy_rows)
    db.commit()
    _table_checked = True


def _pool_to_out(item: UserStockPool) -> StockPoolOut:
    return StockPoolOut(
        id=int(item.id),
        name=str(item.name or ""),
        market=str(item.market or "A"),
        symbols=item.symbols,
        note=str(item.note or ""),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _filter_to_out(item: UserSavedStockFilter) -> StockFilterOut:
    return StockFilterOut(
        id=int(item.id),
        name=str(item.name or ""),
        market=str(item.market or "A"),
        keyword=str(item.keyword or ""),
        sector=str(item.sector or ""),
        sort=str(item.sort or "asc"),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def list_stock_pools(db: Session, user_id: int) -> list[StockPoolOut]:
    _ensure_stock_pool_item_table(db)
    rows = (
        db.query(UserStockPool)
        .options(selectinload(UserStockPool.symbol_rows))
        .filter(UserStockPool.user_id == user_id)
        .order_by(UserStockPool.updated_at.desc(), UserStockPool.id.desc())
        .all()
    )
    return [_pool_to_out(item) for item in rows]


def create_stock_pool(db: Session, user_id: int, payload: StockPoolCreateIn) -> StockPoolOut:
    _ensure_stock_pool_item_table(db)
    normalized_symbols = normalize_symbols(payload.symbols)
    item = UserStockPool(
        user_id=user_id,
        name=str(payload.name).strip(),
        market=str(payload.market or "A"),
        symbols_json="[]",
        note=str(payload.note or ""),
        symbol_rows=_build_pool_symbol_rows(normalized_symbols),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _pool_to_out(item)


def update_stock_pool(db: Session, user_id: int, pool_id: int, payload: StockPoolUpdateIn) -> StockPoolOut | None:
    _ensure_stock_pool_item_table(db)
    item = (
        db.query(UserStockPool)
        .options(selectinload(UserStockPool.symbol_rows))
        .filter(UserStockPool.user_id == user_id, UserStockPool.id == pool_id)
        .first()
    )
    if item is None:
        return None
    if payload.name is not None:
        item.name = str(payload.name).strip()
    if payload.market is not None:
        item.market = str(payload.market)
    if payload.symbols is not None:
        item.symbols_json = "[]"
        item.symbol_rows = _build_pool_symbol_rows(normalize_symbols(payload.symbols))
    if payload.note is not None:
        item.note = str(payload.note)
    db.commit()
    db.refresh(item)
    return _pool_to_out(item)


def delete_stock_pool(db: Session, user_id: int, pool_id: int) -> bool:
    _ensure_stock_pool_item_table(db)
    item = (
        db.query(UserStockPool)
        .filter(UserStockPool.user_id == user_id, UserStockPool.id == pool_id)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True


def list_saved_stock_filters(db: Session, user_id: int) -> list[StockFilterOut]:
    rows = (
        db.query(UserSavedStockFilter)
        .filter(UserSavedStockFilter.user_id == user_id)
        .order_by(UserSavedStockFilter.updated_at.desc(), UserSavedStockFilter.id.desc())
        .all()
    )
    return [_filter_to_out(item) for item in rows]


def create_saved_stock_filter(db: Session, user_id: int, payload: StockFilterCreateIn) -> StockFilterOut:
    item = UserSavedStockFilter(
        user_id=user_id,
        name=str(payload.name).strip(),
        market=str(payload.market or "A"),
        keyword=str(payload.keyword or "").strip(),
        sector=str(payload.sector or "").strip(),
        sort=str(payload.sort or "asc"),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _filter_to_out(item)


def update_saved_stock_filter(
    db: Session,
    user_id: int,
    filter_id: int,
    payload: StockFilterUpdateIn,
) -> StockFilterOut | None:
    item = (
        db.query(UserSavedStockFilter)
        .filter(UserSavedStockFilter.user_id == user_id, UserSavedStockFilter.id == filter_id)
        .first()
    )
    if item is None:
        return None
    if payload.name is not None:
        item.name = str(payload.name).strip()
    if payload.market is not None:
        item.market = str(payload.market)
    if payload.keyword is not None:
        item.keyword = str(payload.keyword).strip()
    if payload.sector is not None:
        item.sector = str(payload.sector).strip()
    if payload.sort is not None:
        item.sort = str(payload.sort)
    db.commit()
    db.refresh(item)
    return _filter_to_out(item)


def delete_saved_stock_filter(db: Session, user_id: int, filter_id: int) -> bool:
    item = (
        db.query(UserSavedStockFilter)
        .filter(UserSavedStockFilter.user_id == user_id, UserSavedStockFilter.id == filter_id)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
