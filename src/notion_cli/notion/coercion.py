"""Type-aware coercion of `--set Prop=Value` arguments into Notion API payloads."""

from __future__ import annotations

from typing import Any

from dateutil import parser as date_parser

from notion_cli.errors import UserError


def _select_options(prop: dict[str, Any], kind: str) -> list[str]:
    return [o["name"] for o in prop.get(kind, {}).get("options", []) if "name" in o]


def _coerce_number(prop_name: str, value: str) -> dict[str, Any]:
    try:
        num: int | float = int(value)
    except ValueError:
        try:
            num = float(value)
        except ValueError as exc:
            raise UserError(
                f"Property {prop_name!r} expects a number, got: {value!r}"
            ) from exc
    return {"number": num}


def _coerce_checkbox(prop_name: str, value: str) -> dict[str, Any]:
    truthy = {"true", "1", "yes", "y"}
    falsy = {"false", "0", "no", "n"}
    v = value.strip().lower()
    if v in truthy:
        return {"checkbox": True}
    if v in falsy:
        return {"checkbox": False}
    raise UserError(
        f"Property {prop_name!r} expects boolean, got: {value!r}",
        hint="Use one of: true/false/1/0/yes/no",
    )


def _coerce_date(prop_name: str, value: str) -> dict[str, Any]:
    try:
        dt = date_parser.parse(value)
    except (ValueError, OverflowError) as exc:
        raise UserError(
            f"Property {prop_name!r} expects a date, got: {value!r} ({exc})"
        ) from exc
    return {"date": {"start": dt.isoformat()}}


def coerce(prop_name: str, value: str, schema_props: dict[str, Any]) -> dict[str, Any]:
    """Convert (`prop`, `value`) into a Notion property payload using the schema."""
    if prop_name not in schema_props:
        available = ", ".join(sorted(schema_props.keys()))
        raise UserError(
            f"Property {prop_name!r} not found.",
            hint=f"Available: {available}" if available else "Database has no properties.",
        )
    prop = schema_props[prop_name]
    ptype = prop.get("type")

    if ptype == "title":
        return {"title": [{"type": "text", "text": {"content": value}}]}
    if ptype == "rich_text":
        return {"rich_text": [{"type": "text", "text": {"content": value}}]}
    if ptype == "number":
        return _coerce_number(prop_name, value)
    if ptype == "select":
        options = _select_options(prop, "select")
        if value not in options:
            raise UserError(
                f"Property {prop_name!r}: option {value!r} not found.",
                hint=f"Available options: {', '.join(options)}",
            )
        return {"select": {"name": value}}
    if ptype == "multi_select":
        options = _select_options(prop, "multi_select")
        items = [v.strip() for v in value.split(",") if v.strip()]
        unknown = [v for v in items if v not in options]
        if unknown:
            raise UserError(
                f"Property {prop_name!r}: unknown options {unknown}.",
                hint=f"Available options: {', '.join(options)}",
            )
        return {"multi_select": [{"name": v} for v in items]}
    if ptype == "status":
        options = _select_options(prop, "status")
        if value not in options:
            raise UserError(
                f"Property {prop_name!r}: status {value!r} not found.",
                hint=f"Available options: {', '.join(options)}",
            )
        return {"status": {"name": value}}
    if ptype == "checkbox":
        return _coerce_checkbox(prop_name, value)
    if ptype == "date":
        return _coerce_date(prop_name, value)
    if ptype == "url":
        return {"url": value}
    if ptype == "email":
        return {"email": value}
    if ptype == "phone_number":
        return {"phone_number": value}
    if ptype == "people":
        ids = [v.strip() for v in value.split(",") if v.strip()]
        return {"people": [{"object": "user", "id": i} for i in ids]}
    if ptype == "relation":
        ids = [v.strip() for v in value.split(",") if v.strip()]
        return {"relation": [{"id": i} for i in ids]}

    raise UserError(
        f"Property {prop_name!r} has type {ptype!r}; not supported for --set.",
        hint="Use --set-raw '<json>' to pass a raw payload for this property.",
    )


def find_title_property(schema_props: dict[str, Any]) -> str:
    for name, prop in schema_props.items():
        if prop.get("type") == "title":
            return name
    raise UserError("Database has no title property.")
