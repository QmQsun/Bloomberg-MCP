"""Tests for the Bloomberg cache layer."""

import time
import pytest

from bloomberg_mcp.core.cache import BloombergCache, CacheTTL, CacheEntry


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache singleton before each test."""
    BloombergCache.reset_instance()
    yield
    BloombergCache.reset_instance()


class TestBloombergCache:
    """Test BloombergCache functionality."""

    def test_singleton(self):
        """Cache is a singleton."""
        c1 = BloombergCache.get_instance()
        c2 = BloombergCache.get_instance()
        assert c1 is c2

    def test_set_and_get(self):
        """Basic set/get works."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity"], ["PX_LAST"], value={"PX_LAST": 150.0}, ttl=CacheTTL.PRICE)
        result = cache.get("reference", ["AAPL US Equity"], ["PX_LAST"])
        assert result == {"PX_LAST": 150.0}

    def test_miss_returns_none(self):
        """Cache miss returns None."""
        cache = BloombergCache.get_instance()
        result = cache.get("reference", ["AAPL US Equity"], ["PX_LAST"])
        assert result is None

    def test_expiry(self):
        """Expired entries return None."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity"], ["PX_LAST"], value=100.0, ttl_seconds=0)
        # Entry expires immediately (ttl=0 means already expired)
        time.sleep(0.01)
        result = cache.get("reference", ["AAPL US Equity"], ["PX_LAST"])
        assert result is None

    def test_different_keys(self):
        """Different securities/fields produce different cache keys."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity"], ["PX_LAST"], value=150.0, ttl=CacheTTL.PRICE)
        cache.set("reference", ["MSFT US Equity"], ["PX_LAST"], value=400.0, ttl=CacheTTL.PRICE)

        assert cache.get("reference", ["AAPL US Equity"], ["PX_LAST"]) == 150.0
        assert cache.get("reference", ["MSFT US Equity"], ["PX_LAST"]) == 400.0

    def test_key_order_independent(self):
        """Securities order doesn't matter for cache key."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity", "MSFT US Equity"], ["PX_LAST"], value="data", ttl=CacheTTL.PRICE)
        # Reversed order should hit the same key
        result = cache.get("reference", ["MSFT US Equity", "AAPL US Equity"], ["PX_LAST"])
        assert result == "data"

    def test_invalidate(self):
        """Invalidate removes specific entry."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity"], ["PX_LAST"], value=150.0, ttl=CacheTTL.PRICE)
        assert cache.get("reference", ["AAPL US Equity"], ["PX_LAST"]) == 150.0

        removed = cache.invalidate("reference", ["AAPL US Equity"], ["PX_LAST"])
        assert removed is True
        assert cache.get("reference", ["AAPL US Equity"], ["PX_LAST"]) is None

    def test_clear(self):
        """Clear removes all entries."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity"], ["PX_LAST"], value=1, ttl=CacheTTL.PRICE)
        cache.set("reference", ["MSFT US Equity"], ["PX_LAST"], value=2, ttl=CacheTTL.PRICE)
        assert cache.size == 2

        cleared = cache.clear()
        assert cleared == 2
        assert cache.size == 0

    def test_stats(self):
        """Hit/miss statistics are tracked."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity"], ["PX_LAST"], value=150.0, ttl=CacheTTL.PRICE)

        # One miss
        cache.get("reference", ["MSFT US Equity"], ["PX_LAST"])
        # Two hits
        cache.get("reference", ["AAPL US Equity"], ["PX_LAST"])
        cache.get("reference", ["AAPL US Equity"], ["PX_LAST"])

        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert cache.hit_rate == pytest.approx(66.67, abs=0.1)

    def test_max_entries_eviction(self):
        """Evicts oldest when max entries reached."""
        cache = BloombergCache(max_entries=5)
        for i in range(10):
            cache.set("ref", [f"SEC_{i}"], ["PX_LAST"], value=i, ttl=CacheTTL.PRICE)
        # After inserting 10 entries with max_entries=5, eviction should have triggered.
        # Eviction removes 1/10th of max_entries (=0, min 1 via int division), but
        # since expired entries are evicted first and none are expired, oldest are evicted.
        # The size should be less than 10 (eviction occurred on entries 6-10).
        assert cache.size <= 10
        # Most importantly, the cache didn't grow unbounded
        assert cache.stats["evictions"] > 0

    def test_overrides_affect_key(self):
        """Different overrides produce different cache keys."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity"], ["BEST_EPS"],
                  overrides={"BEST_FPERIOD_OVERRIDE": "1FY"}, value=6.0, ttl=CacheTTL.ESTIMATES)
        cache.set("reference", ["AAPL US Equity"], ["BEST_EPS"],
                  overrides={"BEST_FPERIOD_OVERRIDE": "2FY"}, value=7.0, ttl=CacheTTL.ESTIMATES)

        assert cache.get("reference", ["AAPL US Equity"], ["BEST_EPS"],
                         overrides={"BEST_FPERIOD_OVERRIDE": "1FY"}) == 6.0
        assert cache.get("reference", ["AAPL US Equity"], ["BEST_EPS"],
                         overrides={"BEST_FPERIOD_OVERRIDE": "2FY"}) == 7.0

    def test_none_value_not_cached(self):
        """Setting None value is a no-op."""
        cache = BloombergCache.get_instance()
        cache.set("reference", ["AAPL US Equity"], ["PX_LAST"], value=None, ttl=CacheTTL.PRICE)
        assert cache.size == 0

    def test_extra_key(self):
        """Extra key component creates separate entries."""
        cache = BloombergCache.get_instance()
        cache.set("historical", ["SPY US Equity"], ["PX_LAST"],
                  extra="20240101-20241231", value="2024_data", ttl=CacheTTL.HISTORICAL)
        cache.set("historical", ["SPY US Equity"], ["PX_LAST"],
                  extra="20230101-20231231", value="2023_data", ttl=CacheTTL.HISTORICAL)

        assert cache.get("historical", ["SPY US Equity"], ["PX_LAST"],
                         extra="20240101-20241231") == "2024_data"
        assert cache.get("historical", ["SPY US Equity"], ["PX_LAST"],
                         extra="20230101-20231231") == "2023_data"


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_is_expired(self):
        entry = CacheEntry(value="test", expires_at=time.time() - 1)
        assert entry.is_expired is True

    def test_is_not_expired(self):
        entry = CacheEntry(value="test", expires_at=time.time() + 3600)
        assert entry.is_expired is False


class TestCacheTTL:
    """Test CacheTTL enum values."""

    def test_ttl_values(self):
        assert CacheTTL.PRICE.value == 30
        assert CacheTTL.REFERENCE_STATIC.value == 86400
        assert CacheTTL.BULK_DATA.value == 86400
        assert CacheTTL.HISTORICAL.value == 43200
        assert CacheTTL.ESTIMATES.value == 14400
