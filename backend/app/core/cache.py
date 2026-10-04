import asyncio
import time


class TTLCache:
    """Простейший in-memory кэш с TTL и одной блокировкой.

    Точка расширения: заменить на Redis/БД, не меняя вызывающий код.
    """

    def __init__(self) -> None:
        self._items: dict[str, tuple[object, float | None]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> object | None:
        async with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            value, expires_at = item
            if expires_at is not None and expires_at < time.monotonic():
                self._items.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: object, ttl: int | None = None) -> None:
        async with self._lock:
            self._items[key] = (value, time.monotonic() + ttl if ttl else None)
