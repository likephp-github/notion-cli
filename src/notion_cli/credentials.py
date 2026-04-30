"""Token storage: OS keyring primary, chmod-600 secrets.toml fallback."""

from __future__ import annotations

import contextlib
import os
import tomllib
from pathlib import Path
from typing import Literal

import keyring
import tomli_w
from keyring.errors import KeyringError, PasswordDeleteError

from notion_cli.config import config_dir

SERVICE = "notion-cli"
ACCOUNT = "default"

TokenSource = Literal["env", "keyring", "fallback"]


def _secrets_path() -> Path:
    return config_dir() / "secrets.toml"


def _read_fallback() -> str | None:
    path = _secrets_path()
    try:
        with path.open("rb") as fp:
            data = tomllib.load(fp)
    except FileNotFoundError:
        return None
    token = data.get("token")
    return str(token) if token else None


def _write_fallback(token: str) -> None:
    path = _secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with contextlib.suppress(OSError):
        path.parent.chmod(0o700)
    with path.open("wb") as fp:
        tomli_w.dump({"token": token}, fp)
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def _delete_fallback() -> bool:
    path = _secrets_path()
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


_ = os  # keep import for environment access below


def _keyring_get() -> str | None:
    try:
        value = keyring.get_password(SERVICE, ACCOUNT)
    except KeyringError:
        return None
    return value


def _keyring_set(token: str) -> bool:
    try:
        keyring.set_password(SERVICE, ACCOUNT, token)
    except KeyringError:
        return False
    return True


def _keyring_delete() -> bool:
    try:
        keyring.delete_password(SERVICE, ACCOUNT)
    except (KeyringError, PasswordDeleteError):
        return False
    return True


def get_token() -> str | None:
    """Resolve the active token: NOTION_TOKEN env → keyring → fallback file."""
    env = os.environ.get("NOTION_TOKEN")
    if env:
        return env
    via_keyring = _keyring_get()
    if via_keyring:
        return via_keyring
    return _read_fallback()


def token_source() -> TokenSource | None:
    """Return where the active token came from, or None if no token is configured."""
    if os.environ.get("NOTION_TOKEN"):
        return "env"
    if _keyring_get():
        return "keyring"
    if _read_fallback():
        return "fallback"
    return None


def set_token(token: str) -> TokenSource:
    """Persist the token, preferring keyring; return the storage backend that was used."""
    if _keyring_set(token):
        return "keyring"
    _write_fallback(token)
    return "fallback"


def delete_token() -> list[TokenSource]:
    """Remove the token from every backend; return the backends that had data."""
    removed: list[TokenSource] = []
    if _keyring_get() is not None and _keyring_delete():
        removed.append("keyring")
    if _delete_fallback():
        removed.append("fallback")
    return removed
