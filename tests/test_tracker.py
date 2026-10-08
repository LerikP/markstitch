import pytest

from markstitch import (
    YFM,
    Bold,
    BulletList,
    Checklist,
    Code,
    CodeBlock,
    Color,
    Comment,
    Cut,
    Emoji,
    Heading,
    Highlight,
    Image,
    Italic,
    LineBreak,
    ListItem,
    Math,
    MathBlock,
    Mention,
    Monospace,
    Note,
    NumberedList,
    Paragraph,
    Quote,
    Raw,
    Rule,
    Strike,
    Subscript,
    Superscript,
    Tab,
    Tabs,
    Task,
    Text,
    Underline,
)
from markstitch.core import Element


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        (Paragraph("Hello ", Bold(Italic("world")), "!"), "Hello **_world_**\\!"),
        (Text("a", LineBreak(), "b"), "a  \nb"),
        (Underline("text"), "++text++"),
        (Strike("text"), "~~text~~"),
        (Highlight("text"), "==text=="),
        (Monospace("text"), "##text##"),
        (Superscript("2"), "^2^"),
        (Subscript("2"), "~2~"),
        (Color(Bold("OK"), color="green"), "{green}(**OK**)"),
        (Code("SELECT `id`"), "`` SELECT `id` ``"),
        (CodeBlock("```\ncode", language="python"), "````python\n```\ncode\n````"),
        (CodeBlock("x = 1", language="python", line_numbers=True), "```python showLineNumbers\nx = 1\n```"),
        (Math("x^2"), "$x^2$"),
        (MathBlock("x^2"), "$$\nx^2\n$$"),
        (Mention("example-user"), "@example-user"),
        (Emoji("smile"), ":smile:"),
        (Heading("Title", level=2, anchor="title", collapsible=True), "##+ Title {#title}"),
        (Image("image.png", alt="image", width=100, height=200), "![image](image.png =100x200)"),
        (Rule(), "---"),
        (Comment("internal note"), "[//]: # (internal note)"),
        (Raw("{% custom %}"), "{% custom %}"),
        (Checklist(Task("Done", checked=True), Task("Next")), "[x] Done\n\n[ ] Next"),
        (Quote("first", Quote("nested")), "> first\n>\n> > nested"),
        (Cut("Details", "Body"), '{% cut "Details" %}\n\nBody\n\n{% endcut %}'),
        (Note("Body", kind="warning", title="Title"), '{% note warning "Title" %}\n\nBody\n\n{% endnote %}'),
        (BulletList(ListItem("Parent", NumberedList("One", "Two"))), "- Parent\n\n  1. One\n  2. Two"),
        (
            Tabs(Tab("One", "first"), Tab("Two", "second")),
            "{% list tabs %}\n\n- One\n\n  first\n\n- Two\n\n  second\n\n{% endlist %}",
        ),
    ],
)
def test_tracker_elements(element: Element, expected: str) -> None:
    result = element.to_yfm()

    assert result == expected


def test_nested_tracker_document() -> None:
    document = YFM(
        Heading("Report", level=2),
        Cut("Details", Note(Paragraph("Status: ", Color("OK", color="green")), kind="tip")),
    )

    result = document.to_yfm()

    assert result == (
        '## Report\n\n{% cut "Details" %}\n\n{% note tip %}\n\nStatus\\: {green}(OK)\n\n{% endnote %}\n\n{% endcut %}'
    )
