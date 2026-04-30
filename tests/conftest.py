"""Shared pytest fixtures for notion-cli tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect HOME / XDG_CONFIG_HOME / XDG_CACHE_HOME to a tmp directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    yield home


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], str]:
    """Replace the keyring backend with an in-memory dict.

    Returns the dict so tests can inspect its state.
    """
    store: dict[tuple[str, str], str] = {}

    class FakeBackend:
        def get_password(self, service: str, username: str) -> str | None:
            return store.get((service, username))

        def set_password(self, service: str, username: str, password: str) -> None:
            store[(service, username)] = password

        def delete_password(self, service: str, username: str) -> None:
            if (service, username) not in store:
                from keyring.errors import PasswordDeleteError

                raise PasswordDeleteError("not found")
            del store[(service, username)]

    import keyring

    backend = FakeBackend()
    monkeypatch.setattr(keyring, "get_password", backend.get_password)
    monkeypatch.setattr(keyring, "set_password", backend.set_password)
    monkeypatch.setattr(keyring, "delete_password", backend.delete_password)
    return store


@pytest.fixture
def disabled_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every keyring call raise — used to test the secrets-file fallback path."""
    import keyring
    from keyring.errors import KeyringError

    def boom(*args: object, **kwargs: object) -> None:
        raise KeyringError("no backend available")

    monkeypatch.setattr(keyring, "get_password", boom)
    monkeypatch.setattr(keyring, "set_password", boom)
    monkeypatch.setattr(keyring, "delete_password", boom)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests unless NOTION_TEST_TOKEN is set."""
    if os.environ.get("NOTION_TEST_TOKEN"):
        return
    skip_integration = pytest.mark.skip(reason="NOTION_TEST_TOKEN not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
