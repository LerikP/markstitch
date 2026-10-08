import pytest

from markstitch import Image, Link, LinkDefinition, Paragraph, ParseError, RawInline, ReferenceLink, parse


@pytest.mark.parametrize(
    "definition",
    [
        '[ref]: /url\n  "Title"',
        "[ref]: /url\n  'Title'",
        '[ref]:\n  /url\n  "Title"',
    ],
)
def test_reference_title_on_next_line(definition: str) -> None:
    source = f"See [ref].\n\n{definition}\n\nAfter"

    document = parse(source, strict=True)

    assert [type(node) for node in document] == [Paragraph, LinkDefinition, Paragraph]
    link = next(node for node in document.walk() if isinstance(node, Link))
    assert link.href == "/url"
    assert link.title == "Title"
    reference = next(node for node in document if isinstance(node, LinkDefinition))
    assert reference.title == "Title"
    assert document.to_yfm() == 'See [ref](/url "Title").\n\n[ref]: /url "Title"\n\nAfter'


@pytest.mark.parametrize(
    ("following", "text"),
    [
        ('\n\n"Separate"', '"Separate"'),
        ('\n  "Title" extra', '"Title" extra'),
        ("\n  plain text", "plain text"),
        ('\n  "Unclosed', '"Unclosed'),
    ],
)
def test_reference_definition_does_not_consume_following_paragraph(following: str, text: str) -> None:
    document = parse(f"[ref]: /url{following}", strict=True)

    reference, paragraph = document
    assert isinstance(reference, LinkDefinition)
    assert reference.title is None
    assert isinstance(paragraph, Paragraph)
    assert paragraph.to_yfm() == text


def test_adjacent_reference_definitions_keep_their_titles() -> None:
    source = '[first]: /first\n  "One"\n[second]: /second\n  "Two"'

    document = parse(source, strict=True)

    assert [type(node) for node in document] == [LinkDefinition, LinkDefinition]
    assert document.to_yfm() == '[first]: /first "One"\n\n[second]: /second "Two"'


@pytest.mark.parametrize(
    ("url", "encoded"),
    [
        ("https://example.com", "https://example.com"),
        ("https://example.com/a b", "https://example.com/a%20b"),
        ("https://example.com/a)b(", "https://example.com/a%29b%28"),
    ],
)
def test_angle_reference_destination_and_shortcut(url: str, encoded: str) -> None:
    source = f'See [ref].\n\n[ref]: <{url}> "Title"'

    document = parse(source, strict=True)

    reference = next(node for node in document if isinstance(node, LinkDefinition))
    link = next(node for node in document.walk() if isinstance(node, Link))
    assert (reference.href, reference.title) == (url, "Title")
    assert (link.href, link.title) == (url, "Title")
    assert document.to_yfm() == f'See [ref]({encoded} "Title").\n\n[ref]: {encoded} "Title"'


@pytest.mark.parametrize("title", ['"Title"', "'Title'", "(Title)"])
def test_reference_title_uses_commonmark_delimiters(title: str) -> None:
    document = parse(f"[ref]: <https://example.com>\n  {title}", strict=True)

    reference = next(iter(document))
    assert isinstance(reference, LinkDefinition)
    assert reference.title == "Title"
    assert document.to_yfm() == '[ref]: https://example.com "Title"'


def test_angle_reference_without_title() -> None:
    document = parse("[ref]: <https://example.com>", strict=True)

    reference = next(iter(document))
    assert isinstance(reference, LinkDefinition)
    assert reference.href == "https://example.com"
    assert reference.title is None
    assert document.to_yfm() == "[ref]: https://example.com"


def test_angle_reference_rejects_unsafe_scheme() -> None:
    with pytest.raises(ParseError, match="Unsupported URL scheme"):
        parse("[ref]: <javascript:alert(1)>", strict=True)


@pytest.mark.parametrize("label", ["ref", "REF"])
@pytest.mark.parametrize(("prefix", "node_type", "field"), [("", Link, "href"), ("!", Image, "src")])
def test_collapsed_reference_resolves_implicit_label(
    label: str, prefix: str, node_type: type[Link] | type[Image], field: str
) -> None:
    source = f'{prefix}[{label}][]\n\n[ref]: /url "Title"'

    document = parse(source, strict=True)

    node = next(node for node in document.walk() if isinstance(node, node_type))
    assert getattr(node, field) == "/url"
    assert node.title == "Title"
    assert document.to_yfm() == f'{prefix}[{label}](/url "Title")\n\n[ref]: /url "Title"'


