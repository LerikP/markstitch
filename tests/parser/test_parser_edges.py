from collections.abc import Callable

import pytest

from markstitch import (
    YFM,
    Bold,
    BulletList,
    Cell,
    Checklist,
    CodeBlock,
    Cut,
    Element,
    Emoji,
    File,
    Heading,
    If,
    Image,
    Link,
    Math,
    Paragraph,
    ParseError,
    Raw,
    RawInline,
    ReferenceImage,
    Row,
    Text,
    Visibility,
    YFMTable,
    parse,
)


@pytest.mark.parametrize(
    "source",
    [
        "[link](/url){future=value}",
        "{{ unsupported() }}",
        '{% cut "Unclosed" %}\n\nbody',
        "{% if enabled %}unclosed",
        '![image](/image.png "title" extra)',
        "#|\n|| a | > ||\n|| ^ | b ||\n|#",
    ],
)
def test_unknown_or_invalid_source_is_preserved(source: str) -> None:
    document = parse(source, profile="diplodoc")

    assert document.to_yfm() == source
    assert any(isinstance(node, (Raw, RawInline)) for node in document.walk())


@pytest.mark.parametrize("source", ["[link](/url){future=value}", "{{ unsupported() }}", "{% if enabled %}unclosed"])
def test_strict_mode_rejects_invalid_inline_source(source: str) -> None:
    with pytest.raises(ParseError):
        parse(source, profile="diplodoc", strict=True)


def test_inline_markers_in_middle_of_text() -> None:
    source = "Text :smile: and $x^2$ and {green}(OK) and ++yes++."

    document = parse(source, strict=True)

    assert any(isinstance(node, Emoji) for node in document.walk())
    assert any(isinstance(node, Math) for node in document.walk())
    assert document.to_yfm() == source


def test_escaped_input_stays_text() -> None:
    source = r"\*\*literal\*\* \{\% cut title \%\} &amp;amp;"

    document = parse(source, strict=True)

    assert not any(isinstance(node, (Bold, Cut)) for node in document.walk())
    assert next(node for node in document.walk() if isinstance(node, Text)).children


def test_table_code_cannot_swallow_following_blocks() -> None:
    table = YFMTable(Row(Cell(CodeBlock("#|\n|| a | b ||\n|#", language="text"))))
    source = YFM(table, Paragraph("after")).to_yfm()

    document = parse(source, strict=True)

    assert len(list(document)) == 2
    assert document.to_yfm() == source


def test_nested_visibility_and_following_content() -> None:
    source = YFM(Visibility("human", Visibility("agent", "nested")), Paragraph("after")).to_yfm(profile="diplodoc")

    document = parse(source, profile="diplodoc", strict=True)

    assert len(list(document)) == 2
    assert len([node for node in document.walk() if isinstance(node, Visibility)]) == 2
    assert document.to_yfm() == source


def test_condition_markers_inside_code_are_not_branches() -> None:
    source = If("enabled", CodeBlock("{% else %}", language="text"), otherwise="other").to_yfm(profile="diplodoc")

    document = parse(source, profile="diplodoc", strict=True)

    assert document.to_yfm() == source


def test_diplodoc_checklist_is_not_plain_bullet_list() -> None:
    document = parse("- [x] Done\n- [ ] Next", profile="diplodoc", strict=True)

    assert isinstance(next(iter(document)), Checklist)
    assert document.to_yfm() == "- [x] Done\n- [ ] Next"


def test_nested_lists_and_links_remain_editable() -> None:
    source = "- Parent\n\n  1. **one**\n  2. [two](/two)"

    document = parse(source, strict=True)

    assert isinstance(next(iter(document)), BulletList)
    assert any(isinstance(node, Link) for node in document.walk())
    assert document.to_yfm() == source


def test_unknown_inline_macro_is_a_raw_leaf() -> None:
    source = "Before {% custom %}body{% endcustom %} after"

    document = parse(source)

    assert isinstance(next(iter(document)), Paragraph)
    assert any(isinstance(node, RawInline) for node in document.walk())
    assert document.to_yfm() == source


def test_deeply_nested_directives_are_rejected_with_parse_error() -> None:
    source = '{% cut "x" %}\n\n' * 70 + "body\n\n" + "{% endcut %}\n\n" * 70

    with pytest.raises(ParseError, match="nesting"):
        parse(source)


@pytest.mark.parametrize(
    "source",
    [
        "A\n\n#|\n||\n```text\n#|\n```\n||\n|#\n\nAfter",
        '{% list tabs %}\n\n- First\n\n  {% cut "Details" %}\n\n  body\n\n  {% endcut %}\n\n{% endlist %}',
        "1. First\n\n2. Second",
        "- First\n\n- Second",
        "`     `",
        '``` prompt="$"\n$ date\n```',
        "[`a]b`](/path)",
    ],
)
def test_additional_normalized_roundtrips(source: str) -> None:
    document = parse(source, profile="diplodoc", strict=True)

    assert document.to_yfm() == source


