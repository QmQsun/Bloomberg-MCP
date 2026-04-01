"""TTL-based in-memory cache for Bloomberg data.

Caches Bloomberg API responses keyed on (request_type, securities, fields, overrides).
Different data types get different TTLs reflecting their update frequency.
"""

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CacheTTL(Enum):
    """TTL presets by data type (in seconds)."""
    REFERENCE_STATIC = 86400     # 24h (company name, sector, BICS)
    FINANCIAL_STMT = 604800      # 7 days (quarterly financials)
    ESTIMATES = 14400            # 4h (consensus updates intraday)
    PRICE = 30                   # 30 sec (near real-time)
    HISTORICAL = 43200           # 12h (EOD data doesn't change)
    BULK_DATA = 86400            # 24h (holders, supply chain)
    INTRADAY = 60                # 1 min (intraday bars/ticks)
    SEARCH = 3600                # 1h (security/field search results)


@dataclass
class CacheEntry:
    """A cached value with expiration."""
    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class BloombergCache:
    """Thread-safe TTL-based in-memory cache for Bloomberg API responses.

    Keys are derived from (request_type, securities, fields, overrides).
    Automatically evicts expired entries on access and periodically.

    Usage:
        cache = BloombergCache.get_instance()

        # Check cache
        result = cache.get("reference", securities, fields, overrides)
        if result is not None:
            return result

        # Fetch from Bloomberg...
        data = fetch_from_bloomberg(...)

        # Store in cache
        cache.set("reference", securities, fields, overrides, data, ttl=CacheTTL.PRICE)
    """

    _instance: Optional["BloombergCache"] = None
    _lock = threading.Lock()

    def __init__(self, max_entries: int = 10000):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self._access_lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    @classmethod
    def get_instance(cls, max_entries: int = 10000) -> "BloombergCache":
        """Get or create singleton cache instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(max_entries=max_entries)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    @staticmethod
    def _make_key(
        request_type: str,
        securities: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        overrides: Optional[Dict[str, Any]] = None,
        extra: Optional[str] = None,
    ) -> str:
        """Build a deterministic cache key from request parameters."""
        key_parts = [request_type]
        if securities:
            key_parts.append("|".join(sorted(securities)))
        if fields:
            key_parts.append("|".join(sorted(fields)))
        if overrides:
            key_parts.append(json.dumps(overrides, sort_keys=True, default=str))
        if extra:
            key_parts.append(extra)

        raw = "::".join(key_parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self,
        request_type: str,
        securities: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        overrides: Optional[Dict[str, Any]] = None,
        extra: Optional[str] = None,
    ) -> Optional[Any]:
        """Look up cached value. Returns None on miss or expiry."""
        key = self._make_key(request_type, securities, fields, overrides, extra)

        with self._access_lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats["misses"] += 1
                self._stats["evictions"] += 1
                return None

            entry.hits += 1
            self._stats["hits"] += 1
            return entry.value

    def set(
        self,
        request_type: str,
        securities: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        overrides: Optional[Dict[str, Any]] = None,
        extra: Optional[str] = None,
        value: Any = None,
        ttl: Optional[CacheTTL] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store a value in cache with TTL.

        Args:
            request_type: Type of request (e.g., "reference", "historical")
            securities: List of security identifiers
            fields: List of Bloomberg fields
            overrides: Optional field overrides
            extra: Additional key component (e.g., date range)
            value: The data to cache
            ttl: TTL preset from CacheTTL enum
            ttl_seconds: Custom TTL in seconds (overrides ttl enum)
        """
        if value is None:
            return

        seconds = ttl_seconds if ttl_seconds is not None else (ttl.value if ttl else CacheTTL.PRICE.value)
        key = self._make_key(request_type, securities, fields, overrides, extra)

        with self._access_lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self._max_entries:
                self._evict_expired()
                if len(self._cache) >= self._max_entries:
                    self._evict_oldest(count=max(1, self._max_entries // 10))

            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + seconds,
            )

    def get_stale(
        self,
        request_type: str,
        securities: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        overrides: Optional[Dict[str, Any]] = None,
        extra: Optional[str] = None,
    ) -> Optional[Tuple[Any, float]]:
        """Return expired cached value if available (for degraded mode).

        Returns:
            Tuple of (value, age_seconds) or None if not in cache at all.
        """
        key = self._make_key(request_type, securities, fields, overrides, extra)

        with self._access_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            age = time.time() - entry.created_at
            return (entry.value, age)

    def invalidate(
        self,
        request_type: str,
        securities: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        overrides: Optional[Dict[str, Any]] = None,
        extra: Optional[str] = None,
    ) -> bool:
        """Remove a specific entry from cache. Returns True if found."""
        key = self._make_key(request_type, securities, fields, overrides, extra)
        with self._access_lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        """Clear all cached entries. Returns count of entries cleared."""
        with self._access_lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats = {"hits": 0, "misses": 0, "evictions": 0}
            return count

    def _evict_expired(self) -> int:
        """Remove all expired entries. Returns count evicted."""
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]
        for k in expired_keys:
            del self._cache[k]
        self._stats["evictions"] += len(expired_keys)
        return len(expired_keys)

    def _evict_oldest(self, count: int = 100) -> int:
        """Evict oldest entries by creation time."""
        if not self._cache:
            return 0
        sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        to_evict = sorted_keys[:count]
        for k in to_evict:
            del self._cache[k]
        self._stats["evictions"] += len(to_evict)
        return len(to_evict)

    @property
    def size(self) -> int:
        """Number of entries currently in cache."""
        return len(self._cache)

    @property
    def stats(self) -> Dict[str, int]:
        """Cache hit/miss/eviction statistics."""
        return {**self._stats, "size": self.size}

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as percentage."""
        total = self._stats["hits"] + self._stats["misses"]
        if total == 0:
            return 0.0
        return (self._stats["hits"] / total) * 100
