"""Plain data shared by the search, radar and render modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class Country:
    name: str
    gl: str | None = None
    """Google country code for local results, when known."""
    local_names: tuple[str, ...] = ()
    """Cities and other names that show a page is about this country, e.g. "Windhoek"."""


@dataclass(frozen=True)
class Event:
    title: str
    country: str
    link: str = ""
    """The event or ticket page; empty when Google lists none."""
    when: str = ""
    """Google's own date text, e.g. "Nov 21, 8:30 AM"."""
    starts_on: date | None = None
    time: str = ""
    kind: str = ""
    """Google's event type, e.g. "Technology conference"."""
    place: str = ""
    description: str = ""


@dataclass(frozen=True)
class Link:
    title: str
    link: str
    snippet: str = ""
    starts_on: date | None = None
    """A date written in the title or snippet, such as "26 February – 4 March 2027"."""

    @property
    def domain(self) -> str:
        return urlparse(self.link).netloc.removeprefix("www.")


@dataclass(frozen=True)
class SearchRecord:
    label: str
    """The country searched."""
    engine: str
    query: str
    result_count: int = 0
    error: str | None = None
    from_cache: bool = False


@dataclass
class Radar:
    title: str
    countries: list[str]
    topic: str
    when: str
    radar_date: date
    communities: dict[str, list[Link]] = field(default_factory=dict)
    """Conference and community pages, by country: the main part of the radar."""
    with_tech_events: bool = False
    python_events: list[Event] = field(default_factory=list)
    """Events from the listings that mention the topic; also kept out of ``tech_events``."""
    tech_events: dict[str, list[Event]] = field(default_factory=dict)
    searches: list[SearchRecord] = field(default_factory=list)
    hidden_off_topic: int = 0
    skipped_countries: list[str] = field(default_factory=list)

    @property
    def community_count(self) -> int:
        return sum(len(links) for links in self.communities.values())

    @property
    def tech_event_count(self) -> int:
        return sum(len(events) for events in self.tech_events.values())

    @property
    def all_searches_failed(self) -> bool:
        return bool(self.searches) and all(record.error for record in self.searches)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
