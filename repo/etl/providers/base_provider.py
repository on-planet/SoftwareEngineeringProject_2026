from __future__ import annotations

from typing import Any, Callable, TypeVar

from etl.utils.http_client import HttpClient
from etl.utils.logging import get_logger

T = TypeVar("T")


class BaseProvider:
    """Provider 基类，统一错误处理、降级与日志。"""

    def __init__(self) -> None:
        self.http = HttpClient()
        self.logger = get_logger(self.__class__.__module__ + "." + self.__class__.__name__)

    def _safe_call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
        """安全调用单个函数，失败返回 None 并记录日志。"""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            self.logger.warning("%s failed: %s", fn.__name__, exc)
            return None

    def _first_success(self, *calls: tuple[Callable[..., T], tuple[Any, ...], dict[str, Any]]) -> T | None:
        """依次尝试多个调用，返回第一个非 None 非空结果。"""
        for fn, args, kwargs in calls:
            result = self._safe_call(fn, *args, **kwargs)
            if result is not None:
                # 对列表/字典类型，空值也算失败
                if isinstance(result, (list, dict, str)) and not result:
                    continue
                return result
        return None

    def _all_results(self, *calls: tuple[Callable[..., T], tuple[Any, ...], dict[str, Any]]) -> list[T]:
        """依次执行多个调用，收集所有非 None 结果。"""
        results: list[T] = []
        for fn, args, kwargs in calls:
            result = self._safe_call(fn, *args, **kwargs)
            if result is not None:
                results.append(result)
        return results
