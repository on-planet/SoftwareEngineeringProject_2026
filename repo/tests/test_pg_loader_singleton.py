from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

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

from etl.loaders import pg_loader


class PgLoaderSingletonTests(unittest.TestCase):
    def setUp(self) -> None:
        pg_loader._reset_loader_cache()

    def tearDown(self) -> None:
        pg_loader._reset_loader_cache()

    def test_get_loader_reuses_singleton_instance(self) -> None:
        class _FakeEngine:
            def dispose(self) -> None:
                return None

        fake_engine = _FakeEngine()

        class _FakeConfig:
            postgres_url = "postgresql://example"
            postgres_pool_size = 3
            postgres_max_overflow = 2

        with (
            patch.object(pg_loader, "load_config", return_value=_FakeConfig()) as load_config_mock,
            patch.object(pg_loader, "create_engine", return_value=fake_engine) as create_engine_mock,
        ):
            loader_one = pg_loader._get_loader()
            loader_two = pg_loader._get_loader()

        self.assertIs(loader_one, loader_two)
        self.assertIs(loader_one.engine, fake_engine)
        load_config_mock.assert_called_once()
        create_engine_mock.assert_called_once_with(
            "postgresql://example",
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
        )


if __name__ == "__main__":
    unittest.main()
