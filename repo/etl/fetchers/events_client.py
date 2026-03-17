from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

from etl.fetchers.snowball_client import normalize_symbol, to_snowball_symbol
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required
from etl.utils.stock_basics_cache import list_cached_symbols

LOGGER = get_logger(__name__)
CACHE_DIR = Path(__file__).resolve().parents[1] / "state" / "rss_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = int(os.getenv("RSS_CACHE_TTL", "1800"))
CACHE_STALE_ON_ERROR_SECONDS = int(os.getenv("RSS_CACHE_STALE_ON_ERROR_SECONDS", str(48 * 3600)))
RSS_TIMEOUT_SECONDS = int(os.getenv("RSS_TIMEOUT_SECONDS", "12"))
RSS_MAX_WORKERS = int(os.getenv("RSS_MAX_WORKERS", "8"))
RSS_RETRY_COUNT = int(os.getenv("RSS_RETRY_COUNT", "2"))
RSS_RETRY_BACKOFF_SECONDS = float(os.getenv("RSS_RETRY_BACKOFF_SECONDS", "1.5"))
RSS_USER_AGENT = os.getenv(
    "RSS_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
RSS_PROXY = os.getenv("RSS_PROXY", "").strip()
RSS_HTTP_PROXY = os.getenv("RSS_HTTP_PROXY", "").strip()
RSS_HTTPS_PROXY = os.getenv("RSS_HTTPS_PROXY", "").strip()
RSS_NO_PROXY = {
    item.strip().lower()
    for item in os.getenv("RSS_NO_PROXY", "").split(",")
    if item.strip()
}
RSS_DISABLE_ENV_PROXY = os.getenv("RSS_DISABLE_ENV_PROXY", "0").strip().lower() in {"1", "true", "yes", "on"}
EVENTS_SYMBOL_WORKERS = max(1, int(os.getenv("EVENTS_SYMBOL_WORKERS", "8")))

try:
    import pysnowball as ball  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ball = None
    LOGGER.warning("pysnowball import failed: %s", exc)

try:
    import akshare as ak  # type: ignore
except Exception as exc:  # pragma: no cover - runtime env dependent
    ak = None
    LOGGER.warning("akshare import failed in events client: %s", exc)

AKSHARE_A_DYNAMIC_FUNCTION_NAME = "stock_zh_a_new"
AKSHARE_A_DYNAMIC_FUNCTION_NAMES = ("stock_zh_a_new_em", "stock_zh_a_new")
A_DYNAMIC_CODE_COLUMNS = (
    "code",
    "symbol",
    "stock_code",
    "security_code",
    "代码",
    "证券代码",
    "股票代码",
)
A_DYNAMIC_NAME_COLUMNS = (
    "name",
    "stock_name",
    "security_name",
    "名称",
    "股票简称",
    "简称",
    "证券简称",
)
A_DYNAMIC_TITLE_COLUMNS = ("title", "event", "news", "summary", "标题", "事件", "动态", "公告")
A_DYNAMIC_DETAIL_COLUMNS = (
    "detail",
    "content",
    "description",
    "board",
    "industry",
    "细分行业",
    "板块",
    "行业",
)
A_DYNAMIC_DATE_COLUMNS = (
    "date",
    "publish_date",
    "trade_date",
    "update_date",
    "list_date",
    "time",
    "日期",
    "发布时间",
    "上市日期",
    "更新时间",
)
A_DYNAMIC_LINK_COLUMNS = ("link", "url", "article_url", "news_url", "公告链接", "链接")
A_DYNAMIC_OPEN_COLUMNS = ("open", "开盘", "今开")
A_DYNAMIC_HIGH_COLUMNS = ("high", "最高")
A_DYNAMIC_LOW_COLUMNS = ("low", "最低")
A_DYNAMIC_VOLUME_COLUMNS = ("volume", "成交量")
A_DYNAMIC_AMOUNT_COLUMNS = ("amount", "成交额")
AKSHARE_A_DYNAMIC_SINA_COUNT_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount"
)
AKSHARE_A_DYNAMIC_SINA_DATA_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
)
AKSHARE_A_DYNAMIC_EM_URL = "https://40.push2.eastmoney.com/api/qt/clist/get"
AKSHARE_A_DYNAMIC_PAGE_SIZE = max(1, int(os.getenv("AKSHARE_A_DYNAMIC_PAGE_SIZE", "80")))
AKSHARE_A_DYNAMIC_MAX_PAGES = max(1, int(os.getenv("AKSHARE_A_DYNAMIC_MAX_PAGES", "25")))
AKSHARE_A_DYNAMIC_CURL_TIMEOUT_SECONDS = max(
    5, int(os.getenv("AKSHARE_A_DYNAMIC_CURL_TIMEOUT_SECONDS", "18"))
)
AKSHARE_A_DYNAMIC_CURL_FALLBACK_ENABLED = (
    os.getenv("AKSHARE_A_DYNAMIC_CURL_FALLBACK_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        number = float(text)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _is_windows_socket_block_error(exc: Exception) -> bool:
    text = str(exc or "")
    return "WinError 10013" in text or "access permissions" in text.lower() or "访问权限不允许" in text


def _decode_http_payload(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk", "latin1"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        try:
            number = int(value)
            if number > 10_000_000_000:
                return datetime.fromtimestamp(number / 1000, tz=timezone.utc).date()
            if number > 1_000_000_000:
                return datetime.fromtimestamp(number, tz=timezone.utc).date()
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return None


def _pick(record: dict, keys: Iterable[str]):
    for key in keys:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    return None


def _pick_ci(record: dict, keys: Iterable[str]):
    lowered: dict[str, object] = {}
    for key, value in record.items():
        normalized = str(key).strip().lower()
        if normalized and normalized not in lowered:
            lowered[normalized] = value
    for key in keys:
        value = lowered.get(str(key).strip().lower())
        if value is None:
            continue
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            continue
        return value
    return None


def _clean_text(value: object, *, max_length: int) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return compact[:max_length].strip()


def _normalize_a_symbol(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    normalized = normalize_symbol(text)
    if normalized.endswith((".SH", ".SZ", ".BJ")) and len(normalized.split(".")[0]) == 6:
        return normalized
    digits = re.sub(r"\D", "", text)
    if len(digits) != 6:
        return None
    if digits.startswith(("4", "8")):
        return f"{digits}.BJ"
    if digits.startswith(("5", "6", "9")):
        return f"{digits}.SH"
    return f"{digits}.SZ"


def _as_record_rows(payload) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict(orient="records")
        except TypeError:
            try:
                records = to_dict("records")
            except Exception:
                return []
        except Exception:
            return []
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    return []


def _extract_dict_rows(payload) -> list[dict]:
    rows: list[dict] = []
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            rows.append(node)
            stack.extend(node.values())
            continue
        if isinstance(node, list):
            stack.extend(node)
    return [row for row in rows if row]


def _event_symbols() -> list[str]:
    raw = os.getenv("SNOWBALL_EVENT_SYMBOLS", "").strip() or os.getenv("SNOWBALL_STOCK_SYMBOLS", "").strip()
    output: list[str] = []
    seen: set[str] = set()
    if raw:
        for item in raw.split(","):
            symbol = normalize_symbol(item.strip())
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            output.append(symbol)
        return output

    for symbol in ("600000.SH", "000001.SZ", "600519.SH"):
        if symbol in seen:
            continue
        seen.add(symbol)
        output.append(symbol)

    cached_limit = max(1, int(os.getenv("SNOWBALL_HK_EVENT_LIMIT", "200")))
    cached_hk_symbols = list_cached_symbols(markets=("HK",), limit=cached_limit) or ["00700.HK", "00005.HK", "00941.HK"]
    for symbol in cached_hk_symbols:
        if symbol in seen:
            continue
        seen.add(symbol)
        output.append(symbol)
    return output

def _hkex_regulatory_announcements_rss() -> str:
    override = os.getenv("HKEX_REGULATORY_ANNOUNCEMENTS_RSS", "").strip()
    if override:
        return override
    return "https://www.hkex.com.hk/Services/RSS-Feeds/regulatory-announcements?sc_lang=zh-HK"


def _normalize_hk_code(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text.isdigit():
        return None
    digits = text.zfill(5)
    return f"{digits}.HK"


def _symbol_from_hkex_title(title: str, link: str = "") -> str | None:
    text = str(title or "").strip()
    if not text:
        return None
    patterns = [
        r"(?<!\d)(\d{5})\s*\.?\s*HK\b",
        r"(?:股份代號|股票代號|股份编号|证券代码|Stock Code|Stock code|stock code)[:：\s#-]*([0-9]{1,5})",
        r"^\(?([0-9]{5})\)?(?:\s|[:：-])",
        r"\(([0-9]{5})\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        symbol = _normalize_hk_code(match.group(1))
        if symbol:
            return symbol

    link_text = str(link or "")
    link_match = re.search(r"(?<!\d)(\d{5})(?!\d)", link_text)
    if link_match:
        return _normalize_hk_code(link_match.group(1))
    return None


def _dedupe_event_rows(rows: List[dict]) -> List[dict]:
    seen: set[tuple[str, str, str, str]] = set()
    output: list[dict] = []
    for row in rows:
        key = (
            str(row.get("symbol") or ""),
            str(row.get("type") or ""),
            str(row.get("title") or ""),
            str(row.get("link") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _get_hkex_regulatory_announcements(as_of: date) -> list[dict]:
    rows: list[dict] = []
    url = _hkex_regulatory_announcements_rss()
    items = _fetch_rss(url)
    for item in items:
        published_at = item.get("published_at")
        if not published_at or published_at.date() != as_of:
            continue
        title = str(item.get("title") or "").strip()
        link = str(item.get("link") or "").strip()
        symbol = _symbol_from_hkex_title(title, link)
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "type": "announcement",
                "title": title,
                "date": as_of,
                "link": link,
                "source": "HKEX Regulatory Announcement",
            }
        )
    return rows


def _is_buyback_title(title: str) -> bool:
    keywords = ("回购", "回購", "股份回购", "股份回購", "buyback", "repurchase")
    lower = title.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def _parse_pub_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _build_proxy_map() -> dict[str, str]:
    if RSS_PROXY:
        return {"http": RSS_PROXY, "https": RSS_PROXY}
    proxies: dict[str, str] = {}
    if RSS_HTTP_PROXY:
        proxies["http"] = RSS_HTTP_PROXY
    if RSS_HTTPS_PROXY:
        proxies["https"] = RSS_HTTPS_PROXY
    return proxies


def _should_bypass_proxy(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    return any(host == item or host.endswith(f".{item}") for item in RSS_NO_PROXY)


def _build_request(url: str) -> Request:
    return Request(
        url,
        headers={
            "User-Agent": RSS_USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )


def _open_url(url: str):
    request = _build_request(url)
    if _should_bypass_proxy(url):
        return build_opener(ProxyHandler({})).open(request, timeout=RSS_TIMEOUT_SECONDS)
    proxies = _build_proxy_map()
    if proxies:
        return build_opener(ProxyHandler(proxies)).open(request, timeout=RSS_TIMEOUT_SECONDS)
    if RSS_DISABLE_ENV_PROXY:
        return build_opener(ProxyHandler({})).open(request, timeout=RSS_TIMEOUT_SECONDS)
    return urlopen(request, timeout=RSS_TIMEOUT_SECONDS)


def _should_retry_http(exc: HTTPError) -> bool:
    return exc.code == 429 or 500 <= exc.code < 600


def _sleep_before_retry(attempt: int) -> None:
    delay = RSS_RETRY_BACKOFF_SECONDS * (2 ** max(0, attempt - 1))
    time.sleep(delay)


def _cache_key(url: str) -> str:
    safe = url.replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_")
    return f"{safe}.json"


def _load_cache(url: str, *, allow_stale: bool = False) -> List[dict] | None:
    path = CACHE_DIR / _cache_key(url)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    ts = payload.get("ts")
    items = payload.get("items")
    if not isinstance(ts, (int, float)) or not isinstance(items, list):
        return None
    age = time.time() - ts
    max_age = CACHE_STALE_ON_ERROR_SECONDS if allow_stale else CACHE_TTL_SECONDS
    if age > max_age:
        return None
    output = []
    for item in items:
        published_at = item.get("published_at")
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at)
            except Exception:
                published_at = None
        output.append(
            {
                "title": item.get("title") or "",
                "link": item.get("link") or "",
                "published_at": published_at,
            }
        )
    return output


def _save_cache(url: str, items: List[dict]) -> None:
    path = CACHE_DIR / _cache_key(url)
    payload = {
        "ts": time.time(),
        "items": [
            {
                "title": item.get("title") or "",
                "link": item.get("link") or "",
                "published_at": item.get("published_at").isoformat() if item.get("published_at") else None,
            }
            for item in items
        ],
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        LOGGER.warning("write rss cache failed [%s]: %s", url, exc)


def _download_rss(url: str) -> bytes | None:
    data = None
    for attempt in range(RSS_RETRY_COUNT + 1):
        try:
            with _open_url(url) as resp:
                data = resp.read()
                break
        except HTTPError as exc:
            LOGGER.warning("fetch rss failed [%s]: %s", url, exc)
            if attempt >= RSS_RETRY_COUNT or not _should_retry_http(exc):
                return None
        except (URLError, TimeoutError) as exc:
            LOGGER.warning("fetch rss failed [%s]: %s", url, exc)
            if attempt >= RSS_RETRY_COUNT:
                return None
        except Exception as exc:
            LOGGER.warning("fetch rss failed [%s]: %s", url, exc)
            return None
        _sleep_before_retry(attempt + 1)
    return data


def _fetch_rss(url: str) -> List[dict]:
    cached = _load_cache(url)
    if cached is not None:
        return cached
    data = _download_rss(url)
    if data is None:
        return _load_cache(url, allow_stale=True) or []

    try:
        root = ET.fromstring(data)
    except Exception as exc:
        LOGGER.warning("parse rss failed [%s]: %s", url, exc)
        return []

    items: list[dict] = []
    for item in root.findall(".//item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published_at": _parse_pub_date(item.findtext("pubDate") or ""),
            }
        )
    _save_cache(url, items)
    return items


def _fetch_rss_batch(urls: list[str]) -> dict[str, List[dict]]:
    results: dict[str, List[dict]] = {}
    url_list = [url for url in urls if url]
    if not url_list:
        return results
    workers = max(1, min(RSS_MAX_WORKERS, len(url_list)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(_fetch_rss, url): url for url in url_list}
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = future.result()
            except Exception as exc:
                LOGGER.warning("fetch rss batch failed [%s]: %s", url, exc)
                results[url] = []
    return results


def _fetch_symbol_report_rows(symbol: str, as_of: date) -> list[dict]:
    if ball is None:
        return []
    snow_symbol = to_snowball_symbol(symbol)
    try:
        payload = ball.report(snow_symbol)
    except Exception as exc:
        LOGGER.warning("snowball report failed [%s]: %s", snow_symbol, exc)
        return []

    rows: list[dict] = []
    for record in _extract_dict_rows(payload):
        row_date = _to_date(
            _pick(
                record,
                (
                    "publish_date",
                    "pub_date",
                    "report_date",
                    "date",
                    "ctime",
                    "timestamp",
                ),
            )
        )
        if row_date != as_of:
            continue
        title = _pick(record, ("title", "name", "report_name", "notice_title"))
        if title in (None, ""):
            continue
        rows.append(
            {
                "symbol": symbol,
                "type": "report",
                "title": str(title),
                "date": row_date,
                "link": str(_pick(record, ("url", "link", "pdf_url", "article_url")) or ""),
                "source": "Snowball Report",
            }
        )
    return rows


def _fetch_symbol_insider_rows(symbol: str, as_of: date) -> list[dict]:
    if ball is None:
        return []
    snow_symbol = to_snowball_symbol(symbol)
    try:
        payload = ball.skholderchg(snow_symbol)
    except Exception as exc:
        LOGGER.warning("snowball skholderchg failed [%s]: %s", snow_symbol, exc)
        return []

    rows: list[dict] = []
    for record in _extract_dict_rows(payload):
        row_date = _to_date(_pick(record, ("change_date", "date", "publish_date", "ctime", "timestamp")))
        if row_date != as_of:
            continue
        shares = _safe_float(_pick(record, ("change_amount", "shares", "volume", "chg_num"))) or 0.0
        trade_type = _pick(record, ("change_type", "direction", "type", "change_reason")) or "trade"
        rows.append(
            {
                "symbol": symbol,
                "date": row_date,
                "type": str(trade_type),
                "shares": shares,
                "link": str(_pick(record, ("url", "link")) or ""),
                "source": "Snowball F10",
            }
        )
    return rows


def _fetch_akshare_company_dynamic_events(as_of: date) -> list[dict]:
    if as_of != date.today():
        return []

    def _fetch_stock_zh_a_new_em_records_via_curl() -> list[dict]:
        if not AKSHARE_A_DYNAMIC_CURL_FALLBACK_ENABLED:
            return []
        curl_path = shutil.which("curl.exe") or shutil.which("curl")
        if not curl_path:
            return []

        command = [
            curl_path,
            "-L",
            "-sS",
            AKSHARE_A_DYNAMIC_EM_URL,
            "--get",
            "--data-urlencode",
            "pn=1",
            "--data-urlencode",
            f"pz={AKSHARE_A_DYNAMIC_PAGE_SIZE}",
            "--data-urlencode",
            "po=1",
            "--data-urlencode",
            "np=1",
            "--data-urlencode",
            "ut=bd1d9ddb04089700cf9c27f6f7426281",
            "--data-urlencode",
            "fltt=2",
            "--data-urlencode",
            "invt=2",
            "--data-urlencode",
            "fid=f26",
            "--data-urlencode",
            "fs=m:0 f:8,m:1 f:8",
            "--data-urlencode",
            "fields=f12,f14,f17,f15,f16,f5,f6",
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=AKSHARE_A_DYNAMIC_CURL_TIMEOUT_SECONDS,
                check=False,
            )
        except Exception as exc:
            LOGGER.warning("curl akshare em event fetch failed: %s", exc)
            return []
        if result.returncode != 0 or not result.stdout:
            return []
        text = _decode_http_payload(result.stdout).strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
        except Exception:
            return []
        data = payload.get("data") if isinstance(payload, dict) else None
        diff = data.get("diff") if isinstance(data, dict) else None
        if not isinstance(diff, list):
            return []
        records: list[dict] = []
        for item in diff:
            if not isinstance(item, dict):
                continue
            records.append(
                {
                    "code": item.get("f12"),
                    "name": item.get("f14"),
                    "open": item.get("f17"),
                    "high": item.get("f15"),
                    "low": item.get("f16"),
                    "volume": item.get("f5"),
                    "amount": item.get("f6"),
                }
            )
        return records

    def _fetch_stock_zh_a_new_records_via_curl() -> list[dict]:
        em_records = _fetch_stock_zh_a_new_em_records_via_curl()
        if em_records:
            return em_records
        if not AKSHARE_A_DYNAMIC_CURL_FALLBACK_ENABLED:
            return []
        curl_path = shutil.which("curl.exe") or shutil.which("curl")
        if not curl_path:
            return []

        count_cmd = [
            curl_path,
            "-L",
            "-sS",
            AKSHARE_A_DYNAMIC_SINA_COUNT_URL,
            "--get",
            "--data-urlencode",
            "node=new_stock",
        ]
        try:
            count_result = subprocess.run(
                count_cmd,
                capture_output=True,
                timeout=AKSHARE_A_DYNAMIC_CURL_TIMEOUT_SECONDS,
                check=False,
            )
        except Exception as exc:
            LOGGER.warning("curl akshare event count failed: %s", exc)
            return []
        if count_result.returncode != 0:
            return []
        count_text = _decode_http_payload(count_result.stdout).strip()
        match = re.search(r"\d+", count_text)
        if not match:
            return []
        total = int(match.group(0))
        total_pages = (total + AKSHARE_A_DYNAMIC_PAGE_SIZE - 1) // AKSHARE_A_DYNAMIC_PAGE_SIZE
        total_pages = max(1, min(total_pages, AKSHARE_A_DYNAMIC_MAX_PAGES))

        records: list[dict] = []
        for page in range(1, total_pages + 1):
            data_cmd = [
                curl_path,
                "-L",
                "-sS",
                AKSHARE_A_DYNAMIC_SINA_DATA_URL,
                "--get",
                "--data-urlencode",
                f"page={page}",
                "--data-urlencode",
                f"num={AKSHARE_A_DYNAMIC_PAGE_SIZE}",
                "--data-urlencode",
                "sort=symbol",
                "--data-urlencode",
                "asc=1",
                "--data-urlencode",
                "node=new_stock",
                "--data-urlencode",
                "symbol=",
                "--data-urlencode",
                "_s_r_a=page",
            ]
            try:
                data_result = subprocess.run(
                    data_cmd,
                    capture_output=True,
                    timeout=AKSHARE_A_DYNAMIC_CURL_TIMEOUT_SECONDS,
                    check=False,
                )
            except Exception:
                continue
            if data_result.returncode != 0 or not data_result.stdout:
                continue
            text = _decode_http_payload(data_result.stdout).strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if isinstance(payload, list):
                records.extend(item for item in payload if isinstance(item, dict))
        return records

    payload_rows: list[dict]
    if ak is None:
        payload_rows = _fetch_stock_zh_a_new_records_via_curl()
    else:
        func = None
        func_name = AKSHARE_A_DYNAMIC_FUNCTION_NAME
        for candidate in AKSHARE_A_DYNAMIC_FUNCTION_NAMES:
            possible = getattr(ak, candidate, None)
            if callable(possible):
                func = possible
                func_name = candidate
                break
        if func is None:
            LOGGER.warning("akshare function missing: %s", AKSHARE_A_DYNAMIC_FUNCTION_NAME)
            payload_rows = []
        else:
            try:
                payload_rows = _as_record_rows(func())
            except Exception as exc:
                if _is_windows_socket_block_error(exc):
                    LOGGER.info(
                        "akshare event python network blocked [%s], fallback to curl",
                        func_name,
                    )
                else:
                    LOGGER.warning("akshare event fetch failed [%s]: %s", func_name, exc)
                payload_rows = _fetch_stock_zh_a_new_records_via_curl()

    rows: list[dict] = []
    for record in payload_rows:
        symbol = _normalize_a_symbol(_pick_ci(record, A_DYNAMIC_CODE_COLUMNS))
        if not symbol:
            continue
        open_val = _safe_float(_pick_ci(record, A_DYNAMIC_OPEN_COLUMNS))
        high_val = _safe_float(_pick_ci(record, A_DYNAMIC_HIGH_COLUMNS))
        low_val = _safe_float(_pick_ci(record, A_DYNAMIC_LOW_COLUMNS))
        volume_val = _safe_float(_pick_ci(record, A_DYNAMIC_VOLUME_COLUMNS))
        amount_val = _safe_float(_pick_ci(record, A_DYNAMIC_AMOUNT_COLUMNS))
        row_date = _to_date(_pick_ci(record, A_DYNAMIC_DATE_COLUMNS))
        if row_date is None and any(value is not None for value in (open_val, high_val, low_val, volume_val, amount_val)):
            row_date = as_of
        if row_date != as_of:
            continue
        name = _clean_text(_pick_ci(record, A_DYNAMIC_NAME_COLUMNS), max_length=64)
        title = _clean_text(_pick_ci(record, A_DYNAMIC_TITLE_COLUMNS), max_length=180)
        detail = _clean_text(_pick_ci(record, A_DYNAMIC_DETAIL_COLUMNS), max_length=120)
        if not title:
            title = f"{name or symbol} company dynamic"
            metrics: list[str] = []
            if open_val is not None:
                metrics.append(f"open {open_val:g}")
            if high_val is not None:
                metrics.append(f"high {high_val:g}")
            if low_val is not None:
                metrics.append(f"low {low_val:g}")
            if metrics:
                title = _clean_text(f"{title} ({', '.join(metrics)})", max_length=240)
        if detail and detail not in title:
            title = _clean_text(f"{title} | {detail}", max_length=240)
        link = _clean_text(_pick_ci(record, A_DYNAMIC_LINK_COLUMNS), max_length=512)
        rows.append(
            {
                "symbol": symbol,
                "type": "company_dynamic",
                "title": title,
                "date": row_date,
                "link": link,
                "source": "AkShare stock_zh_a_new",
            }
        )
    return rows


def get_events(as_of: date) -> List[dict]:
    rows: list[dict] = []
    rows.extend(_get_hkex_regulatory_announcements(as_of))
    rows.extend(_fetch_akshare_company_dynamic_events(as_of))

    if ball is None:
        LOGGER.warning("pysnowball unavailable, skip snowball events")
        return ensure_required(_dedupe_event_rows(rows), ["symbol", "type", "title", "date"], "events.events")

    symbols = _event_symbols()
    workers = max(1, min(EVENTS_SYMBOL_WORKERS, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="event_reports") as executor:
        future_map = {executor.submit(_fetch_symbol_report_rows, symbol, as_of): symbol for symbol in symbols}
        for future in as_completed(future_map):
            symbol = future_map[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                LOGGER.warning("symbol report task failed [%s]: %s", symbol, exc)
    return ensure_required(_dedupe_event_rows(rows), ["symbol", "type", "title", "date"], "events.events")


def get_buyback(as_of: date) -> List[dict]:
    rows: list[dict] = []
    items = _fetch_rss(_hkex_regulatory_announcements_rss())
    for item in items:
        published_at = item.get("published_at")
        if not published_at or published_at.date() != as_of:
            continue
        title = str(item.get("title") or "")
        if not _is_buyback_title(title):
            continue
        symbol = _symbol_from_hkex_title(title, str(item.get("link") or ""))
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": as_of,
                "amount": 0.0,
                "link": item.get("link") or "",
                "source": "HKEX Regulatory Announcement",
            }
        )
    return ensure_required(rows, ["symbol", "date", "amount"], "events.buyback")


def get_insider_trade(as_of: date) -> List[dict]:
    if ball is None:
        LOGGER.warning("pysnowball unavailable, skip insider trades")
        return []

    rows: list[dict] = []
    symbols = _event_symbols()
    workers = max(1, min(EVENTS_SYMBOL_WORKERS, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="event_insider") as executor:
        future_map = {executor.submit(_fetch_symbol_insider_rows, symbol, as_of): symbol for symbol in symbols}
        for future in as_completed(future_map):
            symbol = future_map[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                LOGGER.warning("symbol insider task failed [%s]: %s", symbol, exc)
    return ensure_required(rows, ["symbol", "date", "type", "shares"], "events.insider")



