"""
In-memory cache for Vega-Lite rendered chart images.
Charts are stored by key when generated; served via /api/chart/{key}.
"""
from __future__ import annotations

import time
from typing import Any

# key -> (png_bytes, timestamp)
_chart_cache: dict[str, tuple[bytes, float]] = {}
_TTL_SECONDS = 3600  # 1 hour


def store_chart(key: str, png_data: bytes) -> None:
    """Store chart PNG in cache."""
    _chart_cache[key] = (png_data, time.time())


def get_chart(key: str) -> bytes | None:
    """Retrieve chart PNG from cache. Returns None if expired or not found."""
    if key not in _chart_cache:
        return None
    png_data, ts = _chart_cache[key]
    if time.time() - ts > _TTL_SECONDS:
        del _chart_cache[key]
        return None
    return png_data


def prune_expired() -> None:
    """Remove expired entries from cache."""
    now = time.time()
    expired = [k for k, (_, ts) in _chart_cache.items() if now - ts > _TTL_SECONDS]
    for k in expired:
        del _chart_cache[k]
