from collections.abc import Callable

import pytest

from markstitch import Element, LinkDefinition, ReferenceImage, ReferenceLink


@pytest.mark.parametrize("label", ["foo bar", "foo:bar", "a&b", r"a\]b", "\u044f label with spaces"])
@pytest.mark.parametrize(
    ("factory", "prefix", "suffix"),
    [
        (lambda label: ReferenceLink("site", label), "[site][", "]"),
        (lambda label: ReferenceImage("image", label), "![image][", "]"),
        (lambda label: LinkDefinition(label, "/url"), "[", "]: /url"),
    ],
    ids=["link", "image", "definition"],
)
def test_reference_labels_allow_commonmark_characters(
    label: str, factory: Callable[[str], Element], prefix: str, suffix: str
) -> None:
    element = factory(label)

    result = element.to_yfm()

    assert result == f"{prefix}{label}{suffix}"


@pytest.mark.parametrize("label", ["", " \t\n ", "a]b", "a[b", "tail\\", "a" * 1000])
def test_reference_label_rejects_empty_unsafe_or_oversized_input(label: str) -> None:
    element = LinkDefinition(label, "/url")

    with pytest.raises(ValueError):
        element.to_yfm()


def test_reference_label_normalizes_whitespace() -> None:
    element = ReferenceLink("site", "  foo\tbar  ")

    result = element.to_yfm()

    assert result == "[site][foo bar]"
