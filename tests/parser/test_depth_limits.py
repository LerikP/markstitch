import pytest

from markstitch import Code, Image, ParseError, parse


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "source",
    ["> " * 70 + "LOST", "{{ users" + ".slice(0)" * 1100 + " }}"],
    ids=["commonmark-quotes", "slice-chain"],
)
def test_depth_limit_never_discards_content_or_leaks_recursion_error(source: str, strict: bool) -> None:
    with pytest.raises(ParseError, match="nesting"):
        parse(source, profile="diplodoc", strict=strict)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "source",
    [
        "![" * 70 + "text" + "](/img)" * 70,
        "![" * 70 + "text" + "][ref]" * 70 + "\n\n[ref]: /img",
        "![" + "*" * 140 + "text" + "*" * 140 + "](/img)",
        "*" * 2200 + "text" + "*" * 2200,
    ],
    ids=["nested-images", "nested-reference-images", "image-alt-emphasis", "deep-emphasis"],
)
def test_commonmark_inline_depth_cannot_be_silently_truncated(source: str, strict: bool) -> None:
    with pytest.raises(ParseError, match="nesting"):
        parse(source, strict=strict)


def test_nested_images_within_limit_keep_plain_alt() -> None:
    source = "![" * 20 + "text" + "](/img)" * 20

    document = parse(source, strict=True)

    assert [node.alt for node in document.walk() if isinstance(node, Image)] == ["text"]


def test_brackets_in_code_are_not_inline_nesting() -> None:
    text = "![" * 70 + "literal"

    document = parse(f"`{text}`", strict=True)

    assert [node.text for node in document.walk() if isinstance(node, Code)] == [text]
