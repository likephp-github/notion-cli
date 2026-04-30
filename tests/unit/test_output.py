"""US-002: emit_ok writes to stdout, emit_error writes to stderr; both JSON."""

from __future__ import annotations

import json

import pytest

from notion_cli.output import emit_error, emit_ok


def test_emit_ok_writes_envelope_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    emit_ok({"hello": "world"})
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload == {"ok": True, "data": {"hello": "world"}}


def test_emit_ok_with_meta(capsys: pytest.CaptureFixture[str]) -> None:
    emit_ok({"x": 1}, meta={"duration_ms": 12})
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": True, "data": {"x": 1}, "meta": {"duration_ms": 12}}


def test_emit_error_writes_envelope_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    emit_error("INVALID_TOKEN", "bad token", hint="run init")
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload == {
        "ok": False,
        "error": {"code": "INVALID_TOKEN", "message": "bad token", "hint": "run init"},
    }


def test_emit_error_omits_hint_when_none(capsys: pytest.CaptureFixture[str]) -> None:
    emit_error("X", "msg")
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == {"code": "X", "message": "msg"}


def test_pretty_mode_produces_multiline_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--pretty should switch to indented + colorized JSON, vs compact one-liner."""
    from notion_cli import output

    output.set_pretty(True)
    try:
        emit_ok({"a": 1, "b": [1, 2]})
        captured = capsys.readouterr()
        # Compact dump would be 1 line; pretty must span multiple lines.
        assert captured.out.count("\n") >= 2
        # The data must still parse as valid JSON when ANSI escapes are stripped.
        import re

        stripped = re.sub(r"\x1b\[[0-9;]*m", "", captured.out)
        assert json.loads(stripped) == {"ok": True, "data": {"a": 1, "b": [1, 2]}}
    finally:
        output.set_pretty(False)


def test_pretty_mode_routes_errors_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from notion_cli import output

    output.set_pretty(True)
    try:
        emit_error("CODE", "msg")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err  # something was written
    finally:
        output.set_pretty(False)
