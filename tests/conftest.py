from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from eventradar.models import Country
from eventradar.queries import RadarQuery

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 20)
NO_RESULTS = {"error": "Google Events hasn't returned any results for this query."}


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeBackend:
    """Stands in for the MCP server so tests spend no credits.

    Answers by ``<engine>:<gl>``, e.g. ``google_light:mz`` or ``google_events:za``.
    A response can be an exception, to simulate a failed search.
    """

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {
            "google_light:mz": load_fixture("google_light_communities"),
            "google_light:na": load_fixture("google_light_namibia"),
            "google_events:za": load_fixture("google_events_za"),
        }
        self.requests: list[dict[str, Any]] = []

    async def __aenter__(self) -> FakeBackend:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def search(self, params: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(dict(params))
        response = self.responses.get(f"{params['engine']}:{params.get('gl')}", NO_RESULTS)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


MOZAMBIQUE = Country("Mozambique", "mz", ("Maputo",))
SOUTH_AFRICA = Country("South Africa", "za", ("Johannesburg",))
NAMIBIA = Country("Namibia", "na", ("Windhoek",))


@pytest.fixture
def query() -> RadarQuery:
    return RadarQuery((MOZAMBIQUE, SOUTH_AFRICA, NAMIBIA))


@pytest.fixture
def events_query() -> RadarQuery:
    return RadarQuery((MOZAMBIQUE, SOUTH_AFRICA), tech_events=True)
