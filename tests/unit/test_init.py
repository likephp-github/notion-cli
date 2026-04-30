"""US-007: notion-cli init — non-interactive happy path + ALREADY_CONFIGURED."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from notion_cli import client as client_module
from notion_cli import credentials
from notion_cli.cli import app

runner = CliRunner()


def _fake_client(databases: list[dict[str, Any]] | None = None) -> MagicMock:
    fake = MagicMock()
    fake.users.me.return_value = {
        "id": "bot-1",
        "name": "Test Integration",
        "bot": {"workspace_name": "WS"},
    }
    fake.search.return_value = {
        "results": [
            {
                "object": "database",
                "id": db["id"],
                "title": [{"plain_text": db["title"]}],
            }
            for db in (databases or [])
        ]
    }
    return fake


@pytest.mark.usefixtures("tmp_home")
def test_init_non_interactive_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    fake = _fake_client(
        databases=[{"id": "11111111-1111-1111-1111-111111111111", "title": "Reqs"}]
    )
    monkeypatch.setattr(client_module, "get_client", lambda token=None: fake)

    result = runner.invoke(
        app,
        [
            "init",
            "--token",
            "secret_abc",
            "--database",
            "11111111-1111-1111-1111-111111111111",
            "--alias",
            "reqs",
        ],
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    data = payload["data"]
    assert data["integration_name"] == "Test Integration"
    assert data["default_database"] == "11111111-1111-1111-1111-111111111111"
    assert data["alias"] == "reqs"

    assert credentials.get_token() == "secret_abc"


@pytest.mark.usefixtures("tmp_home")
def test_init_rejects_when_already_configured(
    monkeypatch: pytest.MonkeyPatch,
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    credentials.set_token("secret_existing")
    monkeypatch.setattr(client_module, "get_client", lambda token=None: _fake_client())

    result = runner.invoke(
        app,
        [
            "init",
            "--token",
            "secret_new",
            "--database",
            "11111111-1111-1111-1111-111111111111",
        ],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "ALREADY_CONFIGURED"


@pytest.mark.usefixtures("tmp_home")
def test_init_force_overwrites(
    monkeypatch: pytest.MonkeyPatch,
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    credentials.set_token("secret_old")
    fake = _fake_client(
        databases=[{"id": "22222222-2222-2222-2222-222222222222", "title": "X"}]
    )
    monkeypatch.setattr(client_module, "get_client", lambda token=None: fake)

    result = runner.invoke(
        app,
        [
            "init",
            "--token",
            "secret_new",
            "--database",
            "22222222-2222-2222-2222-222222222222",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert credentials.get_token() == "secret_new"
