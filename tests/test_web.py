from datetime import date

import pytest
from fastapi.testclient import TestClient

from eventradar import web
from eventradar.limits import DemoLimits, LimitReached, RadarCache


def demo(backend, tmp_path, *, daily_searches=100):
    app = web.create_app(lambda: backend, daily_searches=daily_searches, cache_dir=tmp_path)
    return TestClient(app)


def test_home_shows_the_country_picker(backend, tmp_path):
    page = demo(backend, tmp_path).get("/")

    assert page.status_code == 200
    assert '<option value="Namibia">Namibia</option>' in page.text
    assert '<option value="Mozambique" selected>' in page.text
    assert backend.requests == []


def test_radar_with_neighbours_searches_each_country_once(backend, tmp_path):
    page = demo(backend, tmp_path).get("/radar", params={"country": "Namibia", "neighbours": "on"})

    assert page.status_code == 200
    assert "<h1>Python conferences and communities near Namibia</h1>" in page.text
    assert 'href="https://na.pycon.org/2027/"' in page.text
    assert len(backend.requests) == 5  # Namibia + Angola, Zambia, Botswana, South Africa


def test_single_country_radar(backend, tmp_path):
    page = demo(backend, tmp_path).get("/radar", params={"country": "Namibia"})

    assert "<h1>Python conferences and communities in Namibia</h1>" in page.text
    assert len(backend.requests) == 1


def test_repeat_radar_comes_from_the_cache(backend, tmp_path):
    client = demo(backend, tmp_path)
    client.get("/radar", params={"country": "Namibia"})
    client.get("/radar", params={"country": "Namibia"})

    assert len(backend.requests) == 1


def test_searches_already_cached_are_not_charged(backend, tmp_path):
    client = demo(backend, tmp_path, daily_searches=5)
    client.get("/radar", params={"country": "Namibia", "neighbours": "on"})

    page = client.get("/radar", params={"country": "South Africa"})

    assert page.status_code == 200
    assert len(backend.requests) == 5


def test_daily_search_limit_returns_429(backend, tmp_path):
    page = demo(backend, tmp_path, daily_searches=4).get(
        "/radar", params={"country": "Namibia", "neighbours": "on"}
    )

    assert page.status_code == 429
    assert "Please try again tomorrow" in page.text
    assert backend.requests == []


def test_visitor_limit_returns_429(backend, tmp_path):
    client = demo(backend, tmp_path)
    headers = {"X-Forwarded-For": "203.0.113.7"}
    for country in ["Kenya", "Uganda", "Rwanda"]:
        client.get("/radar", params={"country": country}, headers=headers)

    page = client.get("/radar", params={"country": "Malawi"}, headers=headers)
    other = client.get(
        "/radar", params={"country": "Malawi"}, headers={"X-Forwarded-For": "198.51.100.2"}
    )

    assert page.status_code == 429
    assert "in the last hour" in page.text
    assert other.status_code == 200


def test_unknown_country_returns_400(backend, tmp_path):
    page = demo(backend, tmp_path).get("/radar", params={"country": "<b>Atlantis</b>"})

    assert page.status_code == 400
    assert "<b>Atlantis</b>" not in page.text
    assert backend.requests == []


def test_missing_api_key_returns_503(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    client = TestClient(web.create_app(cache_dir=tmp_path))

    assert client.get("/radar", params={"country": "Kenya"}).status_code == 503


def test_result_html_is_escaped(backend, tmp_path):
    backend.responses["google_light:na"]["organic_results"][0]["snippet"] = (
        "<script>alert(1)</script> PyCon"
    )
    page = demo(backend, tmp_path).get("/radar", params={"country": "Namibia"})

    assert "<script>alert(1)</script>" not in page.text


def test_sample_radar_needs_no_searches(backend, tmp_path):
    page = demo(backend, tmp_path).get("/example")

    assert page.status_code == 200
    assert "PyCon Namibia" in page.text
    assert backend.requests == []


def test_healthz(backend, tmp_path):
    assert demo(backend, tmp_path).get("/healthz").text == "ok"


def test_cache_entries_expire():
    now = [0.0]
    cache = RadarCache(ttl_seconds=10, clock=lambda: now[0])
    cache.put("key", "radar")
    now[0] = 9
    assert cache.get("key") == "radar"
    now[0] = 10
    assert cache.get("key") is None


def test_limits_reset_each_hour_and_each_day():
    now, today = [0.0], [date(2026, 10, 20)]
    limits = DemoLimits(
        daily_searches=4,
        radars_per_visitor_per_hour=1,
        clock=lambda: now[0],
        today=lambda: today[0],
    )
    limits.reserve("ip", 2)
    with pytest.raises(LimitReached):
        limits.reserve("ip", 1)

    now[0] = 3600
    limits.reserve("ip", 2)
    with pytest.raises(LimitReached):
        limits.reserve("other-ip", 1)

    today[0] = date(2026, 10, 21)
    limits.reserve("other-ip", 4)
