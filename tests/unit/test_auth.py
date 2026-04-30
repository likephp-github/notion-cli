"""US-009: notion-cli auth verify + auth status."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from notion_cli import client as client_module
from notion_cli import config as config_module
from notion_cli import credentials
from notion_cli.cli import app

runner = CliRunner()


def _fake_client() -> MagicMock:
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
                "id": "11111111-1111-1111-1111-111111111111",
                "title": [{"plain_text": "Reqs"}],
            }
        ]
    }
    return fake


@pytest.mark.usefixtures("tmp_home")
def test_auth_verify_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    credentials.set_token("secret_abc")
    monkeypatch.setattr(client_module, "get_client", lambda token=None: _fake_client())

    result = runner.invoke(app, ["auth", "verify"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["integration_name"] == "Test Integration"
    assert payload["data"]["databases"] == [
        {"id": "11111111-1111-1111-1111-111111111111", "title": "Reqs"}
    ]


@pytest.mark.usefixtures("tmp_home")
def test_auth_verify_no_token_returns_invalid_token(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    result = runner.invoke(app, ["auth", "verify"])
    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.usefixtures("tmp_home")
def test_auth_status_when_unconfigured(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["configured"] is False
    assert payload["data"]["token_source"] is None
    assert payload["data"]["default_database"] is None


@pytest.mark.usefixtures("tmp_home")
def test_auth_status_when_configured_does_not_leak_token(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    credentials.set_token("secret_must_not_leak")
    config_module.save_config(
        {"default": {"database": "11111111-1111-1111-1111-111111111111"}}
    )

    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["configured"] is True
    assert payload["data"]["token_source"] == "keyring"
    assert (
        payload["data"]["default_database"] == "11111111-1111-1111-1111-111111111111"
    )
    # Critical invariant: token never appears anywhere in output.
    assert "secret_must_not_leak" not in result.stdout
    assert "secret_must_not_leak" not in result.stderr
