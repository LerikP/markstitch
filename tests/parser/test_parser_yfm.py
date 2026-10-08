import pytest

from markstitch import (
    YFM,
    Attributes,
    Bold,
    Cell,
    Checklist,
    CodeBlock,
    Color,
    Cut,
    Element,
    File,
    Footnote,
    FootnoteDefinition,
    Grid,
    Heading,
    Highlight,
    If,
    Image,
    Include,
    InlineFor,
    InlineIf,
    Link,
    Math,
    MathBlock,
    Mention,
    Monospace,
    Note,
    Paragraph,
    ParseError,
    Quote,
    Raw,
    RawHTML,
    RawInline,
    Row,
    Slice,
    Span,
    StyledBlock,
    Subscript,
    Superscript,
    Table,
    Tabs,
    Term,
    TermDefinition,
    Toc,
    Underline,
    Variable,
    Visibility,
    WikiInclude,
    YFMTable,
    parse,
)


@pytest.mark.parametrize(
    ("source", "node_type", "profile"),
    [
        ('{% cut "Details" %}\n\n**body**\n\n{% endcut %}', Cut, "tracker"),
        ('{% note warning "Title" %}\n\nbody\n\n{% endnote %}', Note, "tracker"),
        ("{% list tabs %}\n\n- First\n\n  content\n\n- Second\n\n  other\n\n{% endlist %}", Tabs, "tracker"),
        ("##+ Title {#title}", Heading, "tracker"),
        ("[x] Done\n\n[ ] Next", Checklist, "tracker"),
        ("$$\nx^2\n$$", MathBlock, "tracker"),
        ('{% file src="/a.zip" name="Archive" %}', File, "tracker"),
        ("{% block align=center %}\n\nbody\n\n{% endblock %}", StyledBlock, "tracker"),
        ('{% toc from="h2" to="h4" %}', Toc, "wiki"),
        ('{% include page="/docs" warning="true" %}', WikiInclude, "wiki"),
        ('{% wgrid id="grid" readonly="1" num="1" sort="case" %}', Grid, "wiki"),
        ("{% include notitle [Page](_includes/page.md) %}", Include, "diplodoc"),
        ("::: html\n\n<p>trusted</p>\n\n:::", RawHTML, "wiki"),
        (":::visibility agent\nInstructions\n:::", Visibility, "diplodoc"),
    ],
)
def test_yfm_block_tree_and_roundtrip(source: str, node_type: type[Element], profile: str) -> None:
    document = parse(source, profile=profile, strict=True)

    assert isinstance(next(iter(document)), node_type)
    assert document.to_yfm() == source


@pytest.mark.parametrize(
    "element",
    [
        Underline("text"),
        Highlight("text"),
        Monospace("text"),
        Superscript("2"),
        Subscript("2"),
        Color(Bold("OK"), color="green"),
        Math("x^2"),
        Mention("example-user"),
        Image("icon.svg", width=40, title="Icon"),
    ],
)
def test_yfm_inline_tree_and_roundtrip(element: Element) -> None:
    source = element.to_yfm()

    document = parse(source, strict=True)

    assert any(isinstance(node, type(element)) for node in document.walk())
    assert document.to_yfm() == source


def test_nested_directives_ignore_markers_inside_code() -> None:
    source = YFM(Cut("outer", CodeBlock("{% endcut %}", language="text"), Note(Cut("inner", "body")))).to_yfm()

    document = parse(source, strict=True)

    assert [node.title for node in document.walk() if isinstance(node, Cut)] == ["outer", "inner"]
    assert document.to_yfm() == source


def test_simple_table_has_editable_inline_cells() -> None:
    source = "| Name | Value |\n| :--- | ---: |\n| **key** | [value](/value) |"

    document = parse(source, strict=True)

    assert isinstance(next(iter(document)), Table)
    assert len([node for node in document.walk() if isinstance(node, Link)]) == 1
    assert document.to_yfm() == source


def test_multiline_table_with_nested_table_and_code() -> None:
    source = YFMTable(
        Row("header", "body"), Row(Cell(YFMTable(Row("a", "b"))), Cell(CodeBlock("a | b\n#|", language="text")))
    ).to_yfm()

    document = parse(source, strict=True)

    assert len([node for node in document.walk() if isinstance(node, YFMTable)]) == 2
    assert document.to_yfm() == source


