"""Simple Markdown tables and multiline YFM tables."""

from collections.abc import Iterable
from enum import StrEnum

from markstitch.attributes import Attributes
from markstitch.core import Container, Element, Profile, blocks, choice, inline, one_line, render, require


class Span(StrEnum):
    LEFT = ">"
    ABOVE = "^"


class TableFlag(StrEnum):
    WIDE = "wide-content"
    STICKY_HEADER = "sticky-header"


class Cell(Container):
    def __init__(
        self, *children: Element | str, align: str | None = None, attributes: Attributes | None = None
    ) -> None:
        super().__init__(*children)
        self.align = align
        self.attributes = attributes

    def _render(self, profile: Profile) -> str:
        parts = []

        if self.align is not None:
            require(profile, "Cell alignment", Profile.DIPLODOC)
            choice(
                self.align,
                {"top-left", "top-center", "top-right", "center", "bottom-left", "bottom-center", "bottom-right"},
                "cell alignment",
            )
            parts.append(f'align="{self.align}"')

        if self.attributes is not None:
            require(profile, "Cell attributes", Profile.DIPLODOC)
            parts.append(self.attributes.to_yfm())

        attributes = "::{" + " ".join(filter(None, parts)) + "} " if any(parts) else ""

        body = blocks(self.children, profile)

        if attributes and "\n" in body:
            return attributes.rstrip() + "\n" + body

        return attributes + body


class Row(Element):
    _child_fields = ("cells",)

    def __init__(self, *cells: Cell | Element | str | Span, attributes: Attributes | None = None) -> None:
        self.cells = tuple(cells)
        self.attributes = attributes

    def _render(self, profile: Profile) -> str:
        values = []

        for cell in self.cells:
            if isinstance(cell, Span):
                require(profile, "Merged cells", Profile.DIPLODOC)
                values.append(cell.value)
            else:
                values.append(render(cell, profile))

        prefix = "||"

        if self.attributes is not None:
            require(profile, "Row attributes", Profile.DIPLODOC)
            prefix += ":{" + self.attributes.to_yfm() + "}"

        if any("\n" in value for value in values):
            return (
                "".join(
                    (prefix if column_index == 0 else "\n|") + (value if value.startswith("::{") else f"\n{value}")
                    for column_index, value in enumerate(values)
                )
                + "\n||"
            )

        return prefix + "|".join(f"{value} " if value.startswith("::{") else f" {value} " for value in values) + "||"


class Table(Element):
    _child_fields = ("headers", "rows")

    def __init__(
        self,
        headers: Iterable[Element | str],
        rows: Iterable[Iterable[Element | str]],
        *,
        align: Iterable[str] | None = None,
    ) -> None:
        self.headers = tuple(headers)
        self.rows = tuple(tuple(row) for row in rows)
        self.align = tuple(align) if align is not None else ()

    def _render(self, profile: Profile) -> str:
        if not self.headers or any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Table requires headers and rectangular rows")

        if self.align and len(self.align) != len(self.headers):
            raise ValueError("Alignment must have one entry per column")

        alignments = {"left": ":---", "center": ":---:", "right": "---:", "default": "---"}
        separators = [
            alignments[choice(value, set(alignments), "alignment")]
            for value in (self.align or ("default",) * len(self.headers))
        ]
        header = self._row(self.headers, profile)
        separator = "| " + " | ".join(separators) + " |"
        return "\n".join([header, separator, *(self._row(row, profile) for row in self.rows)])

    @staticmethod
    def _row(cells: tuple[Element | str, ...], profile: Profile) -> str:
        # GFM consumes one backslash before every pipe, before any inline syntax is parsed.
        values = [one_line(inline(cell, profile)).replace("|", r"\|") for cell in cells]
        return "| " + " | ".join(values) + " |"


class YFMTable(Element):
    _child_fields = ("rows",)

    def __init__(
        self,
        *rows: Row,
        header_rows: int = 0,
        wide: bool = False,
        sticky_header: bool = False,
        attributes: Attributes | None = None,
    ) -> None:
        self.rows = tuple(rows)
        self.header_rows = header_rows
        self.wide = wide
        self.sticky_header = sticky_header
        self.attributes = attributes

    def _render(self, profile: Profile) -> str:
        self._validate_shape()
        self._validate_spans()

        if not 0 <= self.header_rows <= len(self.rows):
            raise ValueError("header_rows must be between zero and the row count")

        if self.header_rows or self.wide or self.sticky_header:
            require(profile, "Extended table attributes", Profile.DIPLODOC)

        lines = ["#|"]

        if self.header_rows:
            lines.append(f'|:{{header-rows="{self.header_rows}"}}')

        if self.attributes is not None:
            require(profile, "Table attributes", Profile.DIPLODOC)
            lines.append("|:{" + self.attributes.to_yfm() + "}")

        lines.extend(row.to_yfm(profile=profile) for row in self.rows)

        flags = " ".join(
            flag
            for flag, enabled in ((TableFlag.WIDE, self.wide), (TableFlag.STICKY_HEADER, self.sticky_header))
            if enabled
        )
        lines.append("|#" + (f" {{{flags}}}" if flags else ""))

        return "\n".join(lines)

    def _validate_shape(self) -> None:
        if not self.rows or any(not isinstance(row, Row) for row in self.rows):
            raise ValueError("YFMTable requires Row elements")

        width = len(self.rows[0].cells)

        if not width or any(len(row.cells) != width for row in self.rows):
            raise ValueError("YFMTable requires nonempty rectangular rows")

    def _validate_spans(self) -> None:
        owners: list[list[tuple[int, int]]] = []
        areas: dict[tuple[int, int], list[tuple[int, int]]] = {}

        for row_index, row in enumerate(self.rows):
            owners.append([])

            for column_index, cell in enumerate(row.cells):
                owner = self._span_owner(cell, row_index, column_index, owners)
                owners[-1].append(owner)
                areas.setdefault(owner, []).append((row_index, column_index))

        for (top, left), coordinates in areas.items():
            bottom = max(row for row, _column in coordinates)
            right = max(column for _row, column in coordinates)

            if len(coordinates) != (bottom - top + 1) * (right - left + 1):
                raise ValueError(f"Span at row {top + 1}, column {left + 1} must form a complete rectangle")

    @staticmethod
    def _span_owner(
        cell: Element | str, row: int, column: int, owners: list[list[tuple[int, int]]]
    ) -> tuple[int, int]:
        if not isinstance(cell, Span):
            return row, column

        if cell == Span.LEFT:
            if column == 0:
                raise ValueError("Span.LEFT requires a preceding column")

            return owners[row][column - 1]

        if row == 0:
            raise ValueError("Span.ABOVE requires a preceding row")

        owner = owners[row - 1][column]

        if owner[1] != column:
            raise ValueError("Span.ABOVE must continue the leftmost column; use Span.LEFT for the remaining columns")

        return owner
