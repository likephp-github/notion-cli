"""US-051: comment add / list."""

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


def test_comment_add_passes_payload(mocked_client: MagicMock) -> None:
    mocked_client.comments.create.return_value = {
        "id": "c1",
        "created_time": "2025-01-01T00:00:00Z",
        "rich_text": [{"plain_text": "Hello"}],
    }
    result = runner.invoke(
        app, ["comment", "add", "abc", "--text", "Hello"]
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["id"] == "c1"
    assert payload["data"]["text"] == "Hello"
    _, kwargs = mocked_client.comments.create.call_args
    assert kwargs["parent"] == {"page_id": "abc"}
    assert kwargs["rich_text"][0]["text"]["content"] == "Hello"


def test_comment_list_paginates(mocked_client: MagicMock) -> None:
    mocked_client.comments.list.side_effect = [
        {
            "results": [
                {"id": "c1", "created_time": "t1", "rich_text": [{"plain_text": "First"}]}
            ],
            "has_more": True,
            "next_cursor": "cursor1",
        },
        {
            "results": [
                {"id": "c2", "created_time": "t2", "rich_text": [{"plain_text": "Second"}]}
            ],
            "has_more": False,
        },
    ]
    result = runner.invoke(app, ["comment", "list", "abc"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [c["id"] for c in payload["data"]["comments"]] == ["c1", "c2"]
    assert payload["data"]["count"] == 2
    assert mocked_client.comments.list.call_count == 2
