import asyncio
from datetime import date

import pytest

from conftest import NAMIBIA, TODAY
from eventradar.budget import BudgetedSearch
from eventradar.mcp_search import SearchFailed
from eventradar.models import Country, Link
from eventradar.radar import build_radar, fit_to_budget, is_about_country, radar_title


def radar_for(backend, query, *, max_searches=8):
    search = BudgetedSearch(backend, max_searches=max_searches)
    return asyncio.run(build_radar("Radar", query, search, today=TODAY))


def test_one_web_search_per_country_and_no_events_by_default(backend, query):
    radar = radar_for(backend, query)

    assert [(r["engine"], r["q"]) for r in backend.requests] == [
        (
            "google_light",
            '(PyCon OR PyData OR "Python meetup" OR "Django Girls" OR PyLadies) (Mozambique)',
        ),
        (
            "google_light",
            '(PyCon OR PyData OR "Python meetup" OR "Django Girls" OR PyLadies) ("South Africa")',
        ),
        (
            "google_light",
            '(PyCon OR PyData OR "Python meetup" OR "Django Girls" OR PyLadies) (Namibia)',
        ),
    ]
    assert radar.tech_events == {}
    assert not radar.with_tech_events


def test_community_pages_need_python_words_and_the_country(backend, query):
    radar = radar_for(backend, query)

    assert [link.domain for link in radar.communities["Mozambique"]] == [
        "python.example.mz",
        "pydata.example.org",
    ]
    assert radar.hidden_off_topic == 2  # a travel guide, and a pan-African page


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        (Link("PyCon Namibia 2027", "https://example.org/"), True),
        (Link("Django Girls Windhoek #6", "https://djangogirls.org/windhoek/"), True),
        (Link("Call for proposals", "https://na.pycon.org/2027/cfp/"), True),
        (Link("Python courses", "https://school.example.na/"), True),
        (Link("Django Girls PyCon US #3", "https://djangogirls.org/pycon/"), False),
        (Link("PyLadiesCon 2025", "https://conference.pyladies.com/"), False),
    ],
)
def test_is_about_country(link, expected):
    assert is_about_country(link, NAMIBIA) is expected


def test_upcoming_conferences_come_first_and_past_ones_last(backend, query):
    namibia = radar_for(backend, query).communities["Namibia"]

    assert [link.domain for link in namibia] == [
        "na.pycon.org",
        "pretix.eu",
        "facebook.com",
        "x.com",
        "djangogirls.org",
        "pythonnamibia.org",
    ]
    assert namibia[0].starts_on == date(2027, 2, 26)
    assert namibia[1].starts_on == date(2027, 2, 26)
    assert namibia[2].starts_on is None


def test_country_without_results_is_empty_not_failed(backend, query):
    radar = radar_for(backend, query)

    assert radar.communities["South Africa"] == []
    assert radar.searches[1].error is None


def test_a_page_is_listed_once_across_countries(backend, query):
    backend.responses["google_light:za"] = backend.responses["google_light:mz"]

    radar = radar_for(backend, query)

    assert radar.communities["South Africa"] == []
    assert radar.communities["Mozambique"]


def test_tech_events_are_opt_in_upcoming_sorted_and_one_per_title(backend, events_query):
    radar = radar_for(backend, events_query)
    sa = radar.tech_events["South Africa"]

    assert radar.with_tech_events
    assert [e.title for e in sa] == [
        "Africa Tech Example",
        "DevFest Example City",
        "TechCon Example",
        "Mystery Tech Gathering",
    ]
    assert sa[0].starts_on == date(2026, 11, 16)
    assert sa[2].starts_on == date(2027, 3, 3)
    assert radar.tech_events["Mozambique"] == []


def test_python_events_are_highlighted_and_kept_out_of_tech_events(backend, events_query):
    radar = radar_for(backend, events_query)

    assert [e.title for e in radar.python_events] == ["PyData Example Meetup"]
    assert "PyData Example Meetup" not in [e.title for e in radar.tech_events["South Africa"]]


def test_tech_events_search_after_the_web_searches(backend, events_query):
    radar = radar_for(backend, events_query)

    assert [(r.label, r.engine) for r in radar.searches] == [
        ("Mozambique", "Google Light"),
        ("South Africa", "Google Light"),
        ("Mozambique", "Google Events"),
        ("South Africa", "Google Events"),
    ]


def test_one_failed_search_does_not_stop_the_others(backend, query):
    backend.responses["google_light:mz"] = SearchFailed(
        "SerpApi MCP request failed (ConnectError)."
    )
    radar = radar_for(backend, query)

    assert radar.searches[0].error == "SerpApi MCP request failed (ConnectError)."
    assert radar.communities["Namibia"]
    assert not radar.all_searches_failed


def test_fit_to_budget_counts_searches_per_country():
    places = [Country(name) for name in "ABCDE"]

    assert [c.name for c in fit_to_budget(places, 3)[0]] == ["A", "B", "C"]
    kept, skipped = fit_to_budget(places, 5, searches_per_country=2)
    assert [c.name for c in kept] == ["A", "B"]
    assert [c.name for c in skipped] == ["C", "D", "E"]


def test_radar_titles():
    assert radar_title("Python", ["Namibia"], near=True) == (
        "Python conferences and communities near Namibia"
    )
    assert radar_title("PyData", ["Kenya", "Ghana", "Nigeria"]) == (
        "PyData conferences and communities in Kenya, Ghana and Nigeria"
    )
