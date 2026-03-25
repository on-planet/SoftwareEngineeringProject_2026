from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.core import cache


class _FakeRedisClient:
    def __init__(self, payload: bytes | None, ttl: int) -> None:
        self._payload = payload
        self._ttl = ttl

    def get(self, key: str):
        return self._payload

    def ttl(self, key: str) -> int:
        return self._ttl


class CacheTtlSyncTests(unittest.TestCase):
    def tearDown(self) -> None:
        cache._memory_cache.clear()

    def test_get_json_uses_redis_ttl_for_memory_backfill(self) -> None:
        fake_client = _FakeRedisClient(b'{"ok": true}', 12)

        with patch("app.core.cache.get_redis_client", return_value=fake_client):
            payload = cache.get_json("demo:key")

        self.assertEqual(payload, {"ok": True})
        expire_at, stored = cache._memory_cache["demo:key"]
        self.assertEqual(stored, {"ok": True})
        remaining = (expire_at - datetime.now()).total_seconds()
        self.assertGreater(remaining, 8)
        self.assertLessEqual(remaining, 12.5)

    def test_get_json_falls_back_to_default_ttl_when_redis_ttl_is_missing(self) -> None:
        fake_client = _FakeRedisClient(b'{"ok": true}', -1)

        with patch("app.core.cache.get_redis_client", return_value=fake_client):
            cache.get_json("demo:key")

        expire_at, _ = cache._memory_cache["demo:key"]
        remaining = (expire_at - datetime.now()).total_seconds()
        self.assertGreater(remaining, cache.DEFAULT_CACHE_TTL - 5)
        self.assertLessEqual(remaining, cache.DEFAULT_CACHE_TTL + 1)


if __name__ == "__main__":
    unittest.main()