def test_shortcut_reference_is_resolved_before_definition() -> None:
    document = parse("See [site].\n\n[site]: https://example.com", strict=True)

    links = [node for node in document.walk() if isinstance(node, Link)]

    assert len(links) == 1
    assert links[0].href == "https://example.com"


@pytest.mark.parametrize("profile", ["tracker", "wiki", "diplodoc"])
def test_heading_with_leading_plus_is_not_collapsible(profile: str) -> None:
    document = parse("## + Title {#title}", profile=profile, strict=True)

    heading = next(iter(document))
    assert isinstance(heading, Heading)
    assert heading.collapsible is False
    assert heading.anchor == "title"
    assert document.to_yfm() == r"## \+ Title {#title}"


@pytest.mark.parametrize("profile", ["tracker", "wiki"])
def test_collapsible_heading_preserves_its_marker(profile: str) -> None:
    document = parse("##+ Title {#title}", profile=profile, strict=True)

    heading = next(iter(document))
    assert isinstance(heading, Heading)
    assert heading.collapsible is True
    assert heading.anchor == "title"
    assert document.to_yfm() == "##+ Title {#title}"


@pytest.mark.parametrize(
    ("encoded", "prompt"),
    [
        ("a&quot;b", 'a"b'),
        ("a&amp;b", "a&b"),
        ("a&amp;quot;b", "a&quot;b"),
        ("&lt;shell&gt;", "<shell>"),
        ("&#123;&#37;", "{%"),
    ],
)
def test_code_prompt_entities_are_decoded_once(encoded: str, prompt: str) -> None:
    source = f'```bash prompt="{encoded}"\necho hello\n```'

    document = parse(source, profile="diplodoc", strict=True)

    code = next(iter(document))
    assert isinstance(code, CodeBlock)
    assert code.prompt == prompt
    assert document.to_yfm() == source


@pytest.mark.parametrize("name", ["foo.bar", "foo-bar", "foo_bar", "\u044f"])
def test_emoji_identifier_remains_editable(name: str) -> None:
    source = f":{name}:"

    document = parse(source, strict=True)

    assert [node.name for node in document.walk() if isinstance(node, Emoji)] == [name]
    assert document.to_yfm() == source


def test_emoji_with_plus_is_plain_text() -> None:
    document = parse(":foo+bar:", strict=True)

    assert isinstance(next(iter(document)), Paragraph)
    assert not any(isinstance(node, (Emoji, Raw, RawInline)) for node in document.walk())
    assert document.to_yfm() == r"\:foo\+bar\:"


@pytest.mark.parametrize("profile", ["tracker", "wiki", "diplodoc"])
def test_plain_text_does_not_become_emoji_after_parsing(profile: str) -> None:
    source = Text(":smile:").to_yfm(profile=profile)

    document = parse(source, profile=profile, strict=True)

    assert not any(isinstance(node, Emoji) for node in document.walk())
    assert document.to_yfm() == r"\:smile\:"


@pytest.mark.parametrize(
    ("encoded", "alt"),
    [
        (r"a\]b", "a]b"),
        (r"a\\b", r"a\b"),
        ("a&amp;b", "a&b"),
        ("a&amp;amp;b", "a&amp;b"),
        (r"\<script\>", "<script>"),
    ],
)
def test_reference_image_alt_is_decoded_once(encoded: str, alt: str) -> None:
    source = f"![{encoded}][ref]"

    document = parse(source, strict=True)

    images = [node for node in document.walk() if isinstance(node, ReferenceImage)]
    assert len(images) == 1
    assert images[0].alt == alt
    assert images[0].label == "ref"
    assert document.to_yfm() == source


@pytest.mark.parametrize("text", [r"a\b", r"a\\b", "tail\\", "&#92;"])
@pytest.mark.parametrize(
    ("factory", "field", "profile"),
    [
        (lambda text: Cut(text, "body"), "title", "tracker"),
        (lambda text: Link("link", "/url", title=text), "title", "tracker"),
        (lambda text: Image("/image", title=text), "title", "tracker"),
        (lambda text: File("/file", name=text), "name", "tracker"),
        (lambda text: CodeBlock("echo hello", prompt=text), "prompt", "diplodoc"),
    ],
    ids=["cut", "link", "image", "file", "code-prompt"],
)
def test_quoted_fields_preserve_backslashes(
    text: str, factory: Callable[[str], Element], field: str, profile: str
) -> None:
    element = factory(text)
    source = element.to_yfm(profile=profile)

    document = parse(source, profile=profile, strict=True)

    parsed = next(node for node in document.walk() if isinstance(node, type(element)))
    assert getattr(parsed, field) == text
    assert document.to_yfm() == source
