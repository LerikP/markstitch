"""Integration checks against pinned Diplodoc, not a claim about Tracker's deployment."""

import json
import subprocess
from collections.abc import Callable
from html import unescape
from pathlib import Path
from typing import Any

import pytest

from markstitch import (
    YFM,
    Attributes,
    Bold,
    BulletList,
    Cell,
    Code,
    CodeBlock,
    Cut,
    Element,
    Header3,
    Image,
    InlineFor,
    InlineIf,
    Link,
    Note,
    NumberedList,
    Paragraph,
    Row,
    Slice,
    Span,
    Tab,
    Table,
    Tabs,
    Text,
    Variable,
    YFMTable,
    parse,
)

pytestmark = pytest.mark.renderer


def test_document_renders_as_structured_html() -> None:
    document = YFM(Header3("Test1"), NumberedList("One", "Two", "Three"), Link("link", "https://example.com"))

    output = render(document)

    assert output["logs"]["error"] == []
    assert '<h3 id="test1">' in output["result"]["html"]
    assert "<ol>" in output["result"]["html"]
    assert output["result"]["html"].count("<li>") == 3
    assert 'href="https://example.com"' in output["result"]["html"]


def test_nested_directives_are_recognized() -> None:
    document = YFM(Tabs(Tab("One", Cut("Details", Note("Body", kind="tip"))), Tab("Two", "Other")))

    output = render(document)

    assert output["logs"]["error"] == []
    assert "yfm-tabs" in output["result"]["html"]
    assert "yfm-cut" in output["result"]["html"]
    assert "yfm-note" in output["result"]["html"]
    assert "{%" not in output["result"]["html"]


def test_table_preserves_pipes_and_code() -> None:
    document = Table(["Name", "Code"], [["a|b", Code("x|y")]])

    output = render(document)

    assert "<td>a|b</td>" in output["result"]["html"]
    assert ">x|y</code>" in output["result"]["html"]
    assert output["result"]["html"].count("<td>") == 2


@pytest.mark.parametrize("text", ["a|b", r"a\|b", r"a\\|b", r"a\\\|b", r"`a\|b`", r"a``\|b", r"\|\|"])
@pytest.mark.parametrize("factory", [Code, lambda text: Bold(Code(text))], ids=["code", "bold-code"])
def test_table_code_preserves_backslashes_before_pipes(text: str, factory: Callable[[str], Element]) -> None:
    document = Table([factory(text)], [[factory(text)]])

    output = render(document)

    html = unescape(output["result"]["html"])
    assert html.count(f">{text}</code>") == 2
    assert html.count("<th>") == 1
    assert html.count("<td>") == 1


def test_multiline_table_contains_blocks() -> None:
    document = YFMTable(Row("Title", Cell(BulletList("a", "b"), CodeBlock("print(1)", language="python"))))

    output = render(document)

    assert output["logs"]["error"] == []
    assert "<table" in output["result"]["html"]
    assert "<ul>" in output["result"]["html"]
    assert "<pre" in output["result"]["html"]
    assert "#|" not in output["result"]["html"]


@pytest.mark.parametrize("text", ["*literal*", "<script>alert(1)</script>", "{% cut evil %}", "{{ name }}"])
def test_plain_text_cannot_create_markup(text: str) -> None:
    document = Paragraph(text)

    output = render(document)

    assert "<em>" not in output["result"]["html"]
    assert "<script>" not in output["result"]["html"]
    assert "yfm-cut" not in output["result"]["html"]


@pytest.mark.parametrize(
    "parts",
    [("1", ". item"), (Text("1"), Text(".", " item")), ("before\n", Text("12"), ".", " item")],
)
def test_adjacent_text_fragments_cannot_create_list(parts: tuple[Element | str, ...]) -> None:
    document = Paragraph(*parts)

    output = render(document)

    assert "<ol>" not in output["result"]["html"]
    assert "<li>" not in output["result"]["html"]
    assert ". item" in output["result"]["html"]


@pytest.mark.parametrize("text", [" padded ", "SELECT `id`", "`ticks`", "   "])
def test_code_text_survives_rendering(text: str) -> None:
    element = Paragraph(Code(text))

    output = render(element)

    assert f">{text}</code>" in unescape(output["result"]["html"])


@pytest.mark.parametrize("title", ['A "quoted" title', r"a\b", r"a\\b", "tail\\"])
def test_quoted_title_survives_rendering(title: str) -> None:
    element = Cut(title, "body")

    output = render(element)

    assert title in unescape(output["result"]["html"])


def test_alignment_of_multiline_cell() -> None:
    element = YFMTable(Row(Cell(BulletList("one", "two"), align="center")))

    output = render(element, profile="diplodoc")

    assert "cell-align-center" in output["result"]["html"]
    assert "<ul>" in output["result"]["html"]
    assert "::{" not in output["result"]["html"]


def test_table_attributes_are_parsed_at_correct_levels() -> None:
    element = YFMTable(
        Row(
            Cell(BulletList("one", "two"), align="center", attributes=Attributes(style={"width": "300px"})),
            attributes=Attributes(classes=("summary",)),
        ),
        attributes=Attributes(id="report"),
    )

    output = render(element, profile="diplodoc")

    assert output["tableAttributes"] == [
        {"type": "yfm_table_open", "attributes": {"id": "report"}},
        {"type": "yfm_tr_open", "attributes": {"class": "summary"}},
        {"type": "yfm_td_open", "attributes": {"align": "center", "style": "width: 300px"}},
    ]
    assert "<ul>" in output["result"]["html"]
    assert "::{" not in output["result"]["html"]


