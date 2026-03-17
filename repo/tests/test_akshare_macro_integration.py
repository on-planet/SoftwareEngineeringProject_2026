from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

if "pydantic_settings" not in sys.modules:
    fake_module = types.ModuleType("pydantic_settings")

    class BaseSettings:  # pragma: no cover - import shim for tests
        def __init__(self, **kwargs):
            annotations: dict[str, object] = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for key in annotations:
                if key in kwargs:
                    value = kwargs[key]
                else:
                    value = getattr(self.__class__, key, None)
                setattr(self, key, value)

    fake_module.BaseSettings = BaseSettings
    sys.modules["pydantic_settings"] = fake_module

from app.services import macro_service
from etl.fetchers import akshare_macro_client


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return FakeQuery(self.rows)


class AkshareMacroIntegrationTests(unittest.TestCase):
    def test_filter_rows_with_latest_fallback_keeps_latest_stale_key(self) -> None:
        rows = [
            {"key": "AK_CHN_GDP_YOY:CHN", "date": date(2024, 12, 1), "value": 5.0},
            {"key": "AK_USA_CPI_YOY_ACTUAL:USA", "date": date(2026, 3, 1), "value": 2.4},
            {"key": "AK_USA_CPI_YOY_PREVIOUS:USA", "date": date(2026, 2, 1), "value": 2.5},
        ]

        filtered = akshare_macro_client._filter_rows_with_latest_fallback(
            rows,
            start=date(2026, 3, 17),
            end=date(2026, 3, 17),
        )

        self.assertEqual(
            [(row["key"], row["date"]) for row in filtered],
            [
                ("AK_CHN_GDP_YOY:CHN", date(2024, 12, 1)),
                ("AK_USA_CPI_YOY_ACTUAL:USA", date(2026, 3, 1)),
                ("AK_USA_CPI_YOY_PREVIOUS:USA", date(2026, 2, 1)),
            ],
        )

    def test_fetch_akshare_rows_for_report_spec_flattens_actual_forecast_previous(self) -> None:
        spec = akshare_macro_client.AkShareMacroSpec("demo", "AK_USA_CPI_YOY", "USA", "report")
        frame = pd.DataFrame(
            [
                ["2024-01-01", 3.1, 3.0, 3.2],
                ["2024-02-01", 3.2, 3.1, 3.1],
            ],
            columns=["date", "actual", "forecast", "previous"],
        )
        with patch.object(akshare_macro_client, "_call_akshare_function", return_value=frame):
            rows = akshare_macro_client.fetch_akshare_rows_for_spec(spec)

        keys = {row["key"] for row in rows}
        self.assertIn("AK_USA_CPI_YOY_ACTUAL:USA", keys)
        self.assertIn("AK_USA_CPI_YOY_FORECAST:USA", keys)
        self.assertIn("AK_USA_CPI_YOY_PREVIOUS:USA", keys)

    def test_fetch_akshare_rows_for_spec_keeps_latest_row_when_no_data_in_range(self) -> None:
        spec = akshare_macro_client.AkShareMacroSpec("demo", "AK_CHN_GDP_YOY", "CHN", "china_base")
        frame = pd.DataFrame(
            [
                ["2024-12-01", 5.0],
                ["2023-12-01", 4.8],
            ],
            columns=["date", "value"],
        )

        with patch.object(akshare_macro_client, "_call_akshare_function", return_value=frame):
            rows = akshare_macro_client.fetch_akshare_rows_for_spec(
                spec,
                start=date(2026, 3, 17),
                end=date(2026, 3, 17),
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"], "AK_CHN_GDP_YOY:CHN")
        self.assertEqual(rows[0]["date"], date(2024, 12, 1))

    def test_fetch_akshare_rows_for_cnbs_wide_spec_flattens_all_columns(self) -> None:
        spec = next(item for item in akshare_macro_client.AKSHARE_MACRO_SPECS if item.function_name == "macro_cnbs")
        frame = pd.DataFrame(
            [
                ["2024-01", 61.0, 160.0, 70.0, 25.0, 45.0, 231.0, 80.0, 81.0],
            ],
            columns=["period", "a", "b", "c", "d", "e", "f", "g", "h"],
        )
        with patch.object(akshare_macro_client, "_call_akshare_function", return_value=frame):
            rows = akshare_macro_client.fetch_akshare_rows_for_spec(spec)

        keys = {row["key"] for row in rows}
        self.assertIn("AK_CNBS_HOUSEHOLD:CHN", keys)
        self.assertIn("AK_CNBS_FIN_LIABILITY:CHN", keys)

    def test_fetch_akshare_rows_for_report_labeled_spec_uses_second_column_as_date(self) -> None:
        spec = akshare_macro_client.AkShareMacroSpec("demo", "AK_USA_FED_RATE", "USA", "report_labeled")
        frame = pd.DataFrame(
            [
                ["美联储利率决议报告", "2024-01-01", 5.5, 5.5, 5.25],
            ],
            columns=["item", "date", "actual", "forecast", "previous"],
        )
        with patch.object(akshare_macro_client, "_call_akshare_function", return_value=frame):
            rows = akshare_macro_client.fetch_akshare_rows_for_spec(spec)

        keys = {row["key"] for row in rows}
        self.assertIn("AK_USA_FED_RATE_ACTUAL:USA", keys)
        self.assertIn("AK_USA_FED_RATE_FORECAST:USA", keys)
        self.assertIn("AK_USA_FED_RATE_PREVIOUS:USA", keys)

    def test_fetch_akshare_rows_for_house_price_spec_splits_city_keys(self) -> None:
        spec = akshare_macro_client.AkShareMacroSpec(
            "demo",
            "AK_CHN_NEW_HOUSE_PRICE",
            "CHN",
            "house_price",
            field_aliases=("NEW_YOY", "NEW_MOM", "NEW_BASE", "SECOND_YOY", "SECOND_MOM", "SECOND_BASE"),
            group_aliases=("BJ", "SH"),
        )
        frame = pd.DataFrame(
            [
                ["2024-01-01", "北京", 1.0, 0.1, 100.0, 0.8, 0.0, 99.0],
                ["2024-01-01", "上海", 0.9, 0.2, 101.0, 0.7, -0.1, 98.0],
            ],
            columns=["date", "city", "a", "b", "c", "d", "e", "f"],
        )
        with patch.object(akshare_macro_client, "_call_akshare_function", return_value=frame):
            rows = akshare_macro_client.fetch_akshare_rows_for_spec(spec)

        keys = {row["key"] for row in rows}
        self.assertIn("AK_CHN_NEW_HOUSE_PRICE_BJ_NEW_YOY:CHN", keys)
        self.assertIn("AK_CHN_NEW_HOUSE_PRICE_SH_SECOND_BASE:CHN", keys)

    def test_to_date_parses_china_quarter_and_month_range(self) -> None:
        self.assertEqual(akshare_macro_client._to_date("2024年第2季度"), date(2024, 4, 1))
        self.assertEqual(akshare_macro_client._to_date("2024年1-2月份"), date(2024, 2, 1))

    def test_call_akshare_function_uses_shrzgm_fallback_on_exception(self) -> None:
        spec = akshare_macro_client.AkShareMacroSpec("macro_china_shrzgm", "AK_CHN_SOCIAL_FINANCING", "CHN", "wide")
        fake_df = pd.DataFrame([["2024-01", 1.0]], columns=["date", "value"])

        class DummyAk:
            @staticmethod
            def macro_china_shrzgm():
                raise RuntimeError("ssl error")

        with (
            patch.object(akshare_macro_client, "ak", DummyAk()),
            patch.object(akshare_macro_client, "_fetch_macro_china_shrzgm_fallback", return_value=fake_df) as fallback_mock,
        ):
            out = akshare_macro_client._call_akshare_function(spec)

        self.assertFalse(out.empty)
        fallback_mock.assert_called_once()

    def test_get_macro_series_refetches_akshare_key_when_db_empty(self) -> None:
        db = FakeSession([])
        fetched_rows = [
            {"key": "AK_CHN_CPI_YOY:CHN", "date": date(2024, 1, 1), "value": 0.2, "score": 0.3},
            {"key": "AK_CHN_CPI_YOY:CHN", "date": date(2024, 2, 1), "value": 0.4, "score": 0.6},
        ]

        with (
            patch.object(macro_service, "get_json", return_value=[]),
            patch.object(macro_service, "_fetch_world_bank_series_rows", return_value=[]),
            patch.object(macro_service, "fetch_akshare_series_rows", return_value=fetched_rows) as ak_mock,
            patch.object(macro_service, "_upsert_macro_rows") as upsert_mock,
            patch.object(macro_service, "set_json"),
        ):
            items = macro_service.get_macro_series(db, "AK_CHN_CPI_YOY:CHN")

        self.assertEqual([item.date for item in items], [date(2024, 1, 1), date(2024, 2, 1)])
        ak_mock.assert_called_once_with("AK_CHN_CPI_YOY:CHN", start=None, end=None)
        upsert_mock.assert_called_once_with(db, fetched_rows)


if __name__ == "__main__":
    unittest.main()
