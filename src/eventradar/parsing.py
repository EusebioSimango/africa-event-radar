"""Turn SerpApi JSON into ``Event`` and ``Link`` objects. Pure functions, no I/O."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from datetime import date, timedelta
from typing import Any

from eventradar.models import Event, Link

# An event dated this many days ago is still this year's, not next year's.
RECENT_PAST_DAYS = 31

# Google lists ticket sellers and info pages; an info page tells a visitor more.
TICKET_LINK_PREFERENCE = ("more info", "tickets")

_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}
_MONTH_DAY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b")
_DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\b")
_YEAR = re.compile(r"\b(20\d\d)\b")
_TIME = re.compile(r"\b\d{1,2}(?::\d{2})?\s?[AP]M\b", re.IGNORECASE)


def events(payload: Mapping[str, Any], country: str, *, today: date) -> list[Event]:
    return [
        Event(
            title=clean_text(item.get("title")),
            country=country,
            link=event_link(item),
            when=_when(item),
            starts_on=start_date(item, today=today),
            time=_time(_when(item)),
            kind=clean_text(item.get("type")),
            place=_place(item),
            description=clean_text(item.get("description")),
        )
        for item in _items(payload, "events_results")
    ]


def event_link(item: Mapping[str, Any]) -> str:
    """The event page if Google has one, else a ticket or info page, else the map."""
    if _link(item):
        return _link(item)
    tickets = [ticket for ticket in _items(item, "ticket_info") if _link(ticket)]
    for link_type in TICKET_LINK_PREFERENCE:
        for ticket in tickets:
            if clean_text(ticket.get("link_type")).lower() == link_type:
                return _link(ticket)
    if tickets:
        return _link(tickets[0])
    location = item.get("event_location_map")
    return _link(location) if isinstance(location, Mapping) else ""


def links(payload: Mapping[str, Any]) -> list[Link]:
    found = []
    for item in _items(payload, "organic_results"):
        title, snippet = clean_text(item.get("title")), clean_text(item.get("snippet"))
        found.append(
            Link(
                title=title,
                link=_link(item),
                snippet=snippet,
                starts_on=mentioned_date(title) or mentioned_date(snippet),
            )
        )
    return found


def mentioned_date(text: str) -> date | None:
    """The first full date in a page's text, e.g. "From 20 Feb. through 26 Feb., 2026".

    Only dates with a year count: a bare "Joined January" or "Oct 3" says nothing about
    when a conference is.
    """
    month_day = _month_and_day(text)
    year = _YEAR.search(text)
    if not month_day or not year:
        return None
    return _safe_date(int(year.group(1)), *month_day)


def start_date(item: Mapping[str, Any], *, today: date) -> date | None:
    """Google gives "Nov 7" without a year; pick the year that makes the date upcoming."""
    raw = item.get("date")
    details = raw if isinstance(raw, Mapping) else {}
    texts = [clean_text(details.get("start_date")), clean_text(details.get("when"))]
    month_day = next((found for text in texts if (found := _month_and_day(text))), None)
    if not month_day:
        return None
    month, day = month_day
    year_match = next((m for text in texts if (m := _YEAR.search(text))), None)
    if year_match:
        return _safe_date(int(year_match.group(1)), month, day)
    this_year = _safe_date(today.year, month, day)
    if this_year and this_year < today - timedelta(days=RECENT_PAST_DAYS):
        return _safe_date(today.year + 1, month, day)
    return this_year


def clean_text(value: Any) -> str:
    return " ".join(str(value).split()) if value else ""


def _month_and_day(text: str) -> tuple[int, int] | None:
    for match in _MONTH_DAY.finditer(text):
        month = _MONTHS.get(match.group(1).lower())
        if month:
            return month, int(match.group(2))
    for match in _DAY_MONTH.finditer(text):
        month = _MONTHS.get(match.group(2).lower())
        if month:
            return month, int(match.group(1))
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _when(item: Mapping[str, Any]) -> str:
    raw = item.get("date")
    if isinstance(raw, Mapping):
        return clean_text(raw.get("when") or raw.get("start_date"))
    return clean_text(raw)


def _time(when: str) -> str:
    match = _TIME.search(when)
    return match.group(0).upper() if match else ""


def _place(item: Mapping[str, Any]) -> str:
    address = item.get("address")
    parts = [clean_text(part) for part in address] if isinstance(address, list) else []
    venue = item.get("venue")
    venue_name = clean_text(venue.get("name")) if isinstance(venue, Mapping) else ""
    if venue_name and not any(venue_name.lower() in part.lower() for part in parts):
        parts.insert(0, venue_name)
    return ", ".join(part for part in parts if part)


def _items(payload: Mapping[str, Any], key: str) -> Iterator[Mapping[str, Any]]:
    value = payload.get(key)
    if isinstance(value, list):
        yield from (item for item in value if isinstance(item, Mapping))


def _link(item: Mapping[str, Any]) -> str:
    link = item.get("link")
    return link.strip() if isinstance(link, str) else ""
