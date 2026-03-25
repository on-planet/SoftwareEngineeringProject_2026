from __future__ import annotations

from dataclasses import dataclass
import importlib
import pkgutil

from fastapi import APIRouter

DEFAULT_ROUTER_PREFIX = "/api"


@dataclass(frozen=True)
class RouterRegistration:
    module: str
    router: APIRouter
    prefix: str = DEFAULT_ROUTER_PREFIX


def _router_module_names() -> list[str]:
    names: list[str] = []
    for module_info in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        if module_info.ispkg or module_info.name.startswith("_"):
            continue
        names.append(module_info.name)
    names.sort()
    return names


def get_router_registrations() -> tuple[RouterRegistration, ...]:
    registrations: list[RouterRegistration] = []
    package_name = __name__

    for module_name in _router_module_names():
        module = importlib.import_module(f"{package_name}.{module_name}")
        router = getattr(module, "router", None)
        if router is None:
            continue
        if not isinstance(router, APIRouter):
            raise TypeError(f"Router module '{module_name}' must expose an APIRouter named 'router'")
        prefix = str(getattr(module, "ROUTER_PREFIX", DEFAULT_ROUTER_PREFIX) or "")
        registrations.append(RouterRegistration(module=module_name, router=router, prefix=prefix))

    return tuple(registrations)
