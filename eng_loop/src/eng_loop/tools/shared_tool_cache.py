from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# Tools whose results are safe to cache (idempotent reads)
CACHABLE_TOOLS = frozenset({"read", "glob", "grep"})

# Tools that invalidate the cache (mutating operations)
INVALIDATING_TOOLS = frozenset({"write", "edit", "bash"})


class SharedToolResultCache:
    """Singleton cache for tool results shared across all agents in a run.

    Prevents redundant file reads, globs, and greps across different stage
    executions. For example, if agent A reads config.yaml, agent B will
    get the cached result instead of reading the file again.

    Thread-safe with lock-based access. Supports memory limits and TTL.
    """

    def __init__(
        self,
        max_size_mb: int = 50,
        ttl_seconds: int = 300,
    ) -> None:
        self._store: dict[str, tuple[str, float]] = {}
        self._max_bytes = max_size_mb * 1024 * 1024
        self._ttl = ttl_seconds
        self._total_bytes = 0
        self._lock = threading.Lock()
        # Stats
        self.hits = 0
        self.misses = 0
        self.invalidations = 0
        self.evictions = 0

    def get(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """Return cached result if available and not expired, else None."""
        if tool_name not in CACHABLE_TOOLS:
            return None

        key = self._make_key(tool_name, args)

        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None

            result, stored_at = entry
            if time.time() - stored_at > self._ttl:
                # Expired
                self._total_bytes -= len(result.encode("utf-8"))
                del self._store[key]
                self.misses += 1
                return None

            self.hits += 1
            return result

    def set(self, tool_name: str, args: dict[str, Any], result: str) -> None:
        """Cache a tool result with memory-based eviction."""
        if tool_name not in CACHABLE_TOOLS:
            return

        key = self._make_key(tool_name, args)
        # Cap individual entries at 8000 chars to prevent memory bloat
        cached_result = result[:8000] if len(result) > 8000 else result
        result_bytes = len(cached_result.encode("utf-8"))

        with self._lock:
            # If key exists, subtract old size
            existing = self._store.get(key)
            if existing:
                self._total_bytes -= len(existing[0].encode("utf-8"))

            # Evict if needed
            while self._total_bytes + result_bytes > self._max_bytes:
                evicted = self._evict_one()
                if evicted is None:
                    # Cache is full but nothing to evict (shouldn't happen)
                    return

            self._store[key] = (cached_result, time.time())
            self._total_bytes += result_bytes
            self.misses += 1

    def invalidate_path(self, path: str) -> None:
        """Invalidate all cache entries that reference a specific file path."""
        with self._lock:
            to_remove = [key for key in self._store if path in key]
            for key in to_remove:
                self._total_bytes -= len(self._store[key][0].encode("utf-8"))
                del self._store[key]
            self.invalidations += len(to_remove)
            if to_remove:
                logger.debug(
                    "SharedToolResultCache: invalidated %d entries for path %s",
                    len(to_remove),
                    path,
                )

    def invalidate_on_mutation(self, tool_name: str, args: dict[str, Any]) -> None:
        """Invalidate cache entries affected by a mutating tool."""
        if tool_name not in INVALIDATING_TOOLS:
            return

        modified_path = self._extract_path(args)

        if modified_path:
            self.invalidate_path(modified_path)
        elif tool_name == "bash":
            # Bash can modify anything — full invalidation
            with self._lock:
                self._store.clear()
                self._total_bytes = 0
                self.invalidations += 1

    def get_stats(self) -> dict[str, int]:
        """Return cache statistics."""
        with self._lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "invalidations": self.invalidations,
                "evictions": self.evictions,
                "entries": len(self._store),
                "total_bytes": self._total_bytes,
                "hit_rate": round(hit_rate, 1),
            }

    def reset(self) -> None:
        """Clear all cached data (called between runs)."""
        with self._lock:
            self._store.clear()
            self._total_bytes = 0
            self.hits = 0
            self.misses = 0
            self.invalidations = 0
            self.evictions = 0

    def _evict_one(self) -> str | None:
        """Evict one entry using LRU (oldest accessed). Returns evicted key or None."""
        if not self._store:
            return None

        # Find the oldest entry
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        evicted_value = self._store.pop(oldest_key)
        self._total_bytes -= len(evicted_value[0].encode("utf-8"))
        self.evictions += 1
        return oldest_key

    def _make_key(self, tool_name: str, args: dict[str, Any]) -> str:
        """Create a deterministic cache key from tool name and arguments."""
        return f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"

    def _extract_path(self, args: dict[str, Any]) -> str | None:
        """Extract the file path from tool args for targeted invalidation."""
        for key in ("file_path", "path", "old_string", "filePath"):
            if key in args:
                return str(args[key])
        # For single-arg tools, the path might be the value
        if len(args) == 1:
            val = next(iter(args.values()))
            if isinstance(val, str) and (".ts" in val or ".js" in val or ".py" in val or "/" in val or "\\" in val):
                return val
        return None


# Global shared cache instance
_shared_cache: SharedToolResultCache | None = None
_cache_lock = threading.Lock()


def get_shared_cache(config: dict[str, Any] | None = None) -> SharedToolResultCache:
    """Get or create the global shared tool result cache.

    Reads configuration from config.yaml if provided:
        cache:
            enabled: true
            max_size_mb: 50
            ttl_seconds: 300
            shared_between_stages: true
    """
    global _shared_cache

    with _cache_lock:
        if _shared_cache is None:
            max_size_mb = 50
            ttl_seconds = 300

            if config:
                cache_cfg = config.get("cache", {})
                if not cache_cfg.get("enabled", True):
                    # If cache is disabled, still return a cache but with minimal settings
                    max_size_mb = 1
                    ttl_seconds = 60
                else:
                    max_size_mb = cache_cfg.get("max_size_mb", 50)
                    ttl_seconds = cache_cfg.get("ttl_seconds", 300)

            _shared_cache = SharedToolResultCache(
                max_size_mb=max_size_mb,
                ttl_seconds=ttl_seconds,
            )
            logger.debug(
                "SharedToolResultCache: initialized (max_size=%dMB, ttl=%ds)",
                max_size_mb,
                ttl_seconds,
            )

        return _shared_cache


def reset_shared_cache() -> None:
    """Reset the global shared cache (called between runs)."""
    global _shared_cache
    with _cache_lock:
        if _shared_cache:
            _shared_cache.reset()
        _shared_cache = None


def get_cache_stats() -> dict[str, int]:
    """Get current cache statistics (safe to call without an active cache)."""
    if _shared_cache:
        return _shared_cache.get_stats()
    return {
        "hits": 0,
        "misses": 0,
        "invalidations": 0,
        "evictions": 0,
        "entries": 0,
        "total_bytes": 0,
        "hit_rate": 0.0,
    }
