"""Render a ``Radar`` as Markdown. Formatting only; no decisions about content."""

from __future__ import annotations

from datetime import date

from eventradar.models import Event, Link, Radar, SearchRecord

WHEN_LABELS = {
    "any": "any time",
    "week": "this week",
    "next_week": "next week",
    "month": "this month",
    "next_month": "next month",
}
MAX_SNIPPET_LENGTH = 160


def render_markdown(radar: Radar) -> str:
    blocks = [_header(radar), _communities(radar)]
    if radar.with_tech_events:
        blocks += [_python_events(radar), _tech_events(radar)]
    blocks.append(_footer(radar))
    return "\n\n".join(block for block in blocks if block).rstrip() + "\n"


def format_date(value: date) -> str:
    return f"{value.day} {value:%b %Y}"


def _header(radar: Radar) -> str:
    facts = [f"**Countries:** {', '.join(radar.countries)}"]
    if radar.with_tech_events:
        facts.append(f"**Events:** {WHEN_LABELS.get(radar.when, radar.when)}")
    facts.append(f"**Radar date:** {format_date(radar.radar_date)}")
    lines = [f"# {radar.title}", " · ".join(facts), f"> {_summary(radar)}"]
    if radar.skipped_countries:
        skipped = ", ".join(radar.skipped_countries)
        lines.append(
            f"_Not searched, to stay within the search budget: {skipped}."
            " Raise `--max-searches` to include them._"
        )
    return "\n\n".join(lines)


def _summary(radar: Radar) -> str:
    """One line such as "12 community pages, 2 Python events and 14 tech events, from 8 ..."."""
    counts = [
        _plural(radar.community_count, "community page") if radar.community_count else "",
        _plural(len(radar.python_events), f"{radar.topic} event") if radar.python_events else "",
        _plural(radar.tech_event_count, "tech event") if radar.tech_event_count else "",
    ]
    found = _join([count for count in counts if count]) or "Nothing found"
    searches = _plural(len(radar.searches), "SerpApi search", "SerpApi searches")
    return f"{found}, from {searches}."


def _communities(radar: Radar) -> str:
    blocks = [f"## {radar.topic} conferences and communities"]
    empty = []
    for country, links in radar.communities.items():
        record = _record_for(radar, country, "Google Light")
        if record and record.error:
            blocks.append(f"### {country}\n\n_Web search failed: {record.error}_")
        elif links:
            items = "\n".join(
                _link_item(i, link, radar.radar_date) for i, link in enumerate(links, start=1)
            )
            blocks.append(f"### {country}\n\n{items}")
        else:
            empty.append(country)
    if empty:
        blocks.append(f"_No {radar.topic} community pages found for: {', '.join(empty)}._")
    return "\n\n".join(blocks)


def _python_events(radar: Radar) -> str:
    title = f"## {radar.topic} events in Google's event listings"
    if not radar.python_events:
        return (
            f"{title}\n\n_None this time; the conferences and communities above are the best lead._"
        )
    items = "\n".join(
        f"{i}. {_event_line(event, with_country=True)}"
        for i, event in enumerate(radar.python_events, start=1)
    )
    return f"{title}\n\n{items}"


def _tech_events(radar: Radar) -> str:
    blocks = ["## Tech events by country"]
    empty = []
    for country, events in radar.tech_events.items():
        record = _record_for(radar, country, "Google Events")
        if record and record.error:
            blocks.append(f"### {country}\n\n_Google Events search failed: {record.error}_")
        elif events:
            items = "\n".join(f"{i}. {_event_line(e)}" for i, e in enumerate(events, start=1))
            blocks.append(f"### {country}\n\n{items}")
        else:
            empty.append(country)
    if empty:
        blocks.append(f"_No tech events listed on Google Events for: {', '.join(empty)}._")
    return "\n\n".join(blocks)


def _event_line(event: Event, *, with_country: bool = False) -> str:
    place = event.place
    if with_country and event.country.lower() not in place.lower():
        place = f"{place}, {event.country}" if place else event.country
    meta = " · ".join(part for part in (_event_date(event), event.kind, place) if part)
    title = _link_text(event.title)
    line = f"**[{title}]({event.link})**" if event.link else f"**{title}**"
    if meta:
        line += f" — {meta}"
    if event.description:
        line += f"\n   > {_shorten(event.description)}"
    return line


def _event_date(event: Event) -> str:
    if not event.starts_on:
        return event.when
    text = f"{event.starts_on:%a} {format_date(event.starts_on)}"
    return f"{text}, {event.time}" if event.time else text


def _link_item(index: int, link: Link, today: date) -> str:
    line = f"{index}. **[{_link_text(link.title)}]({link.link})**"
    meta = []
    if link.starts_on:
        when = format_date(link.starts_on)
        meta.append(when if link.starts_on >= today else f"past: {when}")
    if link.domain and link.domain.lower() not in link.title.lower():
        meta.append(link.domain)
    if meta:
        line += f" — {' · '.join(meta)}"
    if link.snippet:
        line += f"\n   > {_shorten(link.snippet)}"
    return line


def _footer(radar: Radar) -> str:
    rows = [
        "| For | Engine | Query | Results |",
        "| --- | --- | --- | --- |",
        *(_search_row(record) for record in radar.searches),
    ]
    notes = []
    if radar.hidden_off_topic:
        notes.append(
            f"{_plural(radar.hidden_off_topic, 'web result')} hidden "
            f"(no {radar.topic} words, or not about the country searched)."
        )
    notes.append(
        "Results come from SerpApi, through its MCP server. Check dates and venues on the "
        "event page before you travel."
    )
    return "\n\n".join(["---", "### Searches used", "\n".join(rows), f"_{' '.join(notes)}_"])


def _search_row(record: SearchRecord) -> str:
    query = record.query.replace("|", "\\|").replace("`", "'")
    if record.error:
        outcome = f"Failed: {record.error}"
    else:
        outcome = (
            f"{record.result_count} (cached)" if record.from_cache else str(record.result_count)
        )
    outcome = outcome.replace("|", "\\|")
    return f"| {record.label} | {record.engine} | `{query}` | {outcome} |"


def _record_for(radar: Radar, label: str, engine: str) -> SearchRecord | None:
    return next(
        (r for r in radar.searches if r.label == label and r.engine == engine),
        None,
    )


def _shorten(text: str) -> str:
    if len(text) <= MAX_SNIPPET_LENGTH:
        return text
    return text[: MAX_SNIPPET_LENGTH - 1].rsplit(" ", 1)[0] + " …"


def _join(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _link_text(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]")


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"
