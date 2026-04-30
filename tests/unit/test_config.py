"""US-003: config loader / saver / resolve_database."""

from __future__ import annotations

from pathlib import Path

import pytest

from notion_cli import config as config_module


@pytest.mark.usefixtures("tmp_home")
def test_load_returns_empty_when_missing() -> None:
    assert config_module.load_config() == {}


@pytest.mark.usefixtures("tmp_home")
def test_save_then_load_roundtrip() -> None:
    cfg = {
        "default": {"database": "11111111-1111-1111-1111-111111111111"},
        "databases": {"requirements": {"id": "22222222-2222-2222-2222-222222222222"}},
    }
    config_module.save_config(cfg)
    assert config_module.load_config() == cfg


def test_save_creates_dir_with_mode_0700(tmp_home: Path) -> None:
    cfg_dir = config_module.config_dir()
    assert not cfg_dir.exists()
    config_module.save_config({"default": {"database": "abc"}})
    assert cfg_dir.exists()
    mode = cfg_dir.stat().st_mode & 0o777
    assert mode == 0o700


def test_is_uuid_accepts_dashed_and_dashless() -> None:
    assert config_module.is_uuid("11111111-1111-1111-1111-111111111111")
    assert config_module.is_uuid("11111111111111111111111111111111")
    assert not config_module.is_uuid("requirements")
    assert not config_module.is_uuid("not-a-uuid")


def test_resolve_database_passes_through_uuid() -> None:
    db_id = "11111111-1111-1111-1111-111111111111"
    assert config_module.resolve_database(db_id, {}) == db_id


def test_resolve_database_alias_lookup() -> None:
    cfg = {"databases": {"reqs": {"id": "22222222-2222-2222-2222-222222222222"}}}
    assert config_module.resolve_database("reqs", cfg) == "22222222-2222-2222-2222-222222222222"


def test_resolve_database_unknown_alias_returns_none() -> None:
    assert config_module.resolve_database("nonsense", {"databases": {}}) is None


def test_resolve_database_default_when_no_argument() -> None:
    cfg = {"default": {"database": "33333333-3333-3333-3333-333333333333"}}
    assert config_module.resolve_database(None, cfg) == "33333333-3333-3333-3333-333333333333"


def test_resolve_database_returns_none_when_no_default() -> None:
    assert config_module.resolve_database(None, {}) is None


def test_resolve_database_env_var_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """NOTION_DATABASE_ID env var fills the gap when no arg AND no config default."""
    monkeypatch.setenv("NOTION_DATABASE_ID", "44444444-4444-4444-4444-444444444444")
    assert config_module.resolve_database(None, {}) == "44444444-4444-4444-4444-444444444444"


def test_resolve_database_env_outranks_config_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both env and config default exist, env wins (per CLI tradition)."""
    monkeypatch.setenv("NOTION_DATABASE_ID", "44444444-4444-4444-4444-444444444444")
    cfg = {"default": {"database": "55555555-5555-5555-5555-555555555555"}}
    assert config_module.resolve_database(None, cfg) == "44444444-4444-4444-4444-444444444444"


def test_resolve_database_explicit_arg_outranks_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit UUID/alias must always win over env or config default."""
    monkeypatch.setenv("NOTION_DATABASE_ID", "99999999-9999-9999-9999-999999999999")
    cfg = {"databases": {"reqs": {"id": "11111111-1111-1111-1111-111111111111"}}}
    assert config_module.resolve_database("reqs", cfg) == "11111111-1111-1111-1111-111111111111"


def test_resolve_database_unknown_alias_does_not_fall_back_to_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failing an explicit alias lookup must NOT silently route to env's default."""
    monkeypatch.setenv("NOTION_DATABASE_ID", "44444444-4444-4444-4444-444444444444")
    assert config_module.resolve_database("nonsense", {"databases": {}}) is None
