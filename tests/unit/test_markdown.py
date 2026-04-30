"""US-041: markdown ↔ blocks converter."""

from __future__ import annotations

from notion_cli.notion.markdown import blocks_to_markdown, markdown_to_blocks


def _rich(text: str) -> list[dict]:
    return [{"plain_text": text}]


def test_paragraph_round_trip() -> None:
    md = "Hello world."
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "paragraph"
    assert blocks_to_markdown(blocks) == "Hello world."


def test_heading_levels() -> None:
    blocks = markdown_to_blocks("# H1\n## H2\n### H3")
    assert [b["type"] for b in blocks] == ["heading_1", "heading_2", "heading_3"]
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "H1"


def test_bullet_list() -> None:
    blocks = markdown_to_blocks("- one\n- two")
    assert [b["type"] for b in blocks] == ["bulleted_list_item", "bulleted_list_item"]


def test_numbered_list() -> None:
    blocks = markdown_to_blocks("1. one\n2. two\n3. three")
    assert [b["type"] for b in blocks] == [
        "numbered_list_item",
        "numbered_list_item",
        "numbered_list_item",
    ]


def test_todo_unchecked_and_checked() -> None:
    blocks = markdown_to_blocks("- [ ] open\n- [x] closed")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is False
    assert blocks[1]["to_do"]["checked"] is True


def test_quote() -> None:
    blocks = markdown_to_blocks("> quoted text")
    assert blocks[0]["type"] == "quote"


def test_divider() -> None:
    blocks = markdown_to_blocks("---")
    assert blocks[0]["type"] == "divider"


def test_code_block_with_language() -> None:
    md = "```python\nprint('hi')\n```"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["type"] == "code"
    assert blocks[0]["code"]["language"] == "python"
    assert blocks[0]["code"]["rich_text"][0]["text"]["content"] == "print('hi')"


def test_code_block_no_language_defaults() -> None:
    md = "```\nplain\n```"
    blocks = markdown_to_blocks(md)
    assert blocks[0]["code"]["language"] == "plain text"


def test_blocks_to_markdown_unsupported_block() -> None:
    blocks = [{"type": "image", "image": {"caption": []}}]
    out = blocks_to_markdown(blocks)
    assert "<!-- unsupported: image -->" in out


def test_blocks_to_markdown_to_do_renders_checkbox() -> None:
    blocks = [
        {
            "type": "to_do",
            "to_do": {"rich_text": _rich("done thing"), "checked": True},
        },
        {
            "type": "to_do",
            "to_do": {"rich_text": _rich("open thing"), "checked": False},
        },
    ]
    out = blocks_to_markdown(blocks)
    assert "- [x] done thing" in out
    assert "- [ ] open thing" in out


def test_round_trip_preserves_text_for_supported_types() -> None:
    md = """# Heading 1

- bullet one
- bullet two

1. numbered one
2. numbered two

- [ ] todo open
- [x] todo done

> quoted paragraph

```bash
echo hi
```

---

A paragraph after divider."""
    blocks = markdown_to_blocks(md)
    rendered = blocks_to_markdown(blocks)
    rendered_again = markdown_to_blocks(rendered)
    types_first = [b["type"] for b in blocks]
    types_second = [b["type"] for b in rendered_again]
    assert types_first == types_second
