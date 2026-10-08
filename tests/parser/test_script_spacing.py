import pytest

from markstitch import Code, Subscript, Superscript, Text, parse


@pytest.mark.parametrize("node_type", [Superscript, Subscript])
@pytest.mark.parametrize("text", ["a b", r"a\ b", r"a\\ b", "two  spaces"])
def test_script_spaces_are_decoded_once(node_type: type[Superscript] | type[Subscript], text: str) -> None:
    source = node_type(text).to_yfm()

    document = parse(source, strict=True)

    script = next(node for node in document.walk() if isinstance(node, node_type))
    assert "".join(part for node in script.children if isinstance(node, Text) for part in node.children) == text
    assert document.to_yfm() == source


def test_superscript_code_spaces_are_decoded_once() -> None:
    source = Superscript(Code("a b")).to_yfm()

    document = parse(source, strict=True)

    assert [node.text for node in document.walk() if isinstance(node, Code)] == ["a b"]
    assert document.to_yfm() == source
