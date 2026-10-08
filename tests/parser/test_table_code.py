import pytest

from markstitch import Bold, Code, InlineIf, Math, RawInline, Table, Text, parse


@pytest.mark.parametrize("text", ["a|b", r"a\|b", r"a\\|b", r"a\\\|b", r"`a\|b`", r"a``\|b", r"\|\|"])
def test_table_code_keeps_text_through_roundtrip(text: str) -> None:
    source = Table([Code(text)], [[Bold(Code(text))]]).to_yfm()

    document = parse(source, strict=True)

    assert [node.text for node in document.walk() if isinstance(node, Code)] == [text, text]
    assert document.to_yfm() == source


def test_table_distinguishes_plain_escaped_backticks_from_code() -> None:
    text = r"`a\|b`"
    source = Table(["plain", "code"], [[Text(text), Code(text)]]).to_yfm()

    document = parse(source, strict=True)

    assert [node.text for node in document.walk() if isinstance(node, Code)] == [text]
    table = document.children[0]
    assert isinstance(table, Table)
    assert table.rows[0][0].to_yfm() == Text(text).to_yfm()
    assert document.to_yfm() == source


def test_table_handles_multiple_code_delimiters_in_one_cell() -> None:
    cell = Text("plain ` | ", Code(r"a\|b"), " / ", Code(r"`c\|d`"), " | tail")
    source = Table(["h"], [[cell]]).to_yfm()

    document = parse(source, strict=True)

    assert [node.text for node in document.walk() if isinstance(node, Code)] == [r"a\|b", r"`c\|d`"]
    assert document.to_yfm() == source


@pytest.mark.parametrize("text", [r"\|x\|", r"a\|b", r"a\\|b", r"a\\\|b", "a|b"])
@pytest.mark.parametrize("profile", ["tracker", "wiki", "diplodoc"])
def test_table_math_keeps_literal_backslashes(text: str, profile: str) -> None:
    source = Table([Math(text)], [[Bold(Math(text))]]).to_yfm(profile=profile)

    document = parse(source, profile=profile, strict=True)

    assert [node.text for node in document.walk() if isinstance(node, Math)] == [text, text]
    assert document.to_yfm() == source


def test_table_raw_inline_retains_literal_math() -> None:
    source = Table(["h"], [[RawInline(r"$\|x\|$")]]).to_yfm()

    document = parse(source, strict=True)

    assert [node.text for node in document.walk() if isinstance(node, Math)] == [r"\|x\|"]
    assert document.to_yfm() == source


def test_table_template_keeps_literal_condition() -> None:
    expression = r'value == "a\|b"'
    source = Table(["h"], [[InlineIf(expression, "yes", otherwise="no")]]).to_yfm(profile="diplodoc")

    document = parse(source, profile="diplodoc", strict=True)

    assert [node.expression for node in document.walk() if isinstance(node, InlineIf)] == [expression]
    assert document.to_yfm() == source
