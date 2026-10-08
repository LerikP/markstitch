import pytest

from markstitch import (
    YFM,
    Bold,
    Cell,
    Cut,
    Heading,
    Image,
    InlineIf,
    Link,
    Paragraph,
    Row,
    Table,
    Text,
    YFMTable,
)


def test_iteration_returns_direct_children_only() -> None:
    heading = Heading("title")
    paragraph = Paragraph("hello ", Bold("world"))
    document = YFM(heading, paragraph)

    result = list(document)

    assert result == [heading, paragraph]


def test_walk_visits_inline_labels_tables_and_otherwise_in_source_order() -> None:
    document = YFM(
        Heading(Bold("title")),
        Cut("details", YFMTable(Row(Cell(Paragraph(Link(Image("image.svg"), "/page")))))),
        Paragraph(InlineIf("enabled", Text("yes"), otherwise=Bold("no"))),
    )

    result = [type(node).__name__ for node in document.walk()]

    assert result == [
        "YFM",
        "Heading",
        "Bold",
        "Cut",
        "YFMTable",
        "Row",
        "Cell",
        "Paragraph",
        "Link",
        "Image",
        "Paragraph",
        "InlineIf",
        "Text",
        "Bold",
    ]


def test_simple_table_walk_includes_headers_and_cells() -> None:
    table = Table([Bold("header")], [[Link("site", "/")]])

    result = [type(node).__name__ for node in table.walk()]

    assert result == ["Table", "Bold", "Link"]


def test_walk_returns_original_nodes_for_editing() -> None:
    link = Link("old", "/old")
    document = YFM(Paragraph(link))

    found = next(node for node in document.walk() if isinstance(node, Link))

    assert found is link


def test_walk_visits_reused_nodes_at_each_occurrence() -> None:
    shared = Bold("shared")
    document = YFM(Paragraph(shared), Paragraph(shared))

    result = [node for node in document.walk() if isinstance(node, Bold)]

    assert result == [shared, shared]


def test_walk_rejects_cycles() -> None:
    document = YFM()
    document.children = (document,)

    with pytest.raises(ValueError, match=r"[Cc]ycle"):
        list(document.walk())


def test_row_is_a_renderable_tree_node() -> None:
    row = Row(Cell(Bold("title")), "value")

    result = row.to_yfm()

    assert result == "|| **title** | value ||"
