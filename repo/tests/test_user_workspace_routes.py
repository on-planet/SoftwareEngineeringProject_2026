from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

if "pydantic_settings" not in sys.modules:
    fake_module = types.ModuleType("pydantic_settings")

    class BaseSettings:
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

from app.routers.user_workspace import get_my_workspace


class UserWorkspaceRouteTests(unittest.TestCase):
    def test_get_my_workspace_combines_pools_and_filters(self) -> None:
        current_user = types.SimpleNamespace(id=9)

        with patch(
            "app.routers.user_workspace.list_stock_pools",
            return_value=[{"id": 1, "name": "成长池", "market": "A", "symbols": ["300750.SZ"], "note": ""}],
        ) as list_pools, patch(
            "app.routers.user_workspace.list_saved_stock_filters",
            return_value=[{"id": 11, "name": "新能源", "market": "A", "keyword": "", "sector": "新能源", "sort": "asc"}],
        ) as list_filters:
            result = get_my_workspace(db=MagicMock(), current_user=current_user)

        self.assertEqual(result["pools"][0]["name"], "成长池")
        self.assertEqual(result["filters"][0]["name"], "新能源")
        list_pools.assert_called_once_with(unittest.mock.ANY, 9)
        list_filters.assert_called_once_with(unittest.mock.ANY, 9)


if __name__ == "__main__":
    unittest.main()
