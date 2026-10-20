import json

from typer.testing import CliRunner

from eventradar import cli
from eventradar.mcp_search import SearchFailed

runner = CliRunner()


def use_fake_backend(monkeypatch, backend, tmp_path):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(cli, "McpSearchBackend", lambda api_key: backend)


def test_near_writes_markdown(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)
    out_file = tmp_path / "radar.md"

    result = runner.invoke(cli.app, ["near", "mozambique", "-o", str(out_file)])

    assert result.exit_code == 0, result.output
    text = out_file.read_text()
    assert text.startswith("# Python conferences and communities near Mozambique\n")
    assert "## Tech events by country" not in text
    assert len(backend.requests) == 7  # Mozambique + 6 neighbours, one web search each
    assert {r["engine"] for r in backend.requests} == {"google_light"}


def test_tech_events_add_one_search_per_country(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)

    result = runner.invoke(cli.app, ["countries", "South Africa", "--tech-events", "--json"])

    assert result.exit_code == 0, result.output
    assert [r["engine"] for r in backend.requests] == ["google_light", "google_events"]
    assert json.loads(result.stdout)["tech_events"]["South Africa"]


def test_budget_trims_countries(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)

    result = runner.invoke(cli.app, ["near", "mozambique", "--max-searches", "2", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["countries"] == ["Mozambique", "Tanzania"]
    assert "South Africa" in payload["skipped_countries"]


def test_budget_counts_two_searches_per_country_with_tech_events(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)

    result = runner.invoke(
        cli.app, ["near", "mozambique", "--tech-events", "--max-searches", "3", "--json"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["countries"] == ["Mozambique"]
    assert len(backend.requests) == 2


def test_second_run_comes_from_the_cache(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)
    runner.invoke(cli.app, ["countries", "South Africa", "--json"])
    runner.invoke(cli.app, ["countries", "South Africa", "--json"])

    assert len(backend.requests) == 1


def test_countries_command_accepts_any_country(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)

    result = runner.invoke(cli.app, ["countries", "Nigeria", "Ghana", "--json", "--no-cache"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["title"] == (
        "Python conferences and communities in Nigeria and Ghana"
    )


def test_unknown_country_for_near(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)

    result = runner.invoke(cli.app, ["near", "Atlantis"])

    assert result.exit_code == 2
    assert len(backend.requests) == 0


def test_exit_code_when_every_search_fails(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)
    backend.responses = {"google_light:za": {"error": "Invalid API key."}}

    result = runner.invoke(cli.app, ["countries", "South Africa", "--no-cache"])

    assert result.exit_code == cli.EXIT_ALL_SEARCHES_FAILED


class UnreachableBackend:
    async def __aenter__(self):
        raise SearchFailed("Could not connect to SerpApi's MCP server (ConnectError).")

    async def __aexit__(self, *exc_info):
        return None


def test_connection_failure_is_one_readable_line(backend, monkeypatch, tmp_path):
    use_fake_backend(monkeypatch, backend, tmp_path)
    monkeypatch.setattr(cli, "McpSearchBackend", lambda api_key: UnreachableBackend())

    result = runner.invoke(cli.app, ["countries", "Kenya", "--no-cache"])

    assert result.exit_code == cli.EXIT_ALL_SEARCHES_FAILED
    assert "Could not connect to SerpApi's MCP server" in result.output
    assert "Traceback" not in result.output


def test_missing_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(cli.app, ["near", "kenya"]).exit_code == cli.EXIT_MISSING_API_KEY
