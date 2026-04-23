"""Caching module for AutoPipe."""
import hashlib
import json
import pickle
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar

import cachetools

from ..exceptions import CacheError

T = TypeVar('T')


class CacheBackend(ABC, Generic[T]):
    """Abstract base class for cache backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """Get value from cache."""

    @abstractmethod
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """Set value in cache."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete value from cache."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""

    @abstractmethod
    def ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL for key in seconds."""


class MemoryCache(CacheBackend[T]):
    """In-memory cache using cachetools."""

    def __init__(self, max_size: int = 10000, default_ttl: int = 3600):
        self._cache: dict[str, tuple[T, float]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = cachetools.LRUCache(maxsize=max_size)

    def get(self, key: str) -> Optional[T]:
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        if len(self._cache) >= self._max_size and key not in self._cache:
            # Evict oldest
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        ttl = ttl or self._default_ttl
        self._cache[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def ttl(self, key: str) -> Optional[int]:
        if key not in self._cache:
            return None
        _, expiry = self._cache[key]
        remaining = int(expiry - time.time())
        return max(0, remaining) if remaining > 0 else None


class DiskCache(CacheBackend[T]):
    """Disk-based cache using pickle."""

    def __init__(self, directory: str = "./.autopipe_cache", default_ttl: int = 3600):
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl
        self._metadata_file = self._directory / "metadata.json"
        self._metadata: dict[str, float] = self._load_metadata()

    def _load_metadata(self) -> dict[str, float]:
        """Load cache metadata."""
        if self._metadata_file.exists():
            try:
                with open(self._metadata_file, "r") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save_metadata(self) -> None:
        """Save cache metadata."""
        try:
            with open(self._metadata_file, "w") as f:
                json.dump(self._metadata, f)
        except OSError:
            pass

    def _get_path(self, key: str) -> Path:
        """Get cache file path for key."""
        hashed = hashlib.md5(key.encode()).hexdigest()
        return self._directory / f"{hashed}.cache"

    def get(self, key: str) -> Optional[T]:
        if key not in self._metadata:
            return None

        expiry = self._metadata[key]
        if time.time() > expiry:
            self.delete(key)
            return None

        cache_path = self._get_path(key)
        if not cache_path.exists():
            self._metadata.pop(key, None)
            self._save_metadata()
            return None

        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except (OSError, pickle.PickleError):
            self.delete(key)
            return None

    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        ttl = ttl or self._default_ttl
        cache_path = self._get_path(key)

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(value, f)
            self._metadata[key] = time.time() + ttl
            self._save_metadata()
        except (OSError, pickle.PickleError) as e:
            raise CacheError(f"Failed to cache value: {e}")

    def delete(self, key: str) -> None:
        cache_path = self._get_path(key)
        if cache_path.exists():
            cache_path.unlink(missing_ok=True)
        self._metadata.pop(key, None)
        self._save_metadata()

    def clear(self) -> None:
        for cache_file in self._directory.glob("*.cache"):
            cache_file.unlink(missing_ok=True)
        self._metadata.clear()
        self._save_metadata()

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def ttl(self, key: str) -> Optional[int]:
        if key not in self._metadata:
            return None
        expiry = self._metadata[key]
        remaining = int(expiry - time.time())
        return max(0, remaining) if remaining > 0 else None


class CacheManager:
    """Manages caching for pipeline execution."""

    def __init__(
        self,
        enabled: bool = True,
        backend: str = "memory",
        ttl: int = 3600,
        max_size: int = 10000,
        directory: str = "./.autopipe_cache",
    ):
        self.enabled = enabled
        self.ttl = ttl
        self.backend_type = backend

        if backend == "memory":
            self._backend: CacheBackend[Any] = MemoryCache(max_size=max_size, default_ttl=ttl)
        elif backend == "disk":
            self._backend = DiskCache(directory=directory, default_ttl=ttl)
        else:
            raise CacheError(f"Unknown cache backend: {backend}")

    def _generate_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate cache key from arguments."""
        key_data = json.dumps((args, kwargs), sort_keys=True, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.enabled:
            return None
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        if not self.enabled:
            return
        self._backend.set(key, value, ttl or self.ttl)

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        if not self.enabled:
            return
        self._backend.delete(key)

    def clear(self) -> None:
        """Clear all cache."""
        self._backend.clear()

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.enabled:
            return False
        return self._backend.exists(key)

    def ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL for key."""
        if not self.enabled:
            return None
        return self._backend.ttl(key)

    def cached(
        self,
        key_fn: Optional[Callable[..., str]] = None,
        ttl: Optional[int] = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator for caching function results."""
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            def wrapper(*args: Any, **kwargs: Any) -> T:
                if not self.enabled:
                    return func(*args, **kwargs)

                if key_fn:
                    cache_key = key_fn(*args, **kwargs)
                else:
                    cache_key = self._generate_key(func.__name__, *args, **kwargs)

                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result

            return wrapper
        return decorator


# Global cache instance
_cache_instance: Optional[CacheManager] = None


def init_cache(
    enabled: bool = True,
    backend: str = "memory",
    ttl: int = 3600,
    max_size: int = 10000,
    directory: str = "./.autopipe_cache",
) -> CacheManager:
    """Initialize the global cache."""
    global _cache_instance
    _cache_instance = CacheManager(
        enabled=enabled,
        backend=backend,
        ttl=ttl,
        max_size=max_size,
        directory=directory,
    )
    return _cache_instance


def get_cache() -> Optional[CacheManager]:
    """Get the global cache instance."""
    return _cache_instance


def cached(
    key_fn: Optional[Callable[..., str]] = None,
    ttl: Optional[int] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for caching using the global cache."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            cache = get_cache()
            if cache is None:
                return func(*args, **kwargs)
            return cache.cached(key_fn, ttl)(func)(*args, **kwargs)
        return wrapper
    return decorator
