# Africa Event Radar

[![Live Demo](https://img.shields.io/badge/Live_Demo-africa--event--radar.onrender.com-2ea44f?style=flat-square&logo=fastapi)](https://africa-event-radar.onrender.com)
[![Tests](https://img.shields.io/github/actions/workflow/status/EusebioSimango/africa-event-radar/tests.yml?branch=main&style=flat-square&label=tests)](https://github.com/EusebioSimango/africa-event-radar/actions/workflows/tests.yml)
[![Hackathon](https://img.shields.io/badge/SerpApi-PyCon_ZA_2026-blue?style=flat-square)](https://serpapi.com/pyconzahackathon)
[![SerpApi MCP](https://img.shields.io/badge/SerpApi-MCP_server-8A2BE2?style=flat-square)](https://github.com/serpapi/serpapi-mcp)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json&style=flat-square)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

Find Python conferences and communities in your country and the countries around it, in one command.

```bash
eventradar near namibia
```

Built for the [SerpApi PyCon ZA 2026 Hackathon](https://serpapi.com/pyconzahackathon).

## Why this exists

As the lead of Python Mozambique, I keep getting the same question from my manager: *"Which Python conferences are coming up in the neighbouring countries, like South Africa, so we can connect with them?"* Answering it means an evening of searching country by country, in conference sites, meetup pages and social media.

Travellers have the same problem. Someone who flies to a PyCon in Africa often wants to visit nearby communities while they are on the continent, but there is no single place to look.

Africa Event Radar answers both questions in one command. Give it your country, and it searches that country and every country that borders it. It returns one Markdown page with the PyCons, PyData chapters, Django Girls workshops, PyLadies chapters and meetups it finds, upcoming conferences first, with a link for each.

## What you get

`eventradar near namibia` gives this (the full page is in [`examples/sample-radar.md`](examples/sample-radar.md)):

```markdown
### Namibia

1. PyCon Namibia 2027, 26 February – 4 March 2027, Windhoek — 26 Feb 2027 · na.pycon.org
2. PyCon Namibia 2027 - pretix — 26 Feb 2027 · pretix.eu
3. PyCon Namibia | Windhoek - Facebook — facebook.com
4. PyLadies Namibia (@PyladiesNamibia) / X — x.com
5. Django Girls Windhoek #6 — djangogirls.org
6. Python · Namibia — pythonnamibia.org

### South Africa

1. PyData Johannesburg - Meetup — meetup.com
...
6. PyConZA 2026 — past: 18 Oct 2026 · za.pycon.org

_No Python community pages found for: Angola, Zambia, Botswana._
```

| Section | What is in it |
| --- | --- |
| **Python conferences and communities** | Up to 6 pages per country: conference sites, ticket pages, meetup groups and community accounts. Upcoming conferences come first, by date; then undated pages in Google's order; then past ones, marked "past". |
| **Python events / Tech events by country** | Only with `--tech-events`: dated events from Google Events, Python ones first. See [`examples/sample-radar-tech-events.md`](examples/sample-radar-tech-events.md). |
| **Searches used** | Every search sent, its engine, and how many results came back. |

Every item comes from a live search; the radar never writes a page or event that a search did not return. A country with nothing to show says so, in one line, instead of padding it with pages from elsewhere.

### Why web search, not an events listing

The first version used [Google Events](https://serpapi.com/google-events-api) for each country. It answered for South Africa (17 events), but for Mozambique, Namibia and most of the region Google returned no events at all, even while PyCon Namibia had dates and a ticket page online. Python communities in Africa publish on their own sites, on pretix or Quicket, and on Meetup or social media, which the events panel rarely picks up.

So the main search is now a web search per country for the Python community brands: `(PyCon OR PyData OR "Python meetup" OR "Django Girls" OR PyLadies) (Namibia)`. Google Events is still there for big tech events, behind `--tech-events`.

### How it keeps results relevant

1. **About Python**: a page must mention Python, PyCon, PyData, Django, Flask, FastAPI, Jupyter, PyLadies or pandas (or your `--topic`) in its title, snippet or link.
2. **About the country**: a page must name the country or one of its main cities (such as Windhoek or Maputo), or sit on the country's domain (`.na`, `na.pycon.org`). Without this, a country with few pages gets filled with PyCon US and global results.
3. **Once per radar**: a page found for one country is not repeated under the next.
4. **Dates from the text**: dates such as "26 February – 4 March 2027" or "February 26th, 2027" are read from the title or snippet, and only count when they include a year.

The footer says how many results were hidden by the first two rules.

## How it uses SerpApi

The radar talks to SerpApi through the **[SerpApi MCP server](https://github.com/serpapi/serpapi-mcp)**, the hosted one at `https://mcp.serpapi.com/mcp`. It is a plain MCP client built with the official [`mcp`](https://pypi.org/project/mcp/) Python SDK: no LLM is involved, and there are no direct requests to serpapi.com.

| Search | Through the MCP `search` tool | Per run |
| --- | --- | --- |
| `(PyCon OR PyData OR "Python meetup" OR "Django Girls" OR PyLadies) ({country})`, with the country's `gl` code | `engine: google_light` | one per country |
| `tech events in {country}`, with the country's `gl` code and an optional date filter (`htichips`) | `engine: google_events` | one per country, only with `--tech-events` |

How it fits together, in [`mcp_search.py`](src/eventradar/mcp_search.py):

- One MCP session is opened over Streamable HTTP and shared by all searches, which run in parallel with `asyncio`.
- Each search calls the server's `search` tool with `{"params": {...}, "mode": "compact"}` and reads the JSON from `structuredContent.result`. A result with `isError` becomes a short message in the radar.
- The API key goes in the `Authorization: Bearer` header, not in the URL path, because SerpApi notes that a key in the path can appear in request logs. The key is never printed.

Searches cost credits, so the radar is careful with them:

- **Budget:** at most 8 searches per run by default (`--max-searches`, up to 20). `near mozambique` uses 7: Mozambique and its 6 neighbours. With `--tech-events` each country costs 2, so the same budget covers 4 countries. Countries that do not fit are skipped, and the radar says which.
- **Cache:** answers are saved in `~/.cache/eventradar` for 12 hours, so running the same radar again costs nothing, and neighbouring radars share countries. Use `--no-cache` to search again.
- **Cost up front:** the command prints how many searches it may spend before it starts, and how many it made at the end.

## Run it

You need Python 3.10 or newer, [uv](https://docs.astral.sh/uv/getting-started/installation/) and a free [SerpApi API key](https://serpapi.com/users/sign_up) (250 searches a month).

```bash
git clone https://github.com/EusebioSimango/africa-event-radar.git
cd africa-event-radar
uv sync
cp .env.example .env   # then paste your key after SERPAPI_API_KEY=
```

Try it:

```bash
# Your country and its neighbours (one search per country)
uv run eventradar near mozambique

# One country, with tech events from Google Events, saved as Markdown
uv run eventradar countries "South Africa" --tech-events --when next_month -o radar-za.md

# Countries you choose, anywhere in Africa, with another topic
uv run eventradar countries Kenya Nigeria Ghana --topic PyData

# Structured output for other tools
uv run eventradar near kenya --json
```

`near` knows 16 countries in Southern, Central and East Africa, their land neighbours and their main cities (see [`regions.py`](src/eventradar/regions.py)). `countries` accepts any country name. `--when` (`any`, `week`, `next_week`, `month`, `next_month`) filters `--tech-events`. `--topic` (Python by default) is a Python community term, such as PyData or Django, that the radar adds to the search. Run `uv run eventradar --help` for every option. The command exits with code `1` if every search failed and `2` if the API key is missing or an argument is invalid.

## Web demo

The same radar as a small web page: pick a country, tick "include the countries that border it", and get the radar, with a link for every item. A [sample radar](https://africa-event-radar.onrender.com/example) needs no searches.

Run it locally:

```bash
uv sync --extra web
uv run uvicorn eventradar.web:app --reload   # http://127.0.0.1:8000
```

The demo runs on a shared SerpApi key, so it protects that key's free plan:

- **Cache:** answers are kept for 12 hours, per country, so a visitor who opens Namibia after someone opened South Africa only pays for the countries not already searched.
- **Limits:** at most 40 searches a day for the whole demo (`DEMO_DAILY_SEARCHES`) and 3 new radars per visitor per hour. Visitors are counted by a salted hash of their IP, kept only in memory.
- **No logs:** the server runs with `--no-access-log`, so searches and IP addresses are not written anywhere. Search results are rendered with raw HTML turned off.
- **Web search only:** `--tech-events` stays in the CLI, to keep each radar to one search per country.

To deploy your own copy on [Render](https://render.com), choose **New > Blueprint**, pick this repository ([`render.yaml`](render.yaml) describes the service) and set `SERPAPI_API_KEY`.

## Project layout

| Module | Responsibility |
| --- | --- |
| [`cli.py`](src/eventradar/cli.py) | The `near` and `countries` commands, API key loading, writing the output. |
| [`web.py`](src/eventradar/web.py) | The FastAPI web demo. |
| [`limits.py`](src/eventradar/limits.py) | The web demo's cache and rate limits. |
| [`regions.py`](src/eventradar/regions.py) | Known countries, their Google country codes, cities and neighbours. |
| [`queries.py`](src/eventradar/queries.py) | `RadarQuery`: the parameters of each search. |
| [`mcp_search.py`](src/eventradar/mcp_search.py) | `McpSearchBackend`: the MCP client for SerpApi's `search` tool. |
| [`budget.py`](src/eventradar/budget.py) | The per-run search budget and the 12-hour cache. |
| [`parsing.py`](src/eventradar/parsing.py) | Turns SerpApi JSON into `Event` and `Link` items, including dates. Pure functions. |
| [`radar.py`](src/eventradar/radar.py) | Runs the searches in parallel and applies the relevance rules. |
| [`render.py`](src/eventradar/render.py) | Writes the `Radar` as Markdown. |
| [`models.py`](src/eventradar/models.py) | The plain data classes shared by the modules above. |

## Tests

The tests replace the MCP server with a fake backend that returns saved responses in SerpApi's real shapes (one of them a real Namibia answer), so they spend no credits and need no key:

```bash
uv run pytest
```

There is one test file per module. They cover the neighbour map, the search parameters, dates read from event listings and from page text, the budget and the cache, reading MCP tool results (including errors that never show the key), the relevance rules, the Markdown output, the CLI end to end, and the web demo's limits, cache and HTML escaping. GitHub Actions runs them, with Ruff, on Python 3.10 and 3.13.

## What was added for the hackathon

Everything. Africa Event Radar is a new project, started on 20 October 2026 for the SerpApi PyCon ZA Hackathon.

## Credits

Built on these open source libraries, used as dependencies under their own licences. No code was copied from them.

- [`mcp`](https://github.com/modelcontextprotocol/python-sdk), the MCP Python SDK (MIT), and the hosted [SerpApi MCP server](https://github.com/serpapi/serpapi-mcp) (MIT)
- [httpx2](https://pypi.org/project/httpx2/) (BSD-3-Clause), [Typer](https://github.com/fastapi/typer) (MIT), [Rich](https://github.com/Textualize/rich) (MIT) and [python-dotenv](https://github.com/theskumar/python-dotenv) (BSD-3-Clause)
- For the web demo: [FastAPI](https://github.com/fastapi/fastapi) (MIT), [Uvicorn](https://github.com/encode/uvicorn) (BSD-3-Clause) and [markdown-it-py](https://github.com/executablebooks/markdown-it-py) (MIT)
- [pytest](https://github.com/pytest-dev/pytest) (MIT), [HTTPX](https://github.com/encode/httpx) (BSD-3-Clause) and [Ruff](https://github.com/astral-sh/ruff) (MIT), for the tests

## License

[MIT](LICENSE)
