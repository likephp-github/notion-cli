"""Markdown ↔ Notion blocks converter.

Supported types: paragraph, heading_1-3, bulleted_list_item, numbered_list_item,
to_do, code, quote, divider. Unsupported types render as a comment placeholder
when going blocks → markdown, and are dropped (with a stderr warning) the other way.
"""

from __future__ import annotations

import re
import sys
from typing import Any

_NUMBERED_RE = re.compile(r"^\d+\.\s+")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")


def _rich_to_text(rich: list[dict[str, Any]]) -> str:
    """Extract plain text from a Notion rich_text array.

    Notion API responses include `plain_text`; payloads we *create* use the
    `text.content` shape. Support both so the converter is symmetric.
    """
    out: list[str] = []
    for r in rich:
        if "plain_text" in r:
            out.append(str(r["plain_text"]))
        elif isinstance(r.get("text"), dict):
            out.append(str(r["text"].get("content", "")))
    return "".join(out)


def _text_to_rich(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text}}]


def _make_block(block_type: str, **payload: Any) -> dict[str, Any]:
    return {"object": "block", "type": block_type, block_type: payload}


def _paragraph(text: str) -> dict[str, Any]:
    return _make_block("paragraph", rich_text=_text_to_rich(text))


def _heading(level: int, text: str) -> dict[str, Any]:
    return _make_block(f"heading_{level}", rich_text=_text_to_rich(text))


def _bullet(text: str) -> dict[str, Any]:
    return _make_block("bulleted_list_item", rich_text=_text_to_rich(text))


def _numbered(text: str) -> dict[str, Any]:
    return _make_block("numbered_list_item", rich_text=_text_to_rich(text))


def _todo(checked: bool, text: str) -> dict[str, Any]:
    return _make_block("to_do", rich_text=_text_to_rich(text), checked=checked)


def _quote(text: str) -> dict[str, Any]:
    return _make_block("quote", rich_text=_text_to_rich(text))


def _code(language: str, text: str) -> dict[str, Any]:
    return _make_block(
        "code",
        rich_text=_text_to_rich(text),
        language=language or "plain text",
    )


def _divider() -> dict[str, Any]:
    return _make_block("divider")


def markdown_to_blocks(md: str) -> list[dict[str, Any]]:
    """Parse a subset of markdown into Notion block payloads."""
    lines = md.splitlines()
    blocks: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        # Fenced code block ``` lang ... ```
        if stripped.startswith("```"):
            language = stripped[3:].strip()
            j = i + 1
            code_lines: list[str] = []
            while j < len(lines) and not lines[j].lstrip().startswith("```"):
                code_lines.append(lines[j])
                j += 1
            blocks.append(_code(language, "\n".join(code_lines)))
            i = j + 1  # skip closing fence
            continue

        # Heading
        if (m := _HEADING_RE.match(line)) is not None:
            blocks.append(_heading(len(m.group(1)), m.group(2)))
            i += 1
            continue

        # To-do (must be tested before bullet because both start with "- ")
        if line.startswith("- [ ] "):
            blocks.append(_todo(False, line[6:]))
            i += 1
            continue
        if line.startswith("- [x] ") or line.startswith("- [X] "):
            blocks.append(_todo(True, line[6:]))
            i += 1
            continue

        # Bullet
        if line.startswith("- "):
            blocks.append(_bullet(line[2:]))
            i += 1
            continue

        # Numbered list
        if (m := _NUMBERED_RE.match(line)) is not None:
            blocks.append(_numbered(line[m.end() :]))
            i += 1
            continue

        # Quote
        if line.startswith("> "):
            blocks.append(_quote(line[2:]))
            i += 1
            continue

        # Divider
        if stripped in ("---", "***", "___"):
            blocks.append(_divider())
            i += 1
            continue

        # Paragraph fallback
        blocks.append(_paragraph(line))
        i += 1

    return blocks


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Render Notion blocks back into markdown for AI consumption."""
    pieces: list[str] = []
    for block in blocks:
        bt = block.get("type")
        body = block.get(bt or "", {}) if bt else {}
        rich = body.get("rich_text", []) if isinstance(body, dict) else []
        text = _rich_to_text(rich)

        if bt == "paragraph":
            pieces.append(text)
        elif bt in ("heading_1", "heading_2", "heading_3"):
            level = int(bt.split("_")[1])
            pieces.append("#" * level + " " + text)
        elif bt == "bulleted_list_item":
            pieces.append(f"- {text}")
        elif bt == "numbered_list_item":
            pieces.append(f"1. {text}")
        elif bt == "to_do":
            checked = body.get("checked", False) if isinstance(body, dict) else False
            mark = "x" if checked else " "
            pieces.append(f"- [{mark}] {text}")
        elif bt == "quote":
            pieces.append(f"> {text}")
        elif bt == "code":
            lang = body.get("language", "") if isinstance(body, dict) else ""
            pieces.append(f"```{lang}\n{text}\n```")
        elif bt == "divider":
            pieces.append("---")
        else:
            pieces.append(f"<!-- unsupported: {bt} -->")
    return "\n\n".join(pieces)


def warn_unsupported(_unused: str) -> None:  # pragma: no cover - convenience helper
    sys.stderr.write(_unused)
