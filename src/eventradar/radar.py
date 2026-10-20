"""Run the searches in parallel, keep what is relevant, and build the ``Radar``."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from eventradar import parsing
from eventradar.budget import BudgetedSearch, ResponseCache
from eventradar.mcp_search import NO_RESULTS_MARKER, McpSearchBackend, SearchFailed
from eventradar.models import Country, Event, Link, Radar, SearchRecord
from eventradar.queries import RadarQuery

PYTHON_WORDS = frozenset(
    {"python", "pycon", "pydata", "django", "flask", "fastapi", "jupyter", "pyladies", "pandas"}
)
MAX_COMMUNITY_LINKS_PER_COUNTRY = 6
MAX_TECH_EVENTS_PER_COUNTRY = 8
ENGINE_LABELS = {"google_events": "Google Events", "google_light": "Google Light"}


@dataclass(frozen=True)
class _Answer:
    payload: dict[str, Any]
    record: SearchRecord


def radar_title(topic: str, countries: list[str], *, near: bool = False) -> str:
    if near:
        return f"{topic} conferences and communities near {countries[0]}"
    names = (
        countries[0] if len(countries) == 1 else f"{', '.join(countries[:-1])} and {countries[-1]}"
    )
    return f"{topic} conferences and communities in {names}"


def fit_to_budget(
    countries: list[Country], max_searches: int, *, searches_per_country: int = 1
) -> tuple[list[Country], list[Country]]:
    """Keep the first countries whose searches fit in the budget; skip the rest."""
    room = max(max_searches // searches_per_country, 0)
    return countries[:room], countries[room:]


async def collect(
    title: str,
    query: RadarQuery,
    backend: McpSearchBackend,
    *,
    max_searches: int,
    cache: ResponseCache | None,
    skipped: list[Country],
) -> tuple[Radar, int]:
    """Open the MCP session, build the radar, and return it with the searches spent."""
    async with backend:
        search = BudgetedSearch(backend, max_searches=max_searches, cache=cache)
        radar = await build_radar(title, query, search, skipped=skipped)
    return radar, search.searches_made


async def build_radar(
    title: str,
    query: RadarQuery,
    search: BudgetedSearch,
    *,
    skipped: list[Country] | None = None,
    today: date | None = None,
) -> Radar:
    today = today or date.today()
    community_answers, event_answers = await _search_all(query, search)
    topic_words = PYTHON_WORDS | query.topic_words

    communities: dict[str, list[Link]] = {}
    hidden = 0
    seen: set[str] = set()
    for country, answer in zip(query.countries, community_answers, strict=True):
        found = [link for link in parsing.links(answer.payload) if link.title and link.link]
        relevant = [
            link
            for link in found
            if _link_words(link) & topic_words and is_about_country(link, country)
        ]
        hidden += len(found) - len(relevant)
        communities[country.name] = _upcoming_first(_new_links(relevant, seen), today)[
            :MAX_COMMUNITY_LINKS_PER_COUNTRY
        ]

    python_events: list[Event] = []
    tech_events: dict[str, list[Event]] = {}
    for country, answer in zip(query.countries, event_answers, strict=False):
        upcoming = _upcoming(parsing.events(answer.payload, country.name, today=today), today)
        listed = _by_date(_one_per_title(upcoming))
        highlighted = [event for event in listed if _event_words(event) & topic_words]
        python_events.extend(highlighted)
        rest = [event for event in listed if event not in highlighted]
        tech_events[country.name] = rest[:MAX_TECH_EVENTS_PER_COUNTRY]

    return Radar(
        title=title,
        countries=[country.name for country in query.countries],
        topic=query.topic,
        when=query.when,
        radar_date=today,
        communities=communities,
        with_tech_events=query.tech_events,
        python_events=_by_date(python_events),
        tech_events=tech_events,
        searches=[answer.record for answer in [*community_answers, *event_answers]],
        hidden_off_topic=hidden,
        skipped_countries=[country.name for country in skipped or []],
    )


async def _search_all(
    query: RadarQuery, search: BudgetedSearch
) -> tuple[list[_Answer], list[_Answer]]:
    community_tasks = [
        _ask(search, country.name, query.community_params(country)) for country in query.countries
    ]
    event_tasks = (
        [_ask(search, country.name, query.event_params(country)) for country in query.countries]
        if query.tech_events
        else []
    )
    answers = await asyncio.gather(*community_tasks, *event_tasks)
    return list(answers[: len(community_tasks)]), list(answers[len(community_tasks) :])


async def _ask(search: BudgetedSearch, label: str, params: dict[str, Any]) -> _Answer:
    engine = ENGINE_LABELS.get(params["engine"], params["engine"])
    try:
        payload, from_cache = await search.search(params)
    except SearchFailed as exc:
        return _Answer({}, SearchRecord(label, engine, params["q"], error=str(exc)))
    error = str(payload.get("error") or "")
    count = len(payload.get("events_results") or payload.get("organic_results") or [])
    record = SearchRecord(
        label,
        engine,
        params["q"],
        result_count=count,
        error=None if not error or NO_RESULTS_MARKER in error else error,
        from_cache=from_cache,
    )
    return _Answer(payload, record)


def is_about_country(link: Link, country: Country) -> bool:
    """The page names the country or one of its cities, or sits on the country's domain.

    Google fills a thin country's results with pages from elsewhere, such as PyCon US.
    """
    text = f" {link.title} {link.snippet} ".lower()
    if any(name.lower() in text for name in (country.name, *country.local_names)):
        return True
    if not country.gl:
        return False
    domain = link.domain.lower()
    return domain.endswith(f".{country.gl}") or domain.startswith(f"{country.gl}.")


def _upcoming_first(links: list[Link], today: date) -> list[Link]:
    """Upcoming pages by date, then undated ones in Google's order, then past ones, newest first."""

    def rank(item: tuple[int, Link]) -> tuple[int, int, int]:
        position, link = item
        if link.starts_on is None:
            return (1, 0, position)
        if link.starts_on >= today:
            return (0, link.starts_on.toordinal(), position)
        return (2, -link.starts_on.toordinal(), position)

    return [link for _, link in sorted(enumerate(links), key=rank)]


def _upcoming(events: list[Event], today: date) -> list[Event]:
    """Drop events without a title, and events whose start date has passed."""
    return [e for e in events if e.title and (e.starts_on is None or e.starts_on >= today)]


def _one_per_title(events: list[Event]) -> list[Event]:
    """Google lists a multi-day event once per day; keep its first day."""
    first: dict[str, Event] = {}
    for event in _by_date(events):
        first.setdefault(event.title.lower(), event)
    return list(first.values())


def _event_words(event: Event) -> set[str]:
    return _words(f"{event.title} {event.kind} {event.description}")


def _link_words(link: Link) -> set[str]:
    return _words(f"{link.title} {link.snippet} {link.link}")


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _new_links(links: list[Link], seen: set[str]) -> list[Link]:
    """Links not already listed for this or an earlier country."""
    kept = []
    for link in links:
        if link.link not in seen:
            seen.add(link.link)
            kept.append(link)
    return kept


def _by_date(events: list[Event]) -> list[Event]:
    return sorted(events, key=lambda e: (e.starts_on is None, e.starts_on or date.max, e.title))
