import pytest

from markstitch import Header3
from markstitch.blocks import Header1, Header2, Header4, Header5, Header6
from markstitch.core import Element
from markstitch.extensions import Iframe


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        (Header1("Title"), "# Title"),
        (Header2("Title"), "## Title"),
        (Header3("Title"), "### Title"),
        (Header4("Title"), "#### Title"),
        (Header5("Title"), "##### Title"),
        (Header6("Title"), "###### Title"),
    ],
)
def test_header_shortcuts(element: Element, expected: str) -> None:
    result = element.to_yfm()

    assert result == expected


def test_wiki_frame() -> None:
    element = Iframe("https://example.com/embed", width=300, height=100)

    result = element.to_yfm(profile="wiki")

    assert (
        result == '/iframe/(src="https://example.com/embed" width="300" height="100" '
        'frameborder="0" scrolling="auto" allow="")'
    )
