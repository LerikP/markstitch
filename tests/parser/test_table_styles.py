import pytest

from markstitch import Cell, ParseError, Raw, Row, YFMTable, parse

TABLE_TEMPLATES = (
    '#|\n|:{style="STYLE"}\n|| x ||\n|#',
    '#|\n||:{style="STYLE"} x ||\n|#',
    '#|\n|| ::{style="STYLE"} x ||\n|#',
)
DUPLICATE_STYLES = (
    "color: red; color: blue",
    "color: red; color: red",
    " color : red ;color: blue",
    "--tone: red; --tone: blue",
)


@pytest.mark.parametrize("template", TABLE_TEMPLATES, ids=["table", "row", "cell"])
@pytest.mark.parametrize("style", DUPLICATE_STYLES)
def test_duplicate_css_declarations_are_rejected(template: str, style: str) -> None:
    source = template.replace("STYLE", style)

    with pytest.raises(ParseError, match="unique CSS declarations"):
        parse(source, profile="diplodoc", strict=True)


@pytest.mark.parametrize("template", TABLE_TEMPLATES, ids=["table", "row", "cell"])
@pytest.mark.parametrize("style", DUPLICATE_STYLES)
def test_duplicate_css_declarations_preserve_original_table(template: str, style: str) -> None:
    source = template.replace("STYLE", style)

    document = parse(source, profile="diplodoc")

    assert isinstance(document.children[0], Raw)
    assert document.to_yfm() == source


@pytest.mark.parametrize("template", TABLE_TEMPLATES, ids=["table", "row", "cell"])
def test_distinct_css_declarations_remain_editable(template: str) -> None:
    source = template.replace("STYLE", " color : red ; width: 10px;")

    document = parse(source, profile="diplodoc", strict=True)

    styles = [
        node.attributes.style
        for node in document.walk()
        if isinstance(node, (YFMTable, Row, Cell)) and node.attributes is not None
    ]
    assert styles == [{"color": "red", "width": "10px"}]
