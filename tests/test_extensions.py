import pytest

from markstitch import YFM, Paragraph
from markstitch.core import Element, UnsupportedFeatureError
from markstitch.extensions import (
    File,
    Footnote,
    FootnoteDefinition,
    Grid,
    Iframe,
    Include,
    Layout,
    LinkDefinition,
    PageTree,
    RawHTML,
    ReferenceImage,
    ReferenceLink,
    StyledBlock,
    Term,
    TermDefinition,
    Toc,
    Video,
    Visibility,
    WikiInclude,
)
from markstitch.templates import For, If, Variable


@pytest.mark.parametrize(
    ("element", "profile", "expected"),
    [
        (
            File("/files/a.zip", "archive", "application/zip"),
            "tracker",
            '{% file src="/files/a.zip" name="archive" type="application/zip" %}',
        ),
        (
            StyledBlock("text", align="center", width=100, border="solid", border_color="warning"),
            "tracker",
            "{% block align=center width=100 border=solid borderColor=warning %}\n\ntext\n\n{% endblock %}",
        ),
        (
            Layout(StyledBlock("left", col=3), StyledBlock("right", col=9)),
            "tracker",
            (
                "{% layout gap=l cols=auto justify=start %}\n\n{% block col=3 %}\n\nleft\n\n{% endblock %}\n\n"
                "{% block col=9 %}\n\nright\n\n{% endblock %}\n\n{% endlayout %}"
            ),
        ),
        (RawHTML("<p>Trusted</p>"), "tracker", "::: html\n\n<p>Trusted</p>\n\n:::"),
        (Toc(start=2, end=4), "wiki", '{% toc from="h2" to="h4" %}'),
        (PageTree("/docs", depth=2), "wiki", '{% tree page="/docs" depth="2" sort="asc" sort_by="title" %}'),
        (
            WikiInclude("/docs", start="a", end="b"),
            "wiki",
            '{% include page="/docs" warning="true" from="a" to="b" %}',
        ),
        (
            Grid("test-grid", columns=("name", "value")),
            "wiki",
            '{% wgrid id="test-grid" readonly="1" num="1" columns="name, value" %}',
        ),
        (
            Include("_includes/page.md", text="Page", notitle=True),
            "diplodoc",
            "{% include notitle [Page](_includes/page.md) %}",
        ),
        (Video("example-video", provider="youtube"), "diplodoc", "@[youtube](example-video)"),
        (ReferenceLink("site", "ref"), "tracker", "[site][ref]"),
        (ReferenceImage("image", "ref"), "diplodoc", "![image][ref]"),
        (LinkDefinition("ref", "https://example.com", title="Site"), "tracker", '[ref]: https://example.com "Site"'),
        (Term("Word", "word"), "diplodoc", "[Word](*word)"),
        (TermDefinition("word", "Meaning"), "diplodoc", "[*word]: Meaning"),
        (Footnote("note"), "diplodoc", "[^note]"),
        (FootnoteDefinition("note", "first", "second"), "diplodoc", "[^note]: first\n\n    second"),
        (Visibility("agent", "Instructions"), "diplodoc", ":::visibility agent\nInstructions\n:::"),
        (Variable("user.name", filters=("capitalize",)), "diplodoc", "{{ user.name | capitalize }}"),
        (
            If("os == 'linux'", "Linux", otherwise="Other"),
            "diplodoc",
            "{% if os == 'linux' %}\n\nLinux\n\n{% else %}\n\nOther\n\n{% endif %}",
        ),
        (
            For("user", "users", Paragraph(Variable("user.name"))),
            "diplodoc",
            "{% for user in users %}\n\n{{ user.name }}\n\n{% endfor %}",
        ),
    ],
)
def test_profile_extensions(element: Element, profile: str, expected: str) -> None:
    result = element.to_yfm(profile=profile)

    assert result == expected


@pytest.mark.parametrize(
    "element",
    [
        Toc(),
        PageTree("/docs"),
        WikiInclude("/docs"),
        Grid("grid"),
        Include("a.md"),
        Term("word", "term"),
        Variable("name"),
        Video("video"),
    ],
)
def test_tracker_rejects_foreign_extensions(element: Element) -> None:
    document = YFM(element)

    with pytest.raises(UnsupportedFeatureError, match="tracker"):
        document.to_yfm()


@pytest.mark.parametrize("scheme", ["https", "HTTPS", "HtTpS"])
def test_iframe_https_scheme_is_case_insensitive(scheme: str) -> None:
    element = Iframe(f"{scheme}://example.com/embed")

    result = element.to_yfm(profile="wiki")

    assert result == (
        f'/iframe/(src="{scheme}://example.com/embed" width="640" height="360" '
        'frameborder="0" scrolling="auto" allow="")'
    )


def test_footnote_is_not_a_term_when_walking_document() -> None:
    term = TermDefinition("term", "meaning")
    footnote = FootnoteDefinition("note", "first", "second")
    document = YFM(term, footnote, profile="diplodoc")

    terms = [node for node in document.walk() if isinstance(node, TermDefinition)]

    assert terms == [term]
    assert footnote.label == "note"
    assert footnote.children == ("first", "second")
    assert document.to_yfm() == "[*term]: meaning\n\n[^note]: first\n\n    second"
