from __future__ import annotations

from typing import Any

from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


class ProviderRegistry:
    """Provider 注册表与工厂。

    支持按名称注册和获取 provider 实例，内部保持单例。
    """

    def __init__(self) -> None:
        self._providers: dict[str, Any] = {}

    def register(self, name: str, provider: Any) -> None:
        """注册一个 provider 实例。"""
        self._providers[name] = provider
        LOGGER.info("Provider registered: %s -> %s", name, type(provider).__name__)

    def get(self, name: str) -> Any:
        """按名称获取 provider 实例。"""
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not registered. Available: {list(self._providers.keys())}")
        return self._providers[name]

    def has(self, name: str) -> bool:
        return name in self._providers

    def names(self) -> list[str]:
        return list(self._providers.keys())

    def clear(self) -> None:
        self._providers.clear()


# 全局注册表实例
provider_registry = ProviderRegistry()
