"""US-022: card list — pagination, --filter-json, --sort, --limit."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from notion_cli import client as client_module
from notion_cli import credentials
from notion_cli.cli import app

runner = CliRunner()

DB_ID = "11111111-1111-1111-1111-111111111111"


def _page(page_id: str, title: str) -> dict:
    return {
        "id": page_id,
        "url": f"https://notion.so/{page_id}",
        "archived": False,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
            "Status": {"type": "select", "select": {"name": "Todo"}},
        },
    }


@pytest.fixture
def mocked_client(
    monkeypatch: pytest.MonkeyPatch,
    fake_keyring: dict[tuple[str, str], str],
    tmp_home,
) -> MagicMock:
    credentials.set_token("secret_test")
    fake = MagicMock()
    monkeypatch.setattr(client_module, "get_client", lambda token=None: fake)
    return fake


def test_card_list_paginates_until_limit_or_done(mocked_client: MagicMock) -> None:
    mocked_client.databases.query.side_effect = [
        {
            "results": [_page("p1", "First"), _page("p2", "Second")],
            "has_more": True,
            "next_cursor": "cursor-1",
        },
        {
            "results": [_page("p3", "Third")],
            "has_more": False,
            "next_cursor": None,
        },
    ]
    result = runner.invoke(app, ["card", "list", "--database", DB_ID])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    titles = [r["title"] for r in payload["data"]["results"]]
    assert titles == ["First", "Second", "Third"]
    assert payload["data"]["count"] == 3
    assert mocked_client.databases.query.call_count == 2


def test_card_list_respects_limit(mocked_client: MagicMock) -> None:
    mocked_client.databases.query.return_value = {
        "results": [_page(f"p{i}", f"T{i}") for i in range(10)],
        "has_more": False,
    }
    result = runner.invoke(
        app, ["card", "list", "--database", DB_ID, "--limit", "5"]
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["count"] == 5


def test_card_list_filter_json_passed_through(mocked_client: MagicMock) -> None:
    mocked_client.databases.query.return_value = {"results": [], "has_more": False}
    raw_filter = '{"property":"Status","select":{"equals":"Todo"}}'
    result = runner.invoke(
        app, ["card", "list", "--database", DB_ID, "--filter-json", raw_filter]
    )
    assert result.exit_code == 0, result.stderr
    _, kwargs = mocked_client.databases.query.call_args
    assert kwargs["filter"] == json.loads(raw_filter)


def test_card_list_filter_json_invalid(mocked_client: MagicMock) -> None:
    result = runner.invoke(
        app, ["card", "list", "--database", DB_ID, "--filter-json", "not json"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"


def test_card_list_sort_parses_directions(mocked_client: MagicMock) -> None:
    mocked_client.databases.query.return_value = {"results": [], "has_more": False}
    runner.invoke(
        app,
        ["card", "list", "--database", DB_ID, "--sort", "Priority,-CreatedAt"],
    )
    _, kwargs = mocked_client.databases.query.call_args
    assert kwargs["sorts"] == [
        {"property": "Priority", "direction": "ascending"},
        {"property": "CreatedAt", "direction": "descending"},
    ]


def test_card_list_propagates_global_token_flag(
    monkeypatch: pytest.MonkeyPatch,
    fake_keyring: dict[tuple[str, str], str],
    tmp_home,
) -> None:
    """`--token X` on the root command must reach get_client(token=X)."""
    captured: dict[str, str | None] = {}

    fake = MagicMock()
    fake.databases.query.return_value = {"results": [], "has_more": False}

    def spy(token: str | None = None) -> MagicMock:
        captured["token"] = token
        return fake

    monkeypatch.setattr(client_module, "get_client", spy)

    result = runner.invoke(
        app, ["--token", "secret_explicit_cli", "card", "list", "--database", DB_ID]
    )
    assert result.exit_code == 0, result.stderr
    assert captured["token"] == "secret_explicit_cli"
