"""US-021: database add / ls / rm — alias management."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from notion_cli.cli import app

runner = CliRunner()


@pytest.mark.usefixtures("tmp_home")
def test_database_add_writes_alias() -> None:
    result = runner.invoke(
        app, ["database", "add", "reqs", "--id", "11111111-1111-1111-1111-111111111111"]
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"]["alias"] == "reqs"
    assert payload["data"]["id"] == "11111111-1111-1111-1111-111111111111"


@pytest.mark.usefixtures("tmp_home")
def test_database_add_rejects_invalid_uuid() -> None:
    result = runner.invoke(app, ["database", "add", "reqs", "--id", "not-a-uuid"])
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"


@pytest.mark.usefixtures("tmp_home")
def test_database_add_refuses_overwrite_without_force() -> None:
    db_id = "11111111-1111-1111-1111-111111111111"
    runner.invoke(app, ["database", "add", "reqs", "--id", db_id])
    result = runner.invoke(
        app, ["database", "add", "reqs", "--id", "22222222-2222-2222-2222-222222222222"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "USER_ERROR"


@pytest.mark.usefixtures("tmp_home")
def test_database_add_force_overwrites() -> None:
    runner.invoke(
        app, ["database", "add", "reqs", "--id", "11111111-1111-1111-1111-111111111111"]
    )
    result = runner.invoke(
        app,
        [
            "database",
            "add",
            "reqs",
            "--id",
            "22222222-2222-2222-2222-222222222222",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.stderr


@pytest.mark.usefixtures("tmp_home")
def test_database_ls_shows_default_flag() -> None:
    db_id = "11111111-1111-1111-1111-111111111111"
    runner.invoke(app, ["database", "add", "reqs", "--id", db_id])

    # Manually set default by editing config (no command for it yet — Phase 6 polish)
    from notion_cli import config as config_module

    cfg = config_module.load_config()
    cfg["default"] = {"database": db_id}
    config_module.save_config(cfg)

    result = runner.invoke(app, ["database", "ls"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    items = payload["data"]["databases"]
    assert items == [{"alias": "reqs", "id": db_id, "is_default": True}]
    assert payload["data"]["default"] == db_id


@pytest.mark.usefixtures("tmp_home")
def test_database_ls_when_empty() -> None:
    result = runner.invoke(app, ["database", "ls"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"] == {"databases": [], "default": None}


@pytest.mark.usefixtures("tmp_home")
def test_database_rm_removes_existing() -> None:
    runner.invoke(
        app, ["database", "add", "reqs", "--id", "11111111-1111-1111-1111-111111111111"]
    )
    result = runner.invoke(app, ["database", "rm", "reqs"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"] == {"alias": "reqs", "removed": True}

    ls = runner.invoke(app, ["database", "ls"])
    assert json.loads(ls.stdout)["data"]["databases"] == []


@pytest.mark.usefixtures("tmp_home")
def test_database_rm_idempotent_on_missing() -> None:
    result = runner.invoke(app, ["database", "rm", "nonexistent"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["data"] == {"alias": "nonexistent", "removed": False}
