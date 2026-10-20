import pytest

from eventradar.models import Country
from eventradar.queries import RadarQuery

SA = Country("South Africa", "za")
NIGERIA = Country("Nigeria")


def test_event_params_use_country_code_and_date_filter():
    params = RadarQuery((SA,), when="next_month").event_params(SA)

    assert params == {
        "engine": "google_events",
        "q": "tech events in South Africa",
        "hl": "en",
        "gl": "za",
        "htichips": "date:next_month",
    }


def test_event_params_without_country_code_or_filter():
    params = RadarQuery((NIGERIA,)).event_params(NIGERIA)

    assert "gl" not in params
    assert "htichips" not in params


def test_community_search_is_per_country_with_its_code():
    query = RadarQuery((SA, NIGERIA))

    assert query.community_params(SA) == {
        "engine": "google_light",
        "q": '(PyCon OR PyData OR "Python meetup" OR "Django Girls" OR PyLadies) ("South Africa")',
        "hl": "en",
        "gl": "za",
    }
    assert "gl" not in query.community_params(NIGERIA)
    assert query.community_query(NIGERIA).endswith("(Nigeria)")


def test_custom_topic_leads_the_community_search():
    assert (
        RadarQuery((SA,), topic="data science")
        .community_query(SA)
        .startswith('("data science" OR PyCon')
    )


@pytest.mark.parametrize(
    "kwargs",
    [{"countries": ()}, {"countries": (SA,), "topic": "  "}, {"countries": (SA,), "when": "soon"}],
)
def test_invalid_queries(kwargs):
    with pytest.raises(ValueError):
        RadarQuery(**kwargs)
