from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any
from urllib.error import HTTPError as UrllibHTTPError
from urllib.request import Request, build_opener, ProxyHandler

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from etl.config.data_source_config import datasource_config
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


class HttpClientError(Exception):
    """统一 HTTP 错误"""
    pass


class HttpClient:
    """统一同步 HTTP 客户端。

    封装 requests / urllib，支持：
    - 统一 Headers、Timeout、Proxy
    - 指数退避重试
    - 自动 curl fallback（Windows 防火墙兼容）
    """

    def __init__(
        self,
        *,
        timeout: int | None = None,
        retry_count: int | None = None,
        retry_backoff: float | None = None,
        user_agent: str | None = None,
        default_headers: dict[str, str] | None = None,
        proxies: dict[str, str] | None = None,
        curl_fallback: bool = True,
    ) -> None:
        cfg = datasource_config
        self.timeout = timeout if timeout is not None else cfg.http_timeout_seconds
        self.retry_count = retry_count if retry_count is not None else cfg.http_retry_count
        self.retry_backoff = retry_backoff if retry_backoff is not None else cfg.http_retry_backoff_seconds
        self.user_agent = user_agent if user_agent is not None else cfg.http_user_agent
        self.default_headers = dict(default_headers) if default_headers else {}
        self.proxies = dict(proxies) if proxies else {}
        self.curl_fallback = curl_fallback
        self._curl_path: str | None = None

    # ---------- 内部工具 ----------
    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent}
        headers.update(self.default_headers)
        if extra:
            headers.update(extra)
        return headers

    def _proxy_dict(self) -> dict[str, str]:
        return dict(self.proxies)

    def _sleep_backoff(self, attempt: int) -> None:
        delay = self.retry_backoff * (2 ** attempt)
        time.sleep(delay)

    def _curl_exe(self) -> str | None:
        if self._curl_path is not None:
            return self._curl_path
        path = shutil.which("curl")
        self._curl_path = path or ""
        return path

    def _curl_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        data: str | None,
        timeout: int,
    ) -> bytes:
        curl = self._curl_exe()
        if not curl:
            raise HttpClientError("curl not available for fallback")
        cmd = [curl, "-L", "-sS", "-m", str(timeout), "-X", method]
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
        if data:
            cmd += ["-d", data]
        cmd.append(url)
        LOGGER.debug("curl fallback: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=False)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="ignore")[:500]
            raise HttpClientError(f"curl failed: {err}")
        return result.stdout

    # ---------- requests 路径 ----------
    def _requests_request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | str | None = None,
        json_payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> bytes:
        if requests is None:
            raise HttpClientError("requests library not available")
        hdrs = self._headers(headers)
        to = timeout if timeout is not None else self.timeout
        proxies = self._proxy_dict()
        kwargs: dict[str, Any] = {
            "headers": hdrs,
            "timeout": to,
            "proxies": proxies if proxies else None,
        }
        if params:
            kwargs["params"] = params
        if json_payload is not None:
            kwargs["json"] = json_payload
        elif data is not None:
            if isinstance(data, dict):
                kwargs["data"] = data
            else:
                kwargs["data"] = data
                if "Content-Type" not in hdrs:
                    hdrs["Content-Type"] = "application/x-www-form-urlencoded"

        method = method.upper()
        if method == "GET":
            resp = requests.get(url, **kwargs)
        elif method == "POST":
            resp = requests.post(url, **kwargs)
        elif method == "PUT":
            resp = requests.put(url, **kwargs)
        elif method == "DELETE":
            resp = requests.delete(url, **kwargs)
        else:
            resp = requests.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.content

    # ---------- urllib 路径（fallback） ----------
    def _urllib_request(
        self,
        method: str,
        url: str,
        *,
        data: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> bytes:
        to = timeout if timeout is not None else self.timeout
        hdrs = self._headers(headers)
        req = Request(url, data=data.encode("utf-8") if data else None, headers=hdrs, method=method.upper())
        proxies = self._proxy_dict()
        if proxies:
            opener = build_opener(ProxyHandler(proxies))
            resp = opener.open(req, timeout=to)
        else:
            resp = opener.open(req, timeout=to) if 'opener' in locals() else build_opener().open(req, timeout=to)
        # 修正：不应重复 opener
        opener = build_opener(ProxyHandler(proxies)) if proxies else build_opener()
        resp = opener.open(req, timeout=to)
        return resp.read()

    # ---------- 统一请求 ----------
    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | str | None = None,
        json_payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> bytes:
        last_exc: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                if requests is not None:
                    return self._requests_request(
                        method, url, params=params, data=data, json_payload=json_payload, headers=headers, timeout=timeout
                    )
                else:
                    # 如果没有 requests，退回到 urllib（不支持 params/json 自动编码）
                    if params:
                        from urllib.parse import urlencode
                        sep = "&" if "?" in url else "?"
                        url = f"{url}{sep}{urlencode(params)}"
                    payload: str | None = None
                    if json_payload is not None:
                        payload = json.dumps(json_payload, ensure_ascii=False)
                        hdrs = dict(headers or {})
                        hdrs.setdefault("Content-Type", "application/json")
                        headers = hdrs
                    elif isinstance(data, dict):
                        from urllib.parse import urlencode
                        payload = urlencode(data)
                        hdrs = dict(headers or {})
                        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
                        headers = hdrs
                    elif isinstance(data, str):
                        payload = data
                    return self._urllib_request(method, url, data=payload, headers=headers, timeout=timeout)
            except (UrllibHTTPError, Exception) as exc:
                last_exc = exc
                is_last = attempt == self.retry_count
                if is_last and self.curl_fallback and method.upper() in {"GET", "POST"}:
                    try:
                        LOGGER.warning("HTTP request failed after %s retries, trying curl fallback: %s", attempt + 1, url)
                        payload: str | None = None
                        if json_payload is not None:
                            payload = json.dumps(json_payload, ensure_ascii=False)
                        elif isinstance(data, dict):
                            from urllib.parse import urlencode
                            payload = urlencode(data)
                        elif isinstance(data, str):
                            payload = data
                        return self._curl_request(
                            method.upper(), url, self._headers(headers), payload, timeout or self.timeout
                        )
                    except Exception as curl_exc:
                        last_exc = curl_exc
                        LOGGER.error("curl fallback also failed: %s", curl_exc)
                if not is_last:
                    LOGGER.warning("HTTP %s %s failed (attempt %s/%s): %s", method, url, attempt + 1, self.retry_count + 1, exc)
                    self._sleep_backoff(attempt)
                else:
                    LOGGER.error("HTTP %s %s failed after all retries: %s", method, url, exc)
        raise HttpClientError(f"{method} {url} failed after {self.retry_count + 1} attempts: {last_exc}") from last_exc

    # ---------- 便捷方法 ----------
    def get(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int | None = None) -> bytes:
        return self.request("GET", url, params=params, headers=headers, timeout=timeout)

    def post(self, url: str, *, data: dict[str, Any] | str | None = None, json_payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int | None = None) -> bytes:
        return self.request("POST", url, data=data, json_payload=json_payload, headers=headers, timeout=timeout)

    def get_json(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int | None = None) -> Any:
        raw = self.get(url, params=params, headers=headers, timeout=timeout)
        return json.loads(raw.decode("utf-8", errors="ignore"))

    def post_json(self, url: str, *, data: dict[str, Any] | str | None = None, json_payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: int | None = None) -> Any:
        raw = self.post(url, data=data, json_payload=json_payload, headers=headers, timeout=timeout)
        return json.loads(raw.decode("utf-8", errors="ignore"))