def test_combined_spans_render_without_overlapping_cells() -> None:
    element = YFMTable(Row("a", Span.LEFT, "b"), Row(Span.ABOVE, Span.LEFT, Span.ABOVE), Row("c", "d", Span.ABOVE))

    output = render(element, profile="diplodoc")

    assert 'colspan="2" rowspan="2"' in output["result"]["html"]
    assert 'rowspan="3"' in output["result"]["html"]
    assert output["result"]["html"].count("<td") == 4


def test_svg_remains_an_image_with_inlining_disabled() -> None:
    element = Image("icon.svg", inline=False)

    output = render(element, profile="diplodoc")

    assert '<img src="icon.svg"' in output["result"]["html"]
    assert "<svg" not in output["result"]["html"]


@pytest.mark.parametrize(("admin", "expected"), [(True, "<strong>admin</strong>"), (False, "guest")])
def test_inline_templates_execute_in_diplodoc(admin: bool, expected: str) -> None:
    element = Paragraph(
        "Hello ",
        InlineIf("user.admin == true", Bold("admin"), otherwise="guest"),
        ": ",
        InlineFor("item", "items", Variable(Slice("item.name", 1)), "; "),
    )

    output = render(
        element,
        profile="diplodoc",
        options={
            "disableLiquid": False,
            "vars": {"user": {"admin": admin}, "items": [{"name": "Alice"}, {"name": "Bob"}]},
        },
    )

    assert output["logs"]["error"] == []
    # Diplodoc's Liquid implementation strips whitespace around the loop body.
    assert f"Hello {expected}: lice;ob;" in output["result"]["html"]
    assert "{%" not in output["result"]["html"]


def test_chained_slice_and_filter_execute_in_diplodoc() -> None:
    element = Paragraph("Count: ", Variable(Slice(Slice("names", 1), 0, 2), filters=("length",)))

    output = render(
        element,
        profile="diplodoc",
        options={
            "disableLiquid": False,
            "vars": {"names": ["Alice", "Bob", "Carol", "Dave"]},
        },
    )

    assert output["logs"]["error"] == []
    assert output["result"]["html"] == "<p>Count: 2</p>\n"


def test_parsed_and_edited_document_renders_nested_content() -> None:
    source = '## Report\n\n{% cut "Details" %}\n\n{% note tip %}\n\n**[old](/old)**\n\n{% endnote %}\n\n{% endcut %}'
    document = parse(source, strict=True)
    link = next(node for node in document.walk() if isinstance(node, Link))
    link.text, link.href = "new", "/new"

    output = render(document)

    assert output["logs"]["error"] == []
    assert 'href="/new"' in output["result"]["html"]
    assert 'href="/old"' not in output["result"]["html"]
    assert "yfm-cut" in output["result"]["html"]
    assert "yfm-note" in output["result"]["html"]


def test_parsed_merged_table_renders_structure() -> None:
    document = parse("#|\n|| wide | > ||\n|| ^ | > ||\n|#", profile="diplodoc", strict=True)

    output = render(document, profile="diplodoc")

    assert 'colspan="2" rowspan="2"' in output["result"]["html"]
    assert output["result"]["html"].count("<td") == 1


def test_parsed_inline_templates_execute_in_diplodoc() -> None:
    document = parse(
        "Hello {% if admin == true %}**admin**{% else %}guest{% endif %}", profile="diplodoc", strict=True
    )

    output = render(document, profile="diplodoc", options={"disableLiquid": False, "vars": {"admin": True}})

    assert output["result"]["html"] == "<p>Hello <strong>admin</strong></p>\n"


@pytest.mark.parametrize(
    ("wide", "opening"),
    [(False, '<table sticky-header="true">'), (True, '<table wide-content="true" sticky-header="true">')],
)
def test_sticky_header_does_not_create_extra_paragraph(wide: bool, opening: str) -> None:
    table = YFMTable(Row("header"), Row("body"), sticky_header=True, wide=wide)

    output = render(table, profile="diplodoc")

    assert output["logs"]["error"] == []
    assert opening in output["result"]["html"]
    assert output["result"]["html"].count("<p") == 2


def test_parsed_image_alt_renders_as_plain_text() -> None:
    document = parse("![**foo** `bar`](/img =120x80)", strict=True)

    output = render(document)

    assert output["logs"]["error"] == []
    assert 'alt="foo bar"' in output["result"]["html"]


def test_reference_label_with_spaces_renders_link() -> None:
    document = parse("[site][foo bar]\n\n[foo bar]: /url", strict=True)

    output = render(document)

    assert output["logs"]["error"] == []
    assert 'href="/url"' in output["result"]["html"]
    assert ">site</a>" in output["result"]["html"]


@pytest.mark.parametrize(
    ("href", "expected"),
    [("javascript&colon;alert(1)", "javascript%26colon;alert%281%29"), ("/path?name=&copy;", "/path?name=%26copy;")],
)
def test_renderer_preserves_entity_like_url(href: str, expected: str) -> None:
    document = Link("link", href)

    output = render(document)

    assert f'href="{expected}"' in output["result"]["html"]
    assert ">link</a>" in output["result"]["html"]


def render(element: Element, *, profile: str = "tracker", options: dict[str, Any] | None = None) -> dict[str, Any]:
    # Fixed local test runner; the generated source is sent over stdin, never through a shell.
    completed = subprocess.run(  # noqa: S603
        ["node", f"{Path(__file__).with_name('render.cjs')}"],  # noqa: S607
        input=json.dumps({"source": element.to_yfm(profile=profile), "options": options or {}}),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    return json.loads(completed.stdout)
