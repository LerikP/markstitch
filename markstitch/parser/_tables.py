"""Parse table cells while respecting nested tables, code and escaped separators."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from markstitch.attributes import Attributes
from markstitch.inline import Text
from markstitch.parser._syntax import code_end, take_attributes
from markstitch.tables import Cell, Row, Span, Table, TableFlag, YFMTable

if TYPE_CHECKING:
    from markdown_it.tree import SyntaxTreeNode

    from markstitch.core import Element
    from markstitch.parser._engine import Parser

TABLE_FLAG_NAMES = "|".join(re.escape(flag) for flag in TableFlag)
TABLE_SUFFIX = re.compile(rf"\{{(?:{TABLE_FLAG_NAMES})(?:\s+(?:{TABLE_FLAG_NAMES}))*\}}|\s")


def simple_table(node: SyntaxTreeNode, parser: Parser, depth: int) -> Table:
    header = node.children[0].children[0]
    headers = [Text(*parser.inlines(cell.children[0].content, depth + 1)) for cell in header.children]
    align = [f"{cell.attrs.get('style', '')}".removeprefix("text-align:") or "default" for cell in header.children]
    rows = [
        [Text(*parser.inlines(cell.children[0].content, depth + 1)) for cell in row.children]
        for section in node.children[1:]
        for row in section.children
    ]

    return Table(headers, rows, align=align)


def multiline_table(source: str, parser: Parser, depth: int) -> YFMTable:
    end = source.rfind("|#")

    if end < 0:
        raise ValueError("Unclosed table")

    suffix = source[end + 2 :].strip()
    flags = set(re.findall(r"[\w-]+", suffix))

    if TABLE_SUFFIX.sub("", suffix):
        raise ValueError("Unknown table suffix")

    body = source[2:end].strip()
    table_attrs: dict[str, str] = {}

    while body.startswith("|:{"):
        attrs, body = take_attributes(body, "|:{")

        if table_attrs.keys() & attrs.keys():
            raise ValueError("Expected unique table attributes")

        table_attrs.update(attrs)
        body = body.lstrip()

    header_rows = int(table_attrs.pop("header-rows", "0"))
    rows = [_row(cells, parser, depth) for cells in _split_rows(body)]
    return YFMTable(
        *rows,
        header_rows=header_rows,
        wide=TableFlag.WIDE in flags,
        sticky_header=TableFlag.STICKY_HEADER in flags,
        attributes=_attributes(table_attrs),
    )


def _row(cells: list[str], parser: Parser, depth: int) -> Row:
    attrs, first = take_attributes(cells[0], ":{")
    cells[0] = first
    result: list[Element | str] = []

    for source in cells:
        content = source.strip()

        if content in {">", "^"}:
            result.append(Span(content))
            continue

        cell_attrs, content = take_attributes(content, "::{")
        align = cell_attrs.pop("align", None)
        result.append(
            Cell(*parser.blocks(content.strip(), depth + 1), align=align, attributes=_attributes(cell_attrs))
        )

    return Row(*result, attributes=_attributes(attrs))


def _attributes(values: dict[str, str]) -> Attributes | None:
    if not values:
        return None

    values = dict(values)
    identity = values.pop("id", None)
    classes = tuple(values.pop("class", "").split())
    style = {}

    for declaration in values.pop("style", "").split(";"):
        if not declaration.strip():
            continue

        name, separator, value = declaration.partition(":")

        if not separator:
            raise ValueError("Invalid CSS declaration")

        name = name.strip()

        if name in style:
            raise ValueError("Expected unique CSS declarations")

        style[name] = value.strip()

    return Attributes(id=identity, classes=classes, style=style, extra=values)


def _split_rows(source: str) -> list[list[str]]:
    rows: list[list[str]] = []
    cells: list[str] | None = None
    start = position = 0
    nested = 0

    while position < len(source):
        skip = _opaque_end(source, position)

        if skip is not None:
            position = skip
            continue

        if source.startswith("#|", position):
            nested += 1
            position += 2
        elif source.startswith("|#", position):
            nested -= 1
            position += 2
        elif not nested and source.startswith("||", position):
            if cells is None:
                if source[start:position].strip():
                    raise ValueError("Text outside table rows")

                cells = []
            else:
                cells.append(source[start:position])
                rows.append(cells)
                cells = None

            position += 2
            start = position
        elif not nested and source[position] == "|" and cells is not None:
            cells.append(source[start:position])
            position += 1
            start = position
        else:
            position += 1

    if cells is not None or nested or source[start:].strip():
        raise ValueError("Unclosed table row or nested table")

    return rows


def _opaque_end(source: str, position: int) -> int | None:
    if source[position] == "\\":
        return position + 2

    if (end := code_end(source, position)) is not None:
        return end

    if source[position] == "{" and (attribute_end := source.find("}", position + 1)) >= 0:
        return attribute_end + 1

    return None
