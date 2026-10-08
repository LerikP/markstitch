import pytest

from markstitch import BulletList, Element, NumberedList, ParseError, Quote, Raw, RawInline, parse


@pytest.mark.parametrize(
    ("source", "container"),
    [
        ("> {{ unsupported() }}", Quote),
        ("- {{ unsupported() }}", BulletList),
        ("1. {{ unsupported() }}", NumberedList),
        ("> - {{ unsupported() }}", Quote),
        ("- > {{ unsupported() }}", BulletList),
        ("> ## {{ unsupported() }}", Quote),
        ("> before [link](/url){future=value} after", Quote),
        ("- known\n- {{ unsupported() }}", BulletList),
        ("> :smile:", Quote),
    ],
)
def test_inline_fallback_preserves_parent_structure(source: str, container: type[Element]) -> None:
    document = parse(source, profile="diplodoc")

    assert isinstance(next(iter(document)), container)
    assert any(isinstance(node, RawInline) for node in document.walk())
    assert document.to_yfm() == source


@pytest.mark.parametrize("source", ["> {{ unsupported() }}", "- {{ unsupported() }}", "> :smile:"])
def test_nested_inline_failure_is_still_rejected_in_strict_mode(source: str) -> None:
    with pytest.raises(ParseError, match="line 1"):
        parse(source, profile="diplodoc", strict=True)


def test_inline_fallback_does_not_hide_depth_limit() -> None:
    source = "{% if enabled %}" * 70 + "text" + "{% endif %}" * 70

    with pytest.raises(ParseError, match="nesting"):
        parse(source, profile="diplodoc")


@pytest.mark.parametrize(
    ("source", "container"),
    [
        ("> {% future %}\n>\n> body\n>\n> {% endfuture %}", Quote),
        ("- {% future %}\n\n  body\n\n  {% endfuture %}", BulletList),
        ("1. {% future %}\n\n   body\n\n   {% endfuture %}", NumberedList),
        ("> - {% future %}\n>\n>   body\n>\n>   {% endfuture %}", Quote),
        ("> {% note invalid %}\n>\n> body\n>\n> {% endnote %}", Quote),
    ],
)
def test_block_fallback_preserves_parent_structure(source: str, container: type[Element]) -> None:
    document = parse(source, profile="diplodoc")

    assert document.to_yfm() == source
    assert isinstance(next(iter(document)), container)
    assert any(isinstance(node, Raw) for node in document.walk())


def test_nested_unknown_block_is_still_rejected_in_strict_mode() -> None:
    source = "> {% future %}\n>\n> body\n>\n> {% endfuture %}"

    with pytest.raises(ParseError, match="line 1"):
        parse(source, profile="diplodoc", strict=True)


@pytest.mark.parametrize("ending", ["", "\n"])
@pytest.mark.parametrize(
    "source",
    [
        "> <div>text</div>",
        "- <div>text</div>",
        "1. <div>text</div>",
        "> - <div>text</div>",
        "> <div>\n> text\n> </div>",
    ],
)
def test_html_fallback_preserves_parent_markers(source: str, ending: str) -> None:
    document = parse(source + ending)

    assert document.to_yfm() == source
    assert any(isinstance(node, Raw) for node in document.walk())


def test_nested_html_is_still_rejected_in_strict_mode() -> None:
    with pytest.raises(ParseError, match="Unsupported block: html_block"):
        parse("> <div>text</div>", strict=True)
