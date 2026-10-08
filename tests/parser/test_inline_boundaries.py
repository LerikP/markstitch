import pytest

from markstitch import Emoji, Mention, RawInline, parse


@pytest.mark.parametrize("profile", ["tracker", "wiki", "diplodoc"])
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("email@example.com", r"email\@example.com"),
        ("user.name+tag@example.com", r"user.name\+tag\@example.com"),
        ("12:30:45", r"12\:30\:45"),
        ("word:smile:", r"word\:smile\:"),
    ],
)
def test_word_fragments_do_not_become_extensions(source: str, expected: str, profile: str) -> None:
    document = parse(source, profile=profile, strict=True)

    assert not any(isinstance(node, (Mention, Emoji, RawInline)) for node in document.walk())
    assert document.to_yfm() == expected


@pytest.mark.parametrize("profile", ["tracker", "wiki"])
@pytest.mark.parametrize("source", ["@alice :smile:", "Hello, @alice and :smile:", "**@alice** **:smile:**"])
def test_explicit_extensions_remain_recognized(source: str, profile: str) -> None:
    document = parse(source, profile=profile, strict=True)

    assert [node.login for node in document.walk() if isinstance(node, Mention)] == ["alice"]
    assert [node.name for node in document.walk() if isinstance(node, Emoji)] == ["smile"]
    assert document.to_yfm() == source
