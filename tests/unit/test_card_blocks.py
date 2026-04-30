"""US-042 + US-043: card read / append (blocks)."""

from __future__ import annotations

import json
from pathlib import Path
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


def _block(text: str, btype: str = "paragraph") -> dict:
    return {
        "object": "block",
        "type": btype,
        btype: {"rich_text": [{"plain_text": text, "type": "text"}]},
    }


def test_card_read_markdown_paginates(mocked_client: MagicMock) -> None:
    mocked_client.blocks.children.list.side_effect = [
        {"results": [_block("Page 1 line")], "has_more": True, "next_cursor": "c1"},
        {"results": [_block("Page 2 line", "heading_1")], "has_more": False},
    ]
    result = runner.invoke(app, ["card", "read", "abc"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    md = payload["data"]["markdown"]
    assert "Page 1 line" in md
    assert "# Page 2 line" in md
    assert mocked_client.blocks.children.list.call_count == 2


def test_card_read_json_returns_raw_blocks(mocked_client: MagicMock) -> None:
    mocked_client.blocks.children.list.return_value = {
        "results": [_block("hi")],
        "has_more": False,
    }
    result = runner.invoke(app, ["card", "read", "abc", "--format", "json"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["blocks"][0]["type"] == "paragraph"


def test_card_read_invalid_format(mocked_client: MagicMock) -> None:
    result = runner.invoke(app, ["card", "read", "abc", "--format", "html"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"


def test_card_append_markdown(mocked_client: MagicMock) -> None:
    result = runner.invoke(
        app,
        ["card", "append", "abc", "--markdown", "# Heading\n\nparagraph"],
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["appended"] == 2
    _, kwargs = mocked_client.blocks.children.append.call_args
    assert kwargs["block_id"] == "abc"
    assert kwargs["children"][0]["type"] == "heading_1"
    assert kwargs["children"][1]["type"] == "paragraph"


def test_card_append_from_file(mocked_client: MagicMock, tmp_path: Path) -> None:
    md_file = tmp_path / "note.md"
    md_file.write_text("- one\n- two\n")
    result = runner.invoke(app, ["card", "append", "abc", "--from-file", str(md_file)])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["appended"] == 2


def test_card_append_requires_one_source(mocked_client: MagicMock) -> None:
    result = runner.invoke(app, ["card", "append", "abc"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"


def test_card_append_both_sources_rejected(
    mocked_client: MagicMock, tmp_path: Path
) -> None:
    md_file = tmp_path / "x.md"
    md_file.write_text("hi")
    result = runner.invoke(
        app,
        [
            "card",
            "append",
            "abc",
            "--markdown",
            "stuff",
            "--from-file",
            str(md_file),
        ],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"