@pytest.mark.parametrize(("prefix", "expected"), [("", r"\[ref\]\[\]"), ("!", r"\!\[ref\]\[\]")])
def test_collapsed_reference_without_definition_is_text(prefix: str, expected: str) -> None:
    document = parse(f"{prefix}[ref][]", strict=True)

    assert not any(isinstance(node, (Link, Image, RawInline)) for node in document.walk())
    assert document.to_yfm() == expected


def test_explicit_reference_keeps_its_label() -> None:
    source = "[site][ref]\n\n[ref]: /url"

    document = parse(source, strict=True)

    reference = next(node for node in document.walk() if isinstance(node, ReferenceLink))
    assert reference.label == "ref"
    assert document.to_yfm() == source


@pytest.mark.parametrize(
    "definition",
    ["> [ref]: /url", "- [ref]: /url", "1. [ref]: /url", "> - [ref]: /url"],
)
def test_shortcut_resolves_definition_nested_later(definition: str) -> None:
    document = parse(f"[ref]\n\n{definition}", strict=True)

    assert [node.href for node in document.walk() if isinstance(node, Link)] == ["/url"]
    assert document.to_yfm() == f"[ref](/url)\n\n{definition}"


@pytest.mark.parametrize(
    "definition",
    [
        '{% cut "x" %}\n\n[ref]: /url\n\n{% endcut %}',
        "{% note info %}\n\n[ref]: /url\n\n{% endnote %}",
        "{% list tabs %}\n\n- First\n\n  [ref]: /url\n\n{% endlist %}",
        ":::visibility human\n\n[ref]: /url\n\n:::",
        "#|\n||\n[ref]: /url\n||\n|#",
        "{% if enabled %}\n\n[ref]: /url\n\n{% else %}\n\n[ref]: /other\n\n{% endif %}",
    ],
)
def test_shortcut_resolves_definition_inside_yfm_container(definition: str) -> None:
    document = parse(f"[ref]\n\n{definition}\n\n[ref]: /later", profile="diplodoc", strict=True)

    assert [node.href for node in document.walk() if isinstance(node, Link)] == ["/url"]


def test_reference_inside_raw_block_does_not_leak() -> None:
    source = "[ref]\n\n{% future %}\n\n[ref]: /hidden\n\n{% endfuture %}"

    document = parse(source)

    assert not any(isinstance(node, Link) for node in document.walk())


def test_collapsed_image_resolves_nested_definition() -> None:
    document = parse('![ref][]\n\n> [ref]: /image "Title"', strict=True)

    images = [node for node in document.walk() if isinstance(node, Image)]
    assert len(images) == 1
    assert images[0].src == "/image"
    assert images[0].title == "Title"
    assert document.to_yfm() == '![ref](/image "Title")\n\n> [ref]: /image "Title"'


@pytest.mark.parametrize(
    "definitions",
    [
        "> [ref]: /first\n\n[ref]: /second",
        "[ref]: /first\n\n> [ref]: /second",
        "> [ref]: /first\n>\n> [ref]: /second",
        "- [ref]: /first\n- [ref]: /second",
    ],
)
def test_first_reference_definition_wins_across_containers(definitions: str) -> None:
    document = parse(f"[ref]\n\n{definitions}", strict=True)

    assert [node.href for node in document.walk() if isinstance(node, Link)] == ["/first"]


@pytest.mark.parametrize("label", ["foo bar", "foo:bar", "a&b", r"a\]b", "\u044f label with spaces"])
def test_commonmark_reference_label_roundtrip(label: str) -> None:
    source = f"[site][{label}]\n\n![image][{label}]\n\n[{label}]: /url"

    document = parse(source, strict=True)

    assert [node.label for node in document if isinstance(node, LinkDefinition)] == [label]
    assert document.to_yfm() == source


@pytest.mark.parametrize("label", ["foo bar", "foo:bar", "a&b", r"a\]b", "\u044f label with spaces"])
def test_shortcut_resolves_commonmark_label(label: str) -> None:
    document = parse(f"[{label}]\n\n[{label}]: /url", strict=True)

    assert [node.href for node in document.walk() if isinstance(node, Link)] == ["/url"]
