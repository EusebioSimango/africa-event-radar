import asyncio

from conftest import TODAY
from eventradar.budget import BudgetedSearch
from eventradar.models import Country
from eventradar.radar import build_radar
from eventradar.render import render_markdown

TITLE = "Python conferences and communities near Mozambique"


def render(backend, query, **kwargs):
    search = BudgetedSearch(backend, max_searches=8)
    radar = asyncio.run(build_radar(TITLE, query, search, today=TODAY, **kwargs))
    return render_markdown(radar)


def headings(text):
    return [line for line in text.splitlines() if line.startswith("#")]


def test_header_and_summary(backend, query):
    text = render(backend, query)

    assert text.startswith(f"# {TITLE}\n")
    assert "**Countries:** Mozambique, South Africa, Namibia · **Radar date:** 20 Oct 2026" in text
    assert "> 8 community pages, from 3 SerpApi searches." in text


def test_communities_by_country_without_event_sections(backend, query):
    assert headings(render(backend, query)) == [
        f"# {TITLE}",
        "## Python conferences and communities",
        "### Mozambique",
        "### Namibia",
        "### Searches used",
    ]


def test_conference_dates_are_shown_next_to_the_link(backend, query):
    text = render(backend, query)

    assert (
        "1. **[PyCon Namibia 2027, 26 February – 4 March 2027, Windhoek ...]"
        "(https://na.pycon.org/2027/)** — 26 Feb 2027 · na.pycon.org"
    ) in text
    assert "3. **[PyCon Namibia | Windhoek - Facebook](https://www.facebook.com/PyConNA/)**" in text


def test_countries_without_pages_share_one_line(backend, query):
    assert "_No Python community pages found for: South Africa._" in render(backend, query)


def test_tech_events_sections_follow_the_communities(backend, events_query):
    text = render(backend, events_query)

    assert headings(text) == [
        f"# {TITLE}",
        "## Python conferences and communities",
        "### Mozambique",
        "## Python events in Google's event listings",
        "## Tech events by country",
        "### South Africa",
        "### Searches used",
    ]
    assert "**Events:** any time" in text
    assert "> 2 community pages, 1 Python event and 4 tech events" in text


def test_event_lines_show_date_time_type_and_place(backend, events_query):
    text = render(backend, events_query)

    assert (
        "2. **[DevFest Example City](https://devfest.example.com/)** — Sat 21 Nov 2026, "
        "8:30 AM · Technology conference · The Example Hall, Sandton, South Africa"
    ) in text
    assert "4. **Mystery Tech Gathering** — Pretoria, South Africa" in text
    assert (
        "1. **[PyData Example Meetup](https://meetup.example.com/pydata)** — Wed 28 Oct 2026, "
        "6:00 PM · Meetup · Example Hub, Johannesburg, South Africa"
    ) in text
    assert "_No tech events listed on Google Events for: Mozambique._" in text


def test_failed_web_search_is_shown_under_its_country(backend, query):
    backend.responses["google_light:na"] = {"error": "Invalid API key."}

    assert "### Namibia\n\n_Web search failed: Invalid API key._" in render(backend, query)


def test_skipped_countries_are_named(backend, query):
    text = render(backend, query, skipped=[Country("Eswatini", "sz")])

    assert "Not searched, to stay within the search budget: Eswatini." in text


def test_footer_lists_searches(backend, query):
    text = render(backend, query)

    assert (
        '| Namibia | Google Light | `(PyCon OR PyData OR "Python meetup" OR "Django Girls" OR '
        "PyLadies) (Namibia)` | 7 |"
    ) in text
    assert "2 web results hidden (no Python words, or not about the country searched)." in text
