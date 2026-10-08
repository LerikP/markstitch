import pytest

from markstitch import Image, ReferenceImage, parse


@pytest.mark.parametrize(
    ("markup", "alt", "serialized"),
    [
        ("*foo*", "foo", "foo"),
        ("**foo _bar_**", "foo bar", "foo bar"),
        ("`a*b`", "a*b", r"a\*b"),
        ("[foo](/target)", "foo", "foo"),
        ("<b>foo</b>", "foo", "foo"),
        (r"\*foo\*", "*foo*", r"\*foo\*"),
        ("a&amp;b", "a&b", "a&amp;b"),
        ("outer ![inner](/inner)", "outer inner", "outer inner"),
        ("foo\nbar", "foo bar", "foo bar"),
    ],
)
def test_image_alt_is_plain_inline_text(markup: str, alt: str, serialized: str) -> None:
    document = parse(f"![{markup}](/img)", strict=True)

    image = next(node for node in document.walk() if isinstance(node, Image))
    assert image.alt == alt
    assert document.to_yfm() == f"![{serialized}](/img)"


@pytest.mark.parametrize(
    ("source", "profile"),
    [("![*foo*](/img =120x80)", "tracker"), ("![*foo*](/img){width=120 height=80}", "diplodoc")],
)
def test_formatted_alt_keeps_image_dimensions(source: str, profile: str) -> None:
    document = parse(source, profile=profile, strict=True)

    image = next(node for node in document.walk() if isinstance(node, Image))
    assert image.alt == "foo"
    assert (image.width, image.height) == (120, 80)


def test_reference_image_alt_is_plain_text() -> None:
    document = parse("![*foo*][ref]\n\n[ref]: /img", strict=True)

    image = next(node for node in document.walk() if isinstance(node, ReferenceImage))
    assert image.alt == "foo"
    assert document.to_yfm() == "![foo][ref]\n\n[ref]: /img"


def test_collapsed_image_alt_is_plain_text() -> None:
    document = parse("![image *foo*][]\n\n[image *foo*]: /img", strict=True)

    image = next(node for node in document.walk() if isinstance(node, Image))
    assert image.alt == "image foo"
    assert document.to_yfm() == "![image foo](/img)\n\n[image *foo*]: /img"
