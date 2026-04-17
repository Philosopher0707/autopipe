"""Tests for the caching module."""
import time
import pytest
from pathlib import Path

from autopipe.caching.manager import MemoryCache, DiskCache, CacheManager
from autopipe.exceptions import CacheError


class TestMemoryCache:
    """Tests for MemoryCache."""

    def test_basic_get_set(self):
        """Test basic get and set operations."""
        cache = MemoryCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        """Test getting a non-existent key."""
        cache = MemoryCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry(self):
        """Test that expired entries are removed."""
        cache = MemoryCache(default_ttl=1)  # 1 second TTL
        cache.set("key1", "value1")
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_delete(self):
        """Test delete operation."""
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        """Test clearing all cache."""
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_exists(self):
        """Test exists check."""
        cache = MemoryCache()
        assert not cache.exists("key1")
        cache.set("key1", "value1")
        assert cache.exists("key1")

    def test_ttl(self):
        """Test TTL retrieval."""
        cache = MemoryCache(default_ttl=60)
        cache.set("key1", "value1")
        ttl = cache.ttl("key1")
        assert ttl is not None
        assert 0 < ttl <= 60

    def test_max_size_eviction(self):
        """Test that old entries are evicted when max size is reached."""
        cache = MemoryCache(max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict one
        # At least one of the first two should be evicted
        count = sum(1 for k in ["key1", "key2", "key3"] if cache.get(k) is not None)
        assert count == 2


class TestDiskCache:
    """Tests for DiskCache."""

    def test_basic_get_set(self, tmp_path):
        """Test basic get and set operations."""
        cache = DiskCache(directory=str(tmp_path))
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self, tmp_path):
        """Test getting a non-existent key."""
        cache = DiskCache(directory=str(tmp_path))
        assert cache.get("nonexistent") is None

    def test_expired_entry(self, tmp_path):
        """Test that expired entries are removed."""
        cache = DiskCache(directory=str(tmp_path), default_ttl=1)
        cache.set("key1", "value1")
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_delete(self, tmp_path):
        """Test delete operation."""
        cache = DiskCache(directory=str(tmp_path))
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self, tmp_path):
        """Test clearing all cache."""
        cache = DiskCache(directory=str(tmp_path))
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestCacheManager:
    """Tests for CacheManager."""

    def test_memory_backend(self):
        """Test CacheManager with memory backend."""
        manager = CacheManager(backend="memory", ttl=3600)
        manager.set("key1", "value1")
        assert manager.get("key1") == "value1"

    def test_disabled_cache(self):
        """Test disabled cache."""
        manager = CacheManager(enabled=False)
        manager.set("key1", "value1")
        assert manager.get("key1") is None

    def test_custom_ttl(self):
        """Test custom TTL."""
        manager = CacheManager()
        manager.set("key1", "value1", ttl=60)
        assert manager.get("key1") == "value1"

    def test_generate_key(self):
        """Test key generation."""
        manager = CacheManager()
        key = manager._generate_key("func_name", 1, 2, a="3")
        # Key should be deterministic
        key2 = manager._generate_key("func_name", 1, 2, a="3")
        assert key == key2

    def test_invalid_backend(self):
        """Test invalid backend raises error."""
        with pytest.raises(CacheError):
            CacheManager(backend="invalid_backend")

    def test_cached_decorator(self):
        """Test the cached decorator."""
        manager = CacheManager()
        
        @manager.cached(ttl=3600)
        def expensive_function(x):
            return x * 2
        
        # First call should compute
        result1 = expensive_function(5)
        assert result1 == 10

    def test_cached_with_disabled_cache(self):
        """Test decorator when cache is disabled."""
        manager = CacheManager(enabled=False)
        call_count = [0]
        
        @manager.cached()
        def expensive_function(x):
            call_count[0] += 1
            return x * 2
        
        # Both calls should execute
        expensive_function(5)
        expensive_function(5)
        assert call_count[0] == 2
