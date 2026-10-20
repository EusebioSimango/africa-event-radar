"""Cap the SerpApi searches per run and reuse recent answers from a local cache."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eventradar.mcp_search import NO_RESULTS_MARKER, SearchBackend, SearchFailed

CACHE_SECONDS = 12 * 60 * 60


class BudgetExceeded(SearchFailed):
    pass


def default_cache_dir() -> Path:
    base = os.getenv("XDG_CACHE_HOME") or "~/.cache"
    return Path(base).expanduser() / "eventradar"


class ResponseCache:
    """SerpApi answers on disk, one JSON file per set of search parameters."""

    def __init__(
        self,
        directory: Path,
        *,
        ttl_seconds: float = CACHE_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._directory = directory
        self._ttl = ttl_seconds
        self._clock = clock

    def get(self, params: dict[str, Any]) -> dict[str, Any] | None:
        path = self._path(params)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if self._clock() - entry.get("saved_at", 0) >= self._ttl:
            return None
        payload = entry.get("payload")
        return payload if isinstance(payload, dict) else None

    def put(self, params: dict[str, Any], payload: dict[str, Any]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        entry = {"saved_at": self._clock(), "params": params, "payload": payload}
        self._path(params).write_text(json.dumps(entry), encoding="utf-8")

    def _path(self, params: dict[str, Any]) -> Path:
        digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        return self._directory / f"{digest}.json"


class BudgetedSearch:
    """Wraps a backend: answers from the cache for free, otherwise spends one search."""

    def __init__(
        self,
        backend: SearchBackend,
        *,
        max_searches: int,
        cache: ResponseCache | None = None,
    ) -> None:
        self._backend = backend
        self._max_searches = max_searches
        self._cache = cache
        self.searches_made = 0

    async def search(self, params: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Return ``(payload, from_cache)``."""
        cached = self._cache.get(params) if self._cache else None
        if cached is not None:
            return cached, True
        if self.searches_made >= self._max_searches:
            raise BudgetExceeded(
                f"Skipped: the budget of {self._max_searches} SerpApi searches per run is used up."
            )
        self.searches_made += 1
        payload = await self._backend.search(params)
        error = str(payload.get("error") or "")
        if self._cache and (not error or NO_RESULTS_MARKER in error):
            self._cache.put(params, payload)
        return payload, False
