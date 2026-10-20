"""Public web demo: pick a country, get its radar, with limits that protect the SerpApi budget.

Run locally with ``uv run --extra web uvicorn eventradar.web:app --reload``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from html import escape
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from markdown_it import MarkdownIt

from eventradar.budget import ResponseCache
from eventradar.limits import DemoLimits, LimitReached, RadarCache
from eventradar.mcp_search import McpSearchBackend, SearchFailed
from eventradar.queries import RadarQuery
from eventradar.radar import collect, radar_title
from eventradar.regions import COUNTRY_CODES, country_and_neighbours, find_country
from eventradar.render import render_markdown

MAX_SEARCHES_PER_RADAR = 8
DEFAULT_DAILY_SEARCHES = 40
RADARS_PER_VISITOR_PER_HOUR = 3
DEFAULT_COUNTRY = "Mozambique"

REPO_URL = "https://github.com/EusebioSimango/africa-event-radar"
SAMPLE_RADAR = Path(__file__).resolve().parents[2] / "examples" / "sample-radar.md"

# Raw HTML in search results is shown as text, never rendered.
_markdown = MarkdownIt("commonmark", {"html": False}).enable("table")


class DemoNotConfigured(RuntimeError):
    """The server has no SerpApi key."""


def create_app(
    backend_factory: Callable[[], McpSearchBackend] | None = None,
    *,
    daily_searches: int | None = None,
    cache_dir: Path | None = None,
) -> FastAPI:
    limits = DemoLimits(
        daily_searches=daily_searches or _daily_searches_from_env(),
        radars_per_visitor_per_hour=RADARS_PER_VISITOR_PER_HOUR,
    )
    radars = RadarCache()
    answers = ResponseCache(cache_dir or Path(tempfile.gettempdir()) / "eventradar-demo")
    make_backend = backend_factory or _backend_from_env
    app = FastAPI(title="Africa Event Radar", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return _page("Africa Event Radar", _intro() + _form())

    @app.get("/radar", response_class=HTMLResponse)
    async def radar(request: Request, country: str = "", neighbours: str = "") -> HTMLResponse:
        with_neighbours = neighbours == "on"
        form = _form(country, with_neighbours)
        if country not in COUNTRY_CODES:
            return _message_page(400, "Please pick a country from the list.", form)

        places = (country_and_neighbours(country) if with_neighbours else [find_country(country)])[
            :MAX_SEARCHES_PER_RADAR
        ]
        key = f"{country}|{with_neighbours}"
        markdown = radars.get(key)
        if markdown is None:
            query = RadarQuery(tuple(places))
            new_searches = sum(
                answers.get(query.community_params(place)) is None for place in places
            )
            try:
                backend = make_backend()
                if new_searches:
                    limits.reserve(_visitor_ip(request), new_searches)
            except DemoNotConfigured:
                return _message_page(503, "The demo is not configured yet.", form)
            except LimitReached as exc:
                return _message_page(429, str(exc), form)
            title = radar_title(query.topic, [places[0].name], near=with_neighbours)
            try:
                result, _ = await collect(
                    title,
                    query,
                    backend,
                    max_searches=MAX_SEARCHES_PER_RADAR,
                    cache=answers,
                    skipped=[],
                )
            except SearchFailed:
                return _message_page(502, "Could not reach SerpApi. Please try again.", form)
            markdown = render_markdown(result)
            if not result.all_searches_failed:
                radars.put(key, markdown)
        return HTMLResponse(_page(places[0].name, form + _radar_html(markdown)))

    @app.get("/example", response_class=HTMLResponse)
    def example() -> HTMLResponse:
        if not SAMPLE_RADAR.is_file():
            return _message_page(404, "The sample radar is not available.", _form())
        markdown = SAMPLE_RADAR.read_text(encoding="utf-8")
        return HTMLResponse(_page("Sample radar", _form() + _radar_html(markdown)))

    @app.get("/healthz", response_class=PlainTextResponse)
    def healthz() -> str:
        return "ok"

    return app


def _backend_from_env() -> McpSearchBackend:
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
    if not api_key:
        raise DemoNotConfigured
    return McpSearchBackend(api_key)


def _daily_searches_from_env() -> int:
    value = os.getenv("DEMO_DAILY_SEARCHES", "")
    return int(value) if value.isdigit() and int(value) > 0 else DEFAULT_DAILY_SEARCHES


def _visitor_ip(request: Request) -> str:
    # Render puts the client IP first in X-Forwarded-For. A visitor can spoof it, which is
    # why the daily cap, not this per-visitor cap, is what bounds the credits spent.
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _radar_html(markdown: str) -> str:
    return f'<article class="radar">{_markdown.render(markdown)}</article>'


def _message_page(status_code: int, message: str, form: str) -> HTMLResponse:
    notice = f'<p class="notice">{escape(message)}</p>'
    return HTMLResponse(_page("Africa Event Radar", form + notice), status_code=status_code)


def _intro() -> str:
    return (
        "<p>Find Python conferences and communities in an African country and the countries "
        "around it: PyCons, PyData, Django Girls, PyLadies and meetups, with a link for every "
        "item. Each country costs one SerpApi search, and answers are reused for 12 hours.</p>"
        '<p><a href="/example">See a sample radar</a> (no searches needed).</p>'
    )


def _form(country: str = DEFAULT_COUNTRY, with_neighbours: bool = True) -> str:
    options = "\n".join(
        f'<option value="{escape(name)}"{" selected" if name == country else ""}>'
        f"{escape(name)}</option>"
        for name in sorted(COUNTRY_CODES)
    )
    checked = " checked" if with_neighbours else ""
    return f"""
