import pytest

from markstitch import (
    YFM,
    Bold,
    Code,
    CodeBlock,
    Heading,
    Italic,
    Link,
    NumberedList,
    Paragraph,
    ParseError,
    Raw,
    Text,
    parse,
)


def test_parse_requested_example_into_typed_tree() -> None:
    source = "### Test1\n\n1. One\n2. Two\n3. Three\n\n[link](example.com)"

    document = parse(source)

    assert [type(node) for node in document] == [Heading, NumberedList, Paragraph]
    assert next(node for node in document.walk() if isinstance(node, Heading)).text.to_yfm() == "Test1"
    assert next(node for node in document.walk() if isinstance(node, Link)).href == "example.com"
    assert document.to_yfm() == source


def test_parsed_tree_is_editable() -> None:
    document = parse("See **[old](/old)**")
    link = next(node for node in document.walk() if isinstance(node, Link))
    link.href = "/new"
    link.text = "new"

    result = document.to_yfm()

    assert result == "See **[new](/new)**"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Hello **bold _italic_**", [YFM, Paragraph, Text, Bold, Text, Italic, Text]),
        ("`**literal**`", [YFM, Paragraph, Code]),
        ("```python\n{% cut not-a-block %}\n```", [YFM, CodeBlock]),
    ],
)
def test_standard_markdown_tree(source: str, expected: list[type]) -> None:
    document = parse(source)

    assert [type(node) for node in document.walk()] == expected


def test_unknown_block_is_preserved() -> None:
    source = '{% future key="value" %}\n\n**body**\n\n{% endfuture %}'

    document = parse(source)

    assert isinstance(next(iter(document)), Raw)
    assert document.to_yfm() == source


def test_strict_mode_reports_unsupported_source() -> None:
    with pytest.raises(ParseError, match="line 1"):
        parse("{% future %}\n\nbody\n\n{% endfuture %}", strict=True)


def test_document_classmethod_preserves_profile() -> None:
    document = YFM.from_yfm("text", profile="wiki")

    assert document.profile == "wiki"
    assert document.to_yfm() == "text"
