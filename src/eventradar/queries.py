"""Decide what to search: Python communities per country, and optionally tech events."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from eventradar.models import Country

# Google Events date filters (the `htichips` parameter).
WHEN_FILTERS = {
    "any": None,
    "week": "date:week",
    "next_week": "date:next_week",
    "month": "date:month",
    "next_month": "date:next_month",
}

# Python community brands that rarely show up in Google Events but have their own pages.
COMMUNITY_TERMS = ("PyCon", "PyData", '"Python meetup"', '"Django Girls"', "PyLadies")

EVENTS_ENGINE = "google_events"
WEB_ENGINE = "google_light"


@dataclass(frozen=True)
class RadarQuery:
    countries: tuple[Country, ...]
    topic: str = "Python"
    when: str = "any"
    language: str = "en"
    tech_events: bool = False
    """Also search Google Events, which lists few events outside South Africa."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "topic", " ".join(self.topic.split()))
        if not self.countries:
            raise ValueError("At least one country is required.")
        if not self.topic:
            raise ValueError("A topic is required.")
        if self.when not in WHEN_FILTERS:
            raise ValueError(f"--when must be one of: {', '.join(WHEN_FILTERS)}.")

    @property
    def topic_words(self) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", self.topic.lower()))

    def event_query(self, country: Country) -> str:
        # Google Events lists almost no events for a niche word like "Python" in Africa, but
        # plenty of tech events; the topic is used to highlight the relevant ones instead.
        return f"tech events in {country.name}"

    def event_params(self, country: Country) -> dict[str, Any]:
        params: dict[str, Any] = {
            "engine": EVENTS_ENGINE,
            "q": self.event_query(country),
            "hl": self.language,
        }
        if country.gl:
            params["gl"] = country.gl
        if WHEN_FILTERS[self.when]:
            params["htichips"] = WHEN_FILTERS[self.when]
        return params

    def community_query(self, country: Country) -> str:
        # One search per country: a combined search shares its ten results between all of
        # them, and the biggest community crowds out the others.
        terms = (
            COMMUNITY_TERMS if self.topic.lower() == "python" else (self.topic, *COMMUNITY_TERMS)
        )
        return f"({' OR '.join(_quoted(term) for term in terms)}) ({_quoted(country.name)})"

    def community_params(self, country: Country) -> dict[str, Any]:
        params: dict[str, Any] = {
            "engine": WEB_ENGINE,
            "q": self.community_query(country),
            "hl": self.language,
        }
        if country.gl:
            params["gl"] = country.gl
        return params


def _quoted(text: str) -> str:
    return f'"{text}"' if " " in text and not text.startswith('"') else text
