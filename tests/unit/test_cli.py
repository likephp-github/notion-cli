"""US-006: CLI root app — --version, --help, subcommand groups."""

from __future__ import annotations

from typer.testing import CliRunner

from notion_cli import __version__
from notion_cli.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    for sub in ("init", "logout", "auth", "database", "card", "comment", "search"):
        assert sub in out, f"subcommand {sub!r} missing from --help output"


def test_unknown_subcommand_returns_error() -> None:
    result = runner.invoke(app, ["nonsense"])
    assert result.exit_code != 0
