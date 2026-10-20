from datetime import date

import pytest

from conftest import TODAY, load_fixture
from eventradar import parsing


def za_events():
    return parsing.events(load_fixture("google_events_za"), "South Africa", today=TODAY)


def test_events_read_the_compact_shape():
    devfest = za_events()[2]

    assert devfest.title == "DevFest Example City"
    assert devfest.starts_on == date(2026, 11, 21)
    assert devfest.time == "8:30 AM"
    assert devfest.kind == "Technology conference"
    assert devfest.place == "The Example Hall, Sandton, South Africa"
    assert devfest.country == "South Africa"


def test_event_link_prefers_info_pages_then_tickets_then_the_map():
    links = [event.link for event in za_events()]

    assert links[2] == "https://devfest.example.com/"
    assert links[0] == "https://tickets.example.com/africa-tech"
    assert links[5] == "https://maps.google.com/?cid=222"
    assert links[6] == ""


def test_an_event_page_link_wins_when_google_has_one():
    item = {"link": "https://event.example.com", "ticket_info": [{"link": "https://t.example"}]}

    assert parsing.event_link(item) == "https://event.example.com"


@pytest.mark.parametrize(
    ("date_field", "expected"),
    [
        ({"start_date": "Nov 7"}, date(2026, 11, 7)),
        ({"start_date": "Jan 16"}, date(2027, 1, 16)),
        ({"start_date": "Oct 1"}, date(2026, 10, 1)),
        ({"when": "Sat, 7 November 2026"}, date(2026, 11, 7)),
        ({"start_date": "Sept 3", "when": "Thu, Sep 3, 2027"}, date(2027, 9, 3)),
        ({"start_date": "soon"}, None),
        ({"start_date": "Feb 30"}, None),
    ],
)
def test_start_date_picks_the_upcoming_year(date_field, expected):
    assert parsing.start_date({"date": date_field}, today=TODAY) == expected


def test_venue_is_not_repeated_when_already_in_the_address():
    item = {"address": ["Hall A, Maputo"], "venue": {"name": "Hall A"}}

    assert parsing._place(item) == "Hall A, Maputo"


def test_links_read_organic_results():
    links = parsing.links(load_fixture("google_light_communities"))

    assert links[0].domain == "pyconafrica.example.org"
    assert links[1].snippet == "Meetups and workshops in Maputo."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("PyCon Namibia 2027, 26 February – 4 March 2027, Windhoek", date(2027, 2, 26)),
        ("February 26th - March 4th, 2027 - Windhoek, Namibia.", date(2027, 2, 26)),
        ("PyCon Namibia 2026 · From 20 Feb. through 26 Feb. , 2026", date(2026, 2, 20)),
        ("South Africa's Python conference — Cape Town. 14–18 October 2026.", date(2026, 10, 18)),
        ("Windhoek, Namibia. Joined January 2021 · 23. Following.", None),
        ("Meetups every Oct 3 in Maputo.", None),
        ("PyConZA 2022 · Past PyConZAs · Videos.", None),
    ],
)
def test_mentioned_date_needs_a_day_month_and_year(text, expected):
    assert parsing.mentioned_date(text) == expected


def test_links_take_their_date_from_the_title_or_snippet():
    links = parsing.links(load_fixture("google_light_namibia"))

    assert links[0].starts_on == date(2027, 2, 26)
    assert links[2].starts_on == date(2026, 2, 20)
    assert links[1].starts_on is None


def test_unexpected_shapes_are_ignored():
    assert parsing.events({"events_results": "oops"}, "X", today=TODAY) == []
    assert parsing.links({"organic_results": [None, 3]}) == []
    assert parsing.event_link({"ticket_info": "oops", "event_location_map": None}) == ""
