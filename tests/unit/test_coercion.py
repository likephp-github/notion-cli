"""US-032: Property coercion engine — covers each Notion property type."""

from __future__ import annotations

import pytest

from notion_cli.errors import UserError
from notion_cli.notion.coercion import coerce, find_title_property

SCHEMA = {
    "Name": {"type": "title"},
    "Notes": {"type": "rich_text"},
    "Score": {"type": "number"},
    "Status": {
        "type": "status",
        "status": {"options": [{"name": "Todo"}, {"name": "Done"}]},
    },
    "Priority": {
        "type": "select",
        "select": {"options": [{"name": "Low"}, {"name": "High"}]},
    },
    "Tags": {
        "type": "multi_select",
        "multi_select": {"options": [{"name": "bug"}, {"name": "urgent"}]},
    },
    "Done": {"type": "checkbox"},
    "Due": {"type": "date"},
    "Link": {"type": "url"},
    "Email": {"type": "email"},
    "Phone": {"type": "phone_number"},
    "Owners": {"type": "people"},
    "Related": {"type": "relation"},
    "Mystery": {"type": "files"},  # unsupported type for --set
}


def test_title() -> None:
    assert coerce("Name", "Hi", SCHEMA) == {
        "title": [{"type": "text", "text": {"content": "Hi"}}]
    }


def test_rich_text() -> None:
    assert coerce("Notes", "Hello", SCHEMA) == {
        "rich_text": [{"type": "text", "text": {"content": "Hello"}}]
    }


def test_number_int() -> None:
    assert coerce("Score", "42", SCHEMA) == {"number": 42}


def test_number_float() -> None:
    assert coerce("Score", "3.14", SCHEMA) == {"number": 3.14}


def test_number_invalid() -> None:
    with pytest.raises(UserError, match="number"):
        coerce("Score", "abc", SCHEMA)


def test_select_valid() -> None:
    assert coerce("Priority", "High", SCHEMA) == {"select": {"name": "High"}}


def test_select_unknown_lists_options() -> None:
    with pytest.raises(UserError) as exc:
        coerce("Priority", "Critical", SCHEMA)
    assert "Low" in (exc.value.hint or "")


def test_multi_select_comma_separated() -> None:
    assert coerce("Tags", "bug,urgent", SCHEMA) == {
        "multi_select": [{"name": "bug"}, {"name": "urgent"}]
    }


def test_multi_select_rejects_unknown() -> None:
    with pytest.raises(UserError, match="unknown"):
        coerce("Tags", "bug,nope", SCHEMA)


def test_status_valid() -> None:
    assert coerce("Status", "Done", SCHEMA) == {"status": {"name": "Done"}}


def test_status_unknown() -> None:
    with pytest.raises(UserError, match="status"):
        coerce("Status", "ZZZ", SCHEMA)


@pytest.mark.parametrize("v", ["true", "1", "yes", "Y", "TRUE"])
def test_checkbox_truthy(v: str) -> None:
    assert coerce("Done", v, SCHEMA) == {"checkbox": True}


@pytest.mark.parametrize("v", ["false", "0", "no", "N", "FALSE"])
def test_checkbox_falsy(v: str) -> None:
    assert coerce("Done", v, SCHEMA) == {"checkbox": False}


def test_checkbox_invalid() -> None:
    with pytest.raises(UserError, match="boolean"):
        coerce("Done", "maybe", SCHEMA)


def test_date_iso() -> None:
    out = coerce("Due", "2025-12-31", SCHEMA)
    assert out["date"]["start"].startswith("2025-12-31")


def test_date_invalid() -> None:
    with pytest.raises(UserError, match="date"):
        coerce("Due", "not-a-date", SCHEMA)


def test_url() -> None:
    assert coerce("Link", "https://x.com", SCHEMA) == {"url": "https://x.com"}


def test_email() -> None:
    assert coerce("Email", "a@b.c", SCHEMA) == {"email": "a@b.c"}


def test_phone() -> None:
    assert coerce("Phone", "+1-555", SCHEMA) == {"phone_number": "+1-555"}


def test_people_id_list() -> None:
    assert coerce("Owners", "u1,u2", SCHEMA) == {
        "people": [{"object": "user", "id": "u1"}, {"object": "user", "id": "u2"}]
    }


def test_relation_id_list() -> None:
    assert coerce("Related", "r1,r2", SCHEMA) == {
        "relation": [{"id": "r1"}, {"id": "r2"}]
    }


def test_unknown_property() -> None:
    with pytest.raises(UserError, match="not found"):
        coerce("Nope", "x", SCHEMA)


def test_unsupported_type() -> None:
    with pytest.raises(UserError, match="not supported"):
        coerce("Mystery", "x", SCHEMA)


def test_find_title_property() -> None:
    assert find_title_property(SCHEMA) == "Name"


def test_find_title_property_missing_raises() -> None:
    with pytest.raises(UserError, match="title"):
        find_title_property({"X": {"type": "rich_text"}})
