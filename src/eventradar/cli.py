"""Command line entry point: ``eventradar near mozambique`` or ``eventradar countries Kenya``."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape

from eventradar.budget import ResponseCache, default_cache_dir
from eventradar.mcp_search import McpSearchBackend, SearchFailed
from eventradar.models import Country, Radar
from eventradar.queries import WHEN_FILTERS, RadarQuery
from eventradar.radar import collect, fit_to_budget, radar_title
from eventradar.regions import UnknownCountry, country_and_neighbours, find_country
from eventradar.render import render_markdown

DEFAULT_MAX_SEARCHES = 8
EXIT_ALL_SEARCHES_FAILED = 1
EXIT_MISSING_API_KEY = 2

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Find Python conferences, communities and events in a country and its neighbours.",
)
console = Console()
status_console = Console(stderr=True)

Topic = Annotated[
    str,
    typer.Option(
        "--topic", "-t", help="Python community term to highlight, e.g. PyData or Django."
    ),
]
TechEvents = Annotated[
    bool,
    typer.Option(
        "--tech-events",
        help="Also search Google Events in each country (one more search per country).",
    ),
]
When = Annotated[
    str,
    typer.Option(help=f"Date filter for --tech-events: {', '.join(WHEN_FILTERS)}."),
]
MaxSearches = Annotated[
    int,
    typer.Option(min=1, max=20, help="Most SerpApi searches to spend in this run."),
]
NoCache = Annotated[
    bool, typer.Option("--no-cache", help="Ignore answers saved in the last 12 hours.")
]
Output = Annotated[Path | None, typer.Option("--output", "-o", help="Save the radar to this file.")]
AsJson = Annotated[bool, typer.Option("--json", help="Output JSON instead of Markdown.")]


@app.command()
def near(
    country: Annotated[str, typer.Argument(help='Your country, e.g. "mozambique".')],
    topic: Topic = "Python",
    tech_events: TechEvents = False,
    when: When = "any",
    max_searches: MaxSearches = DEFAULT_MAX_SEARCHES,
    no_cache: NoCache = False,
    output: Output = None,
    as_json: AsJson = False,
) -> None:
    """Conferences and communities in COUNTRY and in every country that borders it."""
    try:
        places = country_and_neighbours(country)
    except UnknownCountry as exc:
        raise typer.BadParameter(str(exc), param_hint="COUNTRY") from None
    run(
        radar_title(topic, [places[0].name], near=True),
        places,
        topic=topic,
        tech_events=tech_events,
        when=when,
        max_searches=max_searches,
        use_cache=not no_cache,
        output=output,
        as_json=as_json,
    )


@app.command()
def countries(
    names: Annotated[list[str], typer.Argument(help='Countries, e.g. "South Africa" Kenya.')],
    topic: Topic = "Python",
    tech_events: TechEvents = False,
    when: When = "any",
    max_searches: MaxSearches = DEFAULT_MAX_SEARCHES,
    no_cache: NoCache = False,
    output: Output = None,
    as_json: AsJson = False,
) -> None:
    """Conferences and communities in the countries you name, in any part of Africa."""
    try:
        places = list(dict.fromkeys(find_country(name) for name in names))
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="NAMES") from None
    run(
        radar_title(topic, [place.name for place in places]),
        places,
        topic=topic,
        tech_events=tech_events,
        when=when,
        max_searches=max_searches,
        use_cache=not no_cache,
        output=output,
        as_json=as_json,
    )


def run(
    title: str,
    places: list[Country],
    *,
    topic: str,
    tech_events: bool,
    when: str,
    max_searches: int,
    use_cache: bool,
    output: Path | None,
    as_json: bool,
) -> None:
    per_country = 2 if tech_events else 1
    searched, skipped = fit_to_budget(places, max_searches, searches_per_country=per_country)
    try:
        query = RadarQuery(tuple(searched), topic=topic, when=when, tech_events=tech_events)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None

    api_key = load_api_key()
    status_console.print(f"[dim]{_cost_note(len(searched), tech_events)}[/dim]")
    cache = ResponseCache(default_cache_dir()) if use_cache else None
    try:
        with status_console.status("Searching through SerpApi's MCP server..."):
            radar, searches_made = asyncio.run(
                collect(
                    title,
                    query,
                    McpSearchBackend(api_key),
                    max_searches=max_searches,
                    cache=cache,
                    skipped=skipped,
                )
            )
    except SearchFailed as exc:
        fail(f"{exc} Check your internet connection and SERPAPI_API_KEY.")
    except Exception as exc:
        if os.getenv("EVENTRADAR_DEBUG"):
            raise
        fail(f"Unexpected error ({type(exc).__name__}). Run with EVENTRADAR_DEBUG=1 for details.")

    write_output(radar, output=output, as_json=as_json)
    status_console.print(f"[dim]SerpApi searches made: {searches_made}[/dim]")
    if radar.all_searches_failed:
        raise typer.Exit(code=EXIT_ALL_SEARCHES_FAILED)


def _cost_note(country_count: int, tech_events: bool) -> str:
    countries = f"{country_count} {'country' if country_count == 1 else 'countries'}"
    per_country = "2 searches (web + Google Events)" if tech_events else "1 web search"
    total = country_count * (2 if tech_events else 1)
    return (
        f"Up to {total} SerpApi searches: {countries} x {per_country}. "
        "Answers from the last 12 hours are reused for free."
    )


def fail(message: str) -> NoReturn:
    status_console.print(f"[red]Error:[/red] {escape(message)}")
    raise typer.Exit(code=EXIT_ALL_SEARCHES_FAILED)


def load_api_key() -> str:
    load_dotenv(find_dotenv(usecwd=True))
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
    if not api_key:
        status_console.print(
            "[red]Missing SERPAPI_API_KEY.[/red] Copy .env.example to .env and add your key "
            "from https://serpapi.com/manage-api-key"
        )
        raise typer.Exit(code=EXIT_MISSING_API_KEY)
    return api_key


def write_output(radar: Radar, *, output: Path | None, as_json: bool) -> None:
    text = (
        json.dumps(radar.to_dict(), indent=2, ensure_ascii=False, default=str) + "\n"
        if as_json
        else render_markdown(radar)
    )
    if output:
        output.write_text(text, encoding="utf-8")
        status_console.print(f"Saved radar to [bold]{output}[/bold]")
    elif as_json or not console.is_terminal:
        print(text, end="")
    else:
        console.print(Markdown(text))


if __name__ == "__main__":
    app()
