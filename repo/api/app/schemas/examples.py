from __future__ import annotations

INDEX_PAGE_EXAMPLE = {
    "items": [
        {"symbol": "000001.SH", "name": "上证指数", "market": "A", "date": "2026-03-10", "close": 3123.45, "change": 12.34},
        {"symbol": "HKHSI", "name": "恒生指数", "market": "HK", "date": "2026-03-10", "close": 25465.6, "change": -251.16},
    ],
    "total": 2,
    "limit": 20,
    "offset": 0,
}

NEWS_PAGE_EXAMPLE = {
    "items": [
        {
            "id": 1,
            "symbol": "000001.SH",
            "title": "公司发布业绩预告",
            "sentiment": "positive",
            "published_at": "2026-03-10T08:00:00Z",
        }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
}

STOCK_WITH_RISK_EXAMPLE = {
    "symbol": "000001.SH",
    "name": "平安银行",
    "market": "A",
    "sector": "金融",
    "risk": {
        "symbol": "000001.SH",
        "max_drawdown": -0.12,
        "volatility": 0.24,
        "as_of": "2026-03-10",
    },
}

RISK_EXAMPLE = {
    "symbol": "000001.SH",
    "max_drawdown": -0.12,
    "volatility": 0.24,
    "as_of": "2026-03-10",
}

RISK_SERIES_EXAMPLE = {
    "symbol": "000001.SH",
    "items": [
        {"date": "2026-03-06", "max_drawdown": 0.05, "volatility": 0.2},
        {"date": "2026-03-07", "max_drawdown": 0.06, "volatility": 0.18},
    ],
}

KLINE_SERIES_EXAMPLE = {
    "symbol": "000001.SH",
    "items": [
        {"date": "2026-03-06", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2},
        {"date": "2026-03-07", "open": 10.2, "high": 10.6, "low": 10.0, "close": 10.4},
    ],
}

HEATMAP_PAGE_EXAMPLE = {
    "items": [
        {"sector": "金融", "avg_close": 10.2, "avg_change": 0.12},
        {"sector": "科技", "avg_close": 28.5, "avg_change": -0.34},
    ],
    "total": 2,
    "limit": 20,
    "offset": 0,
}

MACRO_PAGE_EXAMPLE = {
    "items": [
        {"key": "CPI", "date": "2026-03-10", "value": 1.23, "score": 0.62},
        {"key": "CPI", "date": "2026-02-10", "value": 1.21, "score": 0.58},
    ],
    "total": 2,
    "limit": 20,
    "offset": 0,
}

BUYBACK_PAGE_EXAMPLE = {
    "items": [
        {"symbol": "00005.HK", "date": "2026-03-10", "amount": 1000000.0}
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
}

INSIDER_PAGE_EXAMPLE = {
    "items": [
        {"id": 1, "symbol": "000001.SH", "date": "2026-03-10", "type": "buy", "shares": 100000.0}
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
}

FINANCIALS_PAGE_EXAMPLE = {
    "items": [
        {
            "symbol": "000001.SH",
            "period": "2025Q4",
            "revenue": 1000000000.0,
            "net_income": 120000000.0,
            "cash_flow": 150000000.0,
            "roe": 0.12,
            "debt_ratio": 0.35,
        }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
}

PORTFOLIO_PAGE_EXAMPLE = {
    "items": [
        {"user_id": 1, "symbol": "000001.SH", "avg_cost": 9.5, "shares": 1000.0},
        {"user_id": 1, "symbol": "00005.HK", "avg_cost": 45.3, "shares": 200.0},
    ],
    "total": 2,
    "limit": 20,
    "offset": 0,
}

INDICATOR_SERIES_EXAMPLE = {
    "symbol": "000001.SH",
    "indicator": "ma",
    "window": 5,
    "items": [
        {"date": "2026-03-06", "value": 10.1},
        {"date": "2026-03-07", "value": 10.3},
        {"date": "2026-03-10", "value": 10.4},
    ],
}

PORTFOLIO_ANALYSIS_EXAMPLE = {
    "user_id": 1,
    "items": [
        {
            "symbol": "000001.SH",
            "shares": 1000.0,
            "avg_cost": 9.5,
            "latest_price": 10.2,
            "pnl": 700.0,
            "pnl_pct": 0.0737,
            "sector": "金融",
        }
    ],
    "summary": {
        "total_cost": 9500.0,
        "total_value": 10200.0,
        "total_pnl": 700.0,
        "total_pnl_pct": 0.0737,
    },
    "sector_exposure": [
        {"sector": "金融", "value": 10200.0, "weight": 1.0}
    ],
    "top_holdings": [
        {"symbol": "000001.SH", "value": 10200.0, "weight": 1.0}
    ],
}

MACRO_SERIES_EXAMPLE = {
    "key": "CPI",
    "items": [
        {"date": "2026-03-01", "value": 1.23, "score": 0.6},
        {"date": "2026-03-10", "value": 1.25, "score": 0.63},
    ],
}

INDEX_CONSTITUENTS_EXAMPLE = {
    "items": [
        {
            "index_symbol": "HKHSI",
            "symbol": "00005.HK",
            "date": "2026-03-10",
            "weight": None,
            "name": "汇丰控股",
            "market": "HK",
            "rank": 1,
            "contribution_change": -97.0,
            "source": "Hang Seng Indexes",
        }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0,
}

SECTOR_EXPOSURE_EXAMPLE = {
    "market": "A",
    "as_of": "2026-03-16",
    "basis": "market_value",
    "total_value": 24200.0,
    "coverage": 0.91,
    "unknown_weight": 0.03,
    "items": [
        {"sector": "科技", "value": 14000.0, "weight": 0.58, "symbol_count": 18},
        {"sector": "金融", "value": 10200.0, "weight": 0.42, "symbol_count": 12},
    ],
}

FUTURES_PAGE_EXAMPLE = {
    "items": [
        {
            "symbol": "AU",
            "name": "黄金",
            "date": "2026-03-10",
            "contract_month": "2606",
            "open": 546.18,
            "high": 548.62,
            "low": 544.56,
            "close": 547.94,
            "settlement": 548.01,
            "open_interest": 178365.0,
            "turnover": 3319.4,
            "volume": 290419.0,
            "source": "SHFE",
        },
        {
            "symbol": "SC",
            "name": "原油",
            "date": "2026-03-10",
            "contract_month": "2605",
            "open": 520.8,
            "high": 528.6,
            "low": 517.3,
            "close": 525.4,
            "settlement": 524.9,
            "open_interest": 303871.0,
            "turnover": 2273.9,
            "volume": 303871.0,
            "source": "SHFE",
        },
    ],
    "total": 2,
    "limit": 20,
    "offset": 0,
}

FUTURES_SERIES_EXAMPLE = {
    "symbol": "AU",
    "items": [
        {"date": "2026-03-06", "contract_month": "2606", "open": 541.88, "high": 544.46, "low": 540.12, "close": 543.36, "settlement": 543.4, "open_interest": 172300.0, "turnover": 3200.1, "volume": 262541.0, "source": "SHFE"},
        {"date": "2026-03-07", "contract_month": "2606", "open": 543.40, "high": 546.52, "low": 542.36, "close": 545.88, "settlement": 545.9, "open_interest": 176020.0, "turnover": 3256.4, "volume": 275160.0, "source": "SHFE"},
        {"date": "2026-03-10", "contract_month": "2606", "open": 546.18, "high": 548.62, "low": 544.56, "close": 547.94, "settlement": 548.01, "open_interest": 178365.0, "turnover": 3319.4, "volume": 290419.0, "source": "SHFE"},
    ],
}

ERROR_EXAMPLE = {"code": "NOT_FOUND", "message": "Not found"}
