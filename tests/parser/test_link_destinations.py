import pytest

from markstitch import Image, Link, LinkDefinition, ParseError, RawInline, Term, parse


@pytest.mark.parametrize(("prefix", "node_type", "field"), [("", Link, "href"), ("!", Image, "src")])
@pytest.mark.parametrize(
    ("url", "encoded"),
    [
        ("https://example.com", "https://example.com"),
        ("https://example.com/a b", "https://example.com/a%20b"),
        ("https://example.com/a)b(", "https://example.com/a%29b%28"),
    ],
)
def test_angle_destination_preserves_address(
    prefix: str, node_type: type[Link] | type[Image], field: str, url: str, encoded: str
) -> None:
    document = parse(f"{prefix}[site](<{url}>)", strict=True)

    node = next(node for node in document.walk() if isinstance(node, node_type))
    assert getattr(node, field) == url
    assert node.title is None
    assert document.to_yfm() == f"{prefix}[site]({encoded})"


def test_angle_link_keeps_title_and_target() -> None:
    document = parse('[site](<https://example.com/a b> "Title ) ("){target=_blank}', profile="diplodoc", strict=True)

    link = next(node for node in document.walk() if isinstance(node, Link))
    assert link.href == "https://example.com/a b"
    assert link.title == "Title ) ("
    assert link.target == "_blank"
    assert document.to_yfm() == '[site](https://example.com/a%20b "Title ) ("){target=_blank}'


@pytest.mark.parametrize("options", ['=120x80 "Icon"', '"Icon" =120x80'])
def test_angle_image_keeps_dimensions_and_title(options: str) -> None:
    document = parse(f"![icon](</image folder/icon.png> {options})", strict=True)

    image = next(node for node in document.walk() if isinstance(node, Image))
    assert image.src == "/image folder/icon.png"
    assert image.title == "Icon"
    assert (image.width, image.height) == (120, 80)
    assert document.to_yfm() == '![icon](/image%20folder/icon.png "Icon" =120x80)'


@pytest.mark.parametrize("prefix", ["", "!"])
def test_angle_destination_still_rejects_unsafe_schemes(prefix: str) -> None:
    with pytest.raises(ParseError, match="Unsupported URL scheme"):
        parse(f"{prefix}[site](<javascript:alert(1)>)", strict=True)


@pytest.mark.parametrize("dimensions", ["=120x80", "=120x", "=x80"])
def test_link_rejects_image_dimensions_in_strict_mode(dimensions: str) -> None:
    with pytest.raises(ParseError, match="Unknown link attributes"):
        parse(f"[text](/url {dimensions})", strict=True)


@pytest.mark.parametrize("dimensions", ["=120x80", "=120x", "=x80"])
def test_link_with_image_dimensions_is_preserved(dimensions: str) -> None:
    source = f"before [text](/url {dimensions}) after"

    document = parse(source)

    assert document.to_yfm() == source
    assert any(isinstance(node, RawInline) for node in document.walk())


def test_image_dimensions_remain_supported() -> None:
    document = parse("![text](/url =120x80)", strict=True)

    image = next(node for node in document.walk() if isinstance(node, Image))
    assert (image.width, image.height) == (120, 80)
    assert document.to_yfm() == "![text](/url =120x80)"


@pytest.mark.parametrize(
    "source",
    [
        '[word](*term "ignored")',
        "[word](*term =120x80)",
        "[word](*term){target=_blank}",
        '[word](*term "ignored"){target=_blank}',
    ],
)
def test_term_rejects_additional_arguments(source: str) -> None:
    with pytest.raises(ParseError, match="Unknown term attributes"):
        parse(source, profile="diplodoc", strict=True)


@pytest.mark.parametrize(
    "source",
    ['[word](*term "ignored")', "[word](*term =120x80)", "[word](*term){target=_blank}"],
)
def test_term_with_additional_arguments_is_preserved(source: str) -> None:
    document = parse(source, profile="diplodoc")

    assert document.to_yfm() == source
    assert any(isinstance(node, RawInline) for node in document.walk())


def test_term_without_additional_arguments_remains_editable() -> None:
    document = parse("[word](*term)", profile="diplodoc", strict=True)

    term = next(node for node in document.walk() if isinstance(node, Term))
    assert term.label == "term"
    assert document.to_yfm() == "[word](*term)"


@pytest.mark.parametrize("options", ["=x", "=10x20 =30x40", "=10x =x20", '=10x20 "Title" =30x40'])
def test_image_rejects_empty_or_repeated_dimensions(options: str) -> None:
    with pytest.raises(ParseError, match="Invalid image dimensions"):
        parse(f"![image](/img {options})", strict=True)


@pytest.mark.parametrize("options", ["=x", "=10x20 =30x40", "=10x =x20"])
def test_invalid_image_dimensions_are_preserved(options: str) -> None:
    source = f"![image](/img {options})"

    document = parse(source)

    assert document.to_yfm() == source
    assert any(isinstance(node, RawInline) for node in document.walk())


@pytest.mark.parametrize(
    ("dimensions", "width", "height"),
    [("=10x20", 10, 20), ("=10x", 10, None), ("=x20", None, 20)],
)
def test_single_nonempty_image_dimensions_remain_supported(
    dimensions: str, width: int | None, height: int | None
) -> None:
    document = parse(f"![image](/img {dimensions})", strict=True)

    image = next(node for node in document.walk() if isinstance(node, Image))
    assert (image.width, image.height) == (width, height)
    assert document.to_yfm() == f"![image](/img {dimensions})"


@pytest.mark.parametrize(("prefix", "node_type"), [("", Link), ("!", Image)])
@pytest.mark.parametrize("title", ["=10x20", "=hello", ""])
def test_quoted_titles_are_not_dimension_arguments(
    prefix: str, node_type: type[Link] | type[Image], title: str
) -> None:
    source = f'{prefix}[x](/url "{title}")'

    document = parse(source, strict=True)

    node = next(node for node in document.walk() if isinstance(node, node_type))
    assert node.title == title
    assert document.to_yfm() == source


@pytest.mark.parametrize("attributes", ["width=30 height=40", "width=10", "height=20"])
def test_conflicting_image_dimensions_are_rejected(attributes: str) -> None:
    with pytest.raises(ParseError, match="Conflicting image dimensions"):
        parse(f"![x](/img =10x20){{{attributes}}}", strict=True)


def test_conflicting_image_dimensions_are_preserved() -> None:
    source = "![x](/img =10x20){width=30 height=40}"

    document = parse(source)

    assert document.to_yfm() == source
    assert any(isinstance(node, RawInline) for node in document.walk())


def test_complementary_image_dimensions_and_quoted_title() -> None:
    document = parse('![x](/img "=title" =10x){height=20}', strict=True)

    image = next(node for node in document.walk() if isinstance(node, Image))
    assert (image.title, image.width, image.height) == ("=title", 10, 20)


@pytest.mark.parametrize(
    ("node", "expected"),
    [
        (Link("x", "javascript&colon;alert(1)"), "[x](javascript%26colon;alert%281%29)"),
        (Image("/img?name=&copy;", alt="x"), "![x](/img?name=%26copy;)"),
        (LinkDefinition("ref", "/path?name=&copy;"), "[ref]: /path?name=%26copy;"),
    ],
)
def test_generated_entity_like_url_survives_strict_roundtrip(
    node: Link | Image | LinkDefinition, expected: str
) -> None:
    source = node.to_yfm()

    document = parse(source, strict=True)

    assert document.to_yfm() == expected
