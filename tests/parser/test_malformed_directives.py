from time import perf_counter

import pytest

from markstitch import Include, ParseError, Text, parse


@pytest.mark.parametrize("prefix", ["", "before "])
def test_unclosed_long_directive_does_not_cause_backtracking(prefix: str) -> None:
    source = prefix + "{%" + "a" * 32000
    started = perf_counter()

    document = parse(source)

    assert perf_counter() - started < 3
    assert "".join(part for node in document.walk() if type(node) is Text for part in node.children) == source


@pytest.mark.parametrize(
    "source",
    [
        "{% a " * 24000,
        "{% if enabled %}" + "{% a " * 24000,
        "{% if enabled %}" + "{% a " * 24000 + "\n{% endif %}",
        "{% include [" + "](" * 32000 + " %}",
    ],
    ids=["inline-prefixes", "unclosed-template", "multiline-template", "include-separators"],
)
def test_repeated_malformed_delimiters_have_bounded_parse_time(source: str) -> None:
    started = perf_counter()

    document = parse(source, profile="diplodoc")

    assert perf_counter() - started < 3
    assert document.to_yfm().count("{% a") == source.count("{% a")
    assert document.to_yfm().count("](") == source.count("](")


@pytest.mark.parametrize("source", ["{% if enabled %}{% a {% a ", "{% include [a](b](c %}"])
def test_malformed_delimiters_still_fail_strictly(source: str) -> None:
    with pytest.raises(ParseError):
        parse(source, profile="diplodoc", strict=True)


@pytest.mark.parametrize("notitle", [False, True])
def test_include_label_and_path_still_roundtrip(notitle: bool) -> None:
    include = Include("_includes/page.md", text=r"a]b\c", notitle=notitle)
    source = include.to_yfm(profile="diplodoc")

    document = parse(source, profile="diplodoc", strict=True)

    assert isinstance(document.children[0], Include)
    assert document.children[0].text == r"a]b\c"
    assert document.to_yfm() == source
