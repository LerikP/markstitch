import pytest

from markstitch import Code, CodeBlock, Cut, If, InlineIf, ParseError, Strike, parse


@pytest.mark.parametrize("marker", ["```", "~~~"])
@pytest.mark.parametrize(
    ("opening", "closing"),
    [('{% cut "x" %}', "{% endcut %}"), (":::visibility human", ":::"), ("#|\n||", "||\n|#")],
)
def test_false_code_closer_does_not_end_container(marker: str, opening: str, closing: str) -> None:
    code = f"{marker}suffix\n{closing}\nkept"
    source = f"{opening}\n\n{marker}text\n{code}\n{marker}\n\n{closing}\n\nafter"

    document = parse(source, profile="diplodoc", strict=True)

    assert len(document.children) == 2
    assert [node.text for node in document.walk() if isinstance(node, CodeBlock)] == [code]


def test_indented_code_does_not_close_directive() -> None:
    source = '{% cut "x" %}\n\n    {% endcut %}\n\ntext\n\n{% endcut %}'

    document = parse(source, strict=True)

    assert isinstance(document.children[0], Cut)
    assert len(document.children) == 1
    assert [node.text for node in document.walk() if isinstance(node, CodeBlock)] == ["{% endcut %}"]


@pytest.mark.parametrize("marker", ["```", "~~~"])
def test_false_code_closer_does_not_expose_else(marker: str) -> None:
    source = f"{{% if enabled %}}\n\n{marker}text\n{marker}suffix\n{{% else %}}\n{marker}\n\n{{% endif %}}"

    document = parse(source, profile="diplodoc", strict=True)

    condition = document.children[0]
    assert isinstance(condition, If)
    assert condition.otherwise is None
    assert [node.text for node in document.walk() if isinstance(node, CodeBlock)] == [f"{marker}suffix\n{{% else %}}"]


@pytest.mark.parametrize("text", [r"literal \`", "unmatched `", "`` `{% else %}` ``", "    literal", "```unmatched"])
def test_inline_condition_scanner_respects_commonmark_code(text: str) -> None:
    source = f"{{% if enabled %}}{text}{{% else %}}no{{% endif %}}"

    document = parse(source, profile="diplodoc", strict=True)

    condition = next(node for node in document.walk() if isinstance(node, InlineIf))
    assert condition.otherwise is not None
    assert condition.otherwise.to_yfm() == "no"


def test_inline_code_hides_formatting_delimiter() -> None:
    document = parse("~~a `~~` b~~", strict=True)

    strike = next(node for node in document.walk() if isinstance(node, Strike))
    assert [node.text for node in strike.walk() if isinstance(node, Code)] == ["~~"]
    assert document.to_yfm() == "~~a `~~` b~~"


@pytest.mark.parametrize(
    "source",
    ["> ```python future\n> x\n> ```", "- ~~~python future\n  x\n  ~~~", "> - ```python future\n>   x\n>   ```"],
)
def test_unknown_nested_fence_preserves_local_source(source: str) -> None:
    document = parse(source)

    assert document.to_yfm() == source


def test_unknown_nested_fence_is_rejected_strictly() -> None:
    with pytest.raises(ParseError, match="Unsupported code option"):
        parse("> ```python future\n> x\n> ```", strict=True)
