import asyncio

import pytest

from conftest import NO_RESULTS
from eventradar.budget import BudgetedSearch, BudgetExceeded, ResponseCache

PARAMS = {"engine": "google_events", "q": "Python events in South Africa", "gl": "za"}


def test_budget_stops_extra_searches(backend):
    search = BudgetedSearch(backend, max_searches=1)

    asyncio.run(search.search(PARAMS))
    with pytest.raises(BudgetExceeded, match="budget of 1 SerpApi searches"):
        asyncio.run(search.search({**PARAMS, "gl": "mz"}))
    assert search.searches_made == 1


def test_cached_answers_are_free(backend, tmp_path):
    cache = ResponseCache(tmp_path)
    first = BudgetedSearch(backend, max_searches=5, cache=cache)
    asyncio.run(first.search(PARAMS))

    second = BudgetedSearch(backend, max_searches=5, cache=cache)
    payload, from_cache = asyncio.run(second.search(PARAMS))

    assert from_cache is True
    assert payload["events_results"]
    assert second.searches_made == 0
    assert len(backend.requests) == 1


def test_cache_expires(tmp_path):
    now = [0.0]
    cache = ResponseCache(tmp_path, ttl_seconds=10, clock=lambda: now[0])
    cache.put(PARAMS, {"events_results": []})

    now[0] = 9
    assert cache.get(PARAMS) == {"events_results": []}
    now[0] = 10
    assert cache.get(PARAMS) is None


def test_errors_are_not_cached_but_empty_results_are(backend, tmp_path):
    cache = ResponseCache(tmp_path)
    backend.responses["google_events:za"] = {"error": "Invalid API key."}
    asyncio.run(BudgetedSearch(backend, max_searches=5, cache=cache).search(PARAMS))
    assert cache.get(PARAMS) is None

    backend.responses["google_events:za"] = NO_RESULTS
    asyncio.run(BudgetedSearch(backend, max_searches=5, cache=cache).search(PARAMS))
    assert cache.get(PARAMS) == NO_RESULTS
