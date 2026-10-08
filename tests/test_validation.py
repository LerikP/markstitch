import pytest

from markstitch import Bold, Code, Color, Cut, Element, Header3, Heading, Link, Paragraph, Text


def test_plain_text_escapes_entities_and_block_markers() -> None:
    element = Text("1. item\n- item\n&amp;")

    result = element.to_yfm()

    assert result == "1\\. item\n\\- item\n&amp;amp;"


def test_inline_code_preserves_surrounding_spaces() -> None:
    element = Code(" padded ")

    result = element.to_yfm()

    assert result == "`  padded  `"


def test_plain_text_cannot_start_a_directive_container() -> None:
    element = Text(":::visibility agent\ncontent\n:::")

    result = element.to_yfm()

    assert result == "\\:\\:\\:visibility agent\ncontent\n\\:\\:\\:"


@pytest.mark.parametrize("container", [Text, Paragraph])
def test_plain_text_escapes_emoji_markers(container: type[Text] | type[Paragraph]) -> None:
    element = container("Before :smile: and :foo.bar: after")

    result = element.to_yfm()

    assert result == r"Before \:smile\: and \:foo.bar\: after"


@pytest.mark.parametrize(
    "element",
    [
        Header3("a\nb"),
        Heading("a", level=7),
        Link("a", "javascript:alert(1)"),
        Link("a", "tel:+123456789"),
        Link("a", "https://example.com\nother"),
        Color("x", "invalid"),
        Code(""),
    ],
)
def test_invalid_input_is_rejected(element: Element) -> None:
    with pytest.raises(ValueError):
        element.to_yfm()


def test_rejects_block_inside_inline() -> None:
    element = Paragraph(Bold(Cut("heading", "body")))

    with pytest.raises(TypeError, match="inline"):
        element.to_yfm()


@pytest.mark.parametrize(
    ("href", "encoded"),
    [
        ("javascript&colon;alert(1)", "javascript%26colon;alert%281%29"),
        ("javascript&#58;alert(1)", "javascript%26#58;alert%281%29"),
        ("javascript&#x3a;alert(1)", "javascript%26#x3a;alert%281%29"),
        ("javascript&#X3A;alert(1)", "javascript%26#X3A;alert%281%29"),
        ("/path?name=&copy;", "/path?name=%26copy;"),
        ("/path?name=&amp;copy;", "/path?name=%26amp;copy;"),
        ("/path?a=1&b=2", "/path?a=1&b=2"),
        ("/path?name=%26copy;", "/path?name=%26copy;"),
    ],
)
def test_url_entities_cannot_be_decoded_as_markup(href: str, encoded: str) -> None:
    link = Link("link", href)

    result = link.to_yfm()

    assert result == f"[link]({encoded})"
