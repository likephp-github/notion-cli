"""US-005: get_client raises AuthError when no token is configured."""

from __future__ import annotations

import pytest

from notion_cli import client as client_module
from notion_cli.errors import AuthError


@pytest.mark.usefixtures("tmp_home")
def test_get_client_raises_when_no_token(
    fake_keyring: dict[tuple[str, str], str],  # empty fake keyring
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    with pytest.raises(AuthError):
        client_module.get_client()


@pytest.mark.usefixtures("tmp_home")
def test_get_client_uses_explicit_token() -> None:
    client = client_module.get_client(token="secret_explicit")
    # notion_client.Client stores the auth token internally — we just verify it constructed.
    assert client is not None


@pytest.mark.usefixtures("tmp_home")
def test_get_client_uses_credentials_when_no_arg(
    fake_keyring: dict[tuple[str, str], str],
) -> None:
    fake_keyring[("notion-cli", "default")] = "secret_via_keyring"
    client = client_module.get_client()
    assert client is not None


def test_call_passes_through_for_simple_callable() -> None:
    assert client_module.call(lambda x: x + 1, 41) == 42