def test_diplodoc_table_attributes_and_spans_roundtrip() -> None:
    source = YFMTable(
        Row(
            Cell("title", align="center", attributes=Attributes(classes=("cell",))),
            Span.LEFT,
            attributes=Attributes(classes=("row",)),
        ),
        Row(Span.ABOVE, Span.LEFT),
        header_rows=1,
        wide=True,
        attributes=Attributes(id="report"),
    ).to_yfm(profile="diplodoc")

    document = parse(source, profile="diplodoc", strict=True)

    assert isinstance(next(iter(document)), YFMTable)
    assert document.to_yfm() == source


@pytest.mark.parametrize(
    "groups", ["|:{id=first}\n|:{id=second}", "|:{id=same}\n|:{id=same}", "|:{header-rows=0}\n|:{header-rows=1}"]
)
def test_duplicate_table_attribute_groups_are_rejected(groups: str) -> None:
    with pytest.raises(ParseError, match="unique table attributes"):
        parse(f"#|\n{groups}\n|| x ||\n|#", profile="diplodoc", strict=True)


@pytest.mark.parametrize("groups", ["|:{id=first}\n|:{id=second}", "|:{header-rows=0}\n|:{header-rows=1}"])
def test_duplicate_table_attribute_groups_are_preserved(groups: str) -> None:
    source = f"#|\n{groups}\n|| x ||\n|#"

    document = parse(source, profile="diplodoc")

    assert isinstance(document.children[0], Raw)
    assert document.to_yfm() == source


def test_disjoint_table_attribute_groups_are_combined() -> None:
    document = parse("#|\n|:{id=report}\n|:{header-rows=1}\n|| x ||\n|#", profile="diplodoc", strict=True)

    table = document.children[0]
    assert isinstance(table, YFMTable)
    assert table.header_rows == 1
    assert table.attributes == Attributes(id="report")


@pytest.mark.parametrize(
    "element",
    [
        Paragraph(InlineIf("enabled", Bold("yes"), otherwise="no"), InlineFor("user", "users", Variable("user.name"))),
        If("enabled", "yes", otherwise="no"),
        Paragraph(Variable(Slice("user.name", 1, 3), filters=("length",))),
        Paragraph(Term("word", "term")),
        TermDefinition("term", "meaning"),
        FootnoteDefinition("note", "description"),
        Paragraph(Footnote("note")),
        Image("icon.svg", inline=False),
    ],
)
def test_diplodoc_extensions_roundtrip(element: Element) -> None:
    source = element.to_yfm(profile="diplodoc")

    document = parse(source, profile="diplodoc", strict=True)

    assert not any(isinstance(node, (Raw, RawInline)) for node in document.walk())
    assert document.to_yfm() == source


@pytest.mark.parametrize(
    "text",
    [
        "**literal**",
        'A "quoted" title',
        "{% if enabled %}",
        "{{ name }}",
        "a|b",
        "a [b](c)",
        "&amp;",
        "<script>",
    ],
)
def test_escaped_data_survives_roundtrip_in_multiple_contexts(text: str) -> None:
    source = YFM(Heading(text), Cut(text, Paragraph(Bold(text), Link(text, "/page")), CodeBlock(text))).to_yfm()

    document = parse(source, strict=True)

    assert document.to_yfm() == source


@pytest.mark.parametrize(
    "element",
    [
        Quote(Cut("Details", "body")),
        Note(YFMTable(Row("a", "b"))),
        Cut("outer", Quote(Note("body"))),
    ],
)
def test_nested_block_contexts_roundtrip(element: Element) -> None:
    source = element.to_yfm()

    document = parse(source, strict=True)

    assert document.to_yfm() == source


@pytest.mark.parametrize("wide", [False, True])
def test_sticky_header_survives_table_roundtrip(wide: bool) -> None:
    source = YFMTable(Row("header"), Row("body"), sticky_header=True, wide=wide).to_yfm(profile="diplodoc")

    document = parse(source, profile="diplodoc", strict=True)

    assert len(list(document)) == 1
    table = next(iter(document))
    assert isinstance(table, YFMTable)
    assert table.sticky_header is True
    assert table.wide is wide
    assert document.to_yfm() == source


@pytest.mark.parametrize("suffix", ["{wide-content sticky-header}", "{wide-content} {sticky-header}"])
def test_combined_table_flags_are_normalized(suffix: str) -> None:
    document = parse(f"#|\n|| header ||\n|# {suffix}", profile="diplodoc", strict=True)

    table = next(iter(document))
    assert isinstance(table, YFMTable)
    assert table.wide is True
    assert table.sticky_header is True
    assert document.to_yfm() == "#|\n|| header ||\n|# {wide-content sticky-header}"
