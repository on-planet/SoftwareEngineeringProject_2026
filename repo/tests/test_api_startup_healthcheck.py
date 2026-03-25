from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from fastapi import APIRouter
from sqlalchemy.exc import SQLAlchemyError

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

from app.core import schema
from app.routers import RouterRegistration, get_router_registrations
from app.routers.health import get_liveness, get_readiness


class _ConnectionContext:
    def __init__(self) -> None:
        self.connection = MagicMock()

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class DatabaseHealthCheckTests(unittest.TestCase):
    def test_check_database_connection_executes_probe_query(self) -> None:
        context = _ConnectionContext()

        with patch.object(schema.engine, "connect", return_value=context) as connect_mock:
            schema.check_database_connection()

        connect_mock.assert_called_once_with()
        context.connection.execute.assert_called_once()
        statement = context.connection.execute.call_args.args[0]
        self.assertEqual(str(statement), "SELECT 1")

    def test_check_database_connection_raises_runtime_error_with_migration_hint(self) -> None:
        with patch.object(schema.engine, "connect", side_effect=SQLAlchemyError("db down")):
            with self.assertRaises(RuntimeError) as exc_info:
                schema.check_database_connection()

        self.assertIn("db/migrations", str(exc_info.exception))

    def test_probe_database_connection_returns_failure_hint_without_raising(self) -> None:
        with patch.object(schema.engine, "connect", side_effect=SQLAlchemyError("db down")):
            ok, detail = schema.probe_database_connection()

        self.assertFalse(ok)
        self.assertIsInstance(detail, str)
        self.assertIn("db/migrations", detail or "")


class HealthRouteTests(unittest.TestCase):
    def test_liveness_route_returns_ok_payload(self) -> None:
        self.assertEqual(get_liveness(), {"status": "ok"})

    def test_readiness_route_returns_503_when_probe_fails(self) -> None:
        with patch("app.routers.health.probe_database_connection", return_value=(False, "db unavailable")):
            response = get_readiness()

        self.assertEqual(response.status_code, 503)
        self.assertIn(b'"status":"degraded"', response.body)
        self.assertIn(b'"database":"error"', response.body)

    def test_readiness_route_returns_200_when_probe_succeeds(self) -> None:
        with patch("app.routers.health.probe_database_connection", return_value=(True, None)):
            response = get_readiness()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"status":"ok"', response.body)
        self.assertIn(b'"database":"ok"', response.body)


class RouterRegistryTests(unittest.TestCase):
    def test_registry_discovers_health_and_api_routers(self) -> None:
        registrations = get_router_registrations()
        prefixes = {item.module: item.prefix for item in registrations}

        self.assertEqual(prefixes["health"], "")
        self.assertEqual(prefixes["stock"], "/api")
        self.assertIn("auth", prefixes)


class AppStartupTests(unittest.TestCase):
    def test_lifespan_does_not_probe_database_on_startup(self) -> None:
        sys.modules.pop("app.main", None)
        main = importlib.import_module("app.main")

        with patch("app.core.schema.check_database_connection") as check_mock:
            asyncio.run(_enter_and_exit_lifespan(main))

        check_mock.assert_not_called()
        sys.modules.pop("app.main", None)

    def test_create_app_registers_routes_from_registry(self) -> None:
        sys.modules.pop("app.main", None)
        main = importlib.import_module("app.main")

        api_router = APIRouter()
        health_router = APIRouter()

        @api_router.get("/example")
        def example_route():
            return {"status": "ok"}

        @health_router.get("/health/mock")
        def mock_health_route():
            return {"status": "ok"}

        with patch.object(
            main,
            "get_router_registrations",
            return_value=(
                RouterRegistration(module="example", router=api_router, prefix="/api"),
                RouterRegistration(module="health", router=health_router, prefix=""),
            ),
        ):
            app = main.create_app()

        paths = {route.path for route in app.routes}
        self.assertIn("/api/example", paths)
        self.assertIn("/health/mock", paths)
        sys.modules.pop("app.main", None)


async def _enter_and_exit_lifespan(main_module) -> None:
    async with main_module.lifespan(main_module.app):
        return


if __name__ == "__main__":
    unittest.main()
