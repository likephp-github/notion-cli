"""US-004: credentials prefer keyring, fall back to chmod-600 file."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from notion_cli import credentials


@pytest.mark.usefixtures("tmp_home")
def test_get_token_prefers_env(
    monkeypatch: pytest.MonkeyPatch, fake_keyring: dict[tuple[str, str], str]
) -> None:
    fake_keyring[("notion-cli", "default")] = "secret_keyring_value"
    monkeypatch.setenv("NOTION_TOKEN", "secret_env_value")
    assert credentials.get_token() == "secret_env_value"
    assert credentials.token_source() == "env"


@pytest.mark.usefixtures("tmp_home")
def test_set_token_uses_keyring_when_available(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    backend = credentials.set_token("secret_xxx")
    assert backend == "keyring"
    assert fake_keyring == {("notion-cli", "default"): "secret_xxx"}
    assert credentials.get_token() == "secret_xxx"
    assert credentials.token_source() == "keyring"


@pytest.mark.usefixtures("tmp_home", "disabled_keyring")
def test_set_token_falls_back_to_secrets_file_when_keyring_broken(
    tmp_home: Path,
) -> None:
    backend = credentials.set_token("secret_yyy")
    assert backend == "fallback"
    secrets_path = tmp_home / ".config" / "notion-cli" / "secrets.toml"
    assert secrets_path.exists()
    if sys.platform != "win32":
        assert secrets_path.stat().st_mode & 0o777 == 0o600
    assert credentials.get_token() == "secret_yyy"
    assert credentials.token_source() == "fallback"


@pytest.mark.usefixtures("tmp_home")
def test_delete_token_idempotent_when_empty(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    assert credentials.delete_token() == []
    assert credentials.get_token() is None


@pytest.mark.usefixtures("tmp_home")
def test_delete_token_removes_keyring(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    credentials.set_token("secret_a")
    removed = credentials.delete_token()
    assert "keyring" in removed
    assert credentials.get_token() is None


@pytest.mark.usefixtures("tmp_home", "disabled_keyring")
def test_delete_token_removes_fallback(tmp_home: Path) -> None:
    credentials.set_token("secret_z")
    secrets_path = tmp_home / ".config" / "notion-cli" / "secrets.toml"
    assert secrets_path.exists()
    removed = credentials.delete_token()
    assert "fallback" in removed
    assert not secrets_path.exists()


@pytest.mark.usefixtures("tmp_home")
def test_config_does_not_contain_token(
    fake_keyring: dict[tuple[str, str], str],
    tmp_home: Path,
) -> None:
    credentials.set_token("secret_must_not_leak")
    cfg_path = tmp_home / ".config" / "notion-cli" / "config.toml"
    if cfg_path.exists():
        content = cfg_path.read_text()
        assert "secret_must_not_leak" not in content
    secrets_path = tmp_home / ".config" / "notion-cli" / "secrets.toml"
    assert not secrets_path.exists()
    _ = os
