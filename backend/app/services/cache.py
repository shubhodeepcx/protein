from __future__ import annotations

import time
from collections import OrderedDict
from typing import Generic, TypeVar

V = TypeVar("V")

# Spec 5.4: in-memory LRU cache, size 256, TTL 1 hour, for metadata calls only.
DEFAULT_MAXSIZE = 256
DEFAULT_TTL_SECONDS = 3600.0


class TTLCache(Generic[V]):
    """Tiny LRU + TTL cache for external metadata lookups.

    Not thread-safe by design: it is only touched from the asyncio event loop.
    `maxsize` bounds a cache of small dicts, so a cap here is a real memory
    bound, not a proxy for the size of any single result.
    """

    def __init__(
        self,
        maxsize: int = DEFAULT_MAXSIZE,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._entries: OrderedDict[str, tuple[float, V]] = OrderedDict()

    def get(self, key: str) -> V | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def put(self, key: str, value: V) -> None:
        if key in self._entries:
            del self._entries[key]
        self._entries[key] = (time.monotonic() + self._ttl, value)
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
