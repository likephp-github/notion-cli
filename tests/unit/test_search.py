"""US-052: search command."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from notion_cli import client as client_module
from notion_cli import credentials
from notion_cli.cli import app

runner = CliRunner()


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


def test_search_paginates_and_extracts_titles(mocked_client: MagicMock) -> None:
    mocked_client.search.side_effect = [
        {
            "results": [
                {
                    "id": "p1",
                    "object": "page",
                    "url": "https://notion.so/p1",
                    "properties": {
                        "Name": {
                            "type": "title",
                            "title": [{"plain_text": "First Page"}],
                        }
                    },
                }
            ],
            "has_more": True,
            "next_cursor": "cur1",
        },
        {
            "results": [
                {
                    "id": "d1",
                    "object": "database",
                    "url": "https://notion.so/d1",
                    "title": [{"plain_text": "My DB"}],
                }
            ],
            "has_more": False,
        },
    ]
    result = runner.invoke(app, ["search", "needle"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    rows = payload["data"]["results"]
    assert [r["title"] for r in rows] == ["First Page", "My DB"]
    assert [r["type"] for r in rows] == ["page", "database"]


def test_search_filter_type_passed_through(mocked_client: MagicMock) -> None:
    mocked_client.search.return_value = {"results": [], "has_more": False}
    runner.invoke(app, ["search", "x", "--type", "database"])
    _, kwargs = mocked_client.search.call_args
    assert kwargs["filter"] == {"value": "database", "property": "object"}


def test_search_invalid_type(mocked_client: MagicMock) -> None:
    result = runner.invoke(app, ["search", "x", "--type", "block"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"


def test_search_limit_caps_results(mocked_client: MagicMock) -> None:
    mocked_client.search.return_value = {
        "results": [
            {
                "id": f"p{i}",
                "object": "page",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": f"T{i}"}]},
                },
            }
            for i in range(10)
        ],
        "has_more": False,
    }
    result = runner.invoke(app, ["search", "x", "--limit", "3"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["count"] == 3
