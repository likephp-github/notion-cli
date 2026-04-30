"""US-008: notion-cli logout — full clear, --keep-config, idempotent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from notion_cli import config as config_module
from notion_cli import credentials
from notion_cli.cli import app

runner = CliRunner()


@pytest.mark.usefixtures("tmp_home")
def test_logout_idempotent_on_empty_state(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["removed"] == []


@pytest.mark.usefixtures("tmp_home")
def test_logout_clears_everything(
    fake_keyring: dict[tuple[str, str], str], tmp_home: Path
) -> None:
    credentials.set_token("secret_x")
    config_module.save_config({"default": {"database": "abc"}})
    cache = config_module.cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "marker.txt").write_text("hi")

    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0, result.stderr

    payload = json.loads(result.stdout)
    removed = set(payload["data"]["removed"])
    assert "token_keyring" in removed
    assert "config_file" in removed
    assert "cache_dir" in removed

    assert credentials.get_token() is None
    assert not config_module.config_path().exists()
    assert not cache.exists()


@pytest.mark.usefixtures("tmp_home")
def test_logout_keep_config_preserves_config(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    credentials.set_token("secret_x")
    config_module.save_config({"default": {"database": "abc"}})

    result = runner.invoke(app, ["logout", "--keep-config"])
    assert result.exit_code == 0, result.stderr

    payload = json.loads(result.stdout)
    removed = set(payload["data"]["removed"])
    assert "token_keyring" in removed
    assert "config_file" not in removed
    assert config_module.config_path().exists()
    assert credentials.get_token() is None
