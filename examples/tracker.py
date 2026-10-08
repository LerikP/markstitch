"""Run with uv run python examples/tracker.py; prints YFM without publishing it."""

from markstitch import (
    YFM,
    Bold,
    Cell,
    Checklist,
    CodeBlock,
    Cut,
    Header3,
    Link,
    Note,
    NumberedList,
    Paragraph,
    Row,
    Tab,
    Tabs,
    Task,
    YFMTable,
)


def build_document() -> YFM:
    return YFM(
        Header3("Test1"),
        NumberedList("One", "Two", "Three"),
        Link(text="link", href="example.com"),
        Note(Paragraph("Status: ", Bold("ready")), kind="tip"),
        Cut("Details", CodeBlock("print('hello')", language="python")),
        Tabs(Tab("Linux", "Instructions"), Tab("macOS", "Instructions")),
        Checklist(Task("Implemented", checked=True), Task("Verified in Tracker")),
        YFMTable(Row(Bold("Stage"), Bold("Steps")), Row("Run", Cell(NumberedList("Install", "Execute")))),
    )


if __name__ == "__main__":
    print(build_document().to_yfm())  # noqa: T201 — this example intentionally writes the generated document to stdout.