<form action="/radar" method="get">
  <label>Country
    <select name="country">{options}</select>
  </label>
  <label class="inline"><input type="checkbox" name="neighbours"{checked}>
    Include the countries that border it
  </label>
  <button type="submit">Show radar</button>
</form>"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · Africa Event Radar</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 46rem; margin: 2rem auto;
         padding: 0 1rem; line-height: 1.5; color: #1f2328; }}
  header a {{ color: inherit; text-decoration: none; }}
  form {{ display: grid; gap: .75rem; margin: 1.5rem 0; }}
  label {{ display: grid; gap: .25rem; font-weight: 600; }}
  label.inline {{ display: flex; gap: .5rem; align-items: center; font-weight: 400; }}
  select {{ font: inherit; padding: .5rem; border: 1px solid #c9ced6; border-radius: 6px; }}
  button {{ font: inherit; padding: .6rem; border: 0; border-radius: 6px;
           background: #1f6feb; color: white; cursor: pointer; }}
  .notice {{ padding: .75rem 1rem; border-radius: 6px; background: #fff4e5; }}
  .radar {{ border-top: 1px solid #d0d7de; margin-top: 1.5rem; }}
  .radar blockquote {{ margin: .25rem 0 .75rem; color: #57606a; }}
  .radar table {{ border-collapse: collapse; font-size: .9rem; }}
  .radar th, .radar td {{ border: 1px solid #d0d7de; padding: .3rem .5rem; }}
  footer {{ margin-top: 3rem; font-size: .85rem; color: #57606a; }}
</style>
</head>
<body>
<header><h1><a href="/">Africa Event Radar</a></h1></header>
{body}
<footer>
  <p>Results come from SerpApi, through its MCP server; links go to third-party sites. This
  demo makes at most {RADARS_PER_VISITOR_PER_HOUR} new radars per visitor per hour and has a
  small daily limit. Searches and IP addresses are not logged.</p>
  <p><a href="{REPO_URL}">Source code and CLI</a>: run it with your own free SerpApi key,
  with tech events from Google Events too.</p>
</footer>
</body>
</html>"""


app = create_app()
