import pytest

from markstitch import CodeBlock, Image, Link, Tab, Tabs
from markstitch.core import Element, UnsupportedFeatureError


@pytest.mark.parametrize("mode", ["radio", "dropdown", "accordion"])
def test_interactive_modes(mode: str) -> None:
    element = Tabs(Tab("Linux", "Instructions", selected=True), mode=mode, group="platform")

    result = element.to_yfm(profile="diplodoc")

    assert result == (
        f"{{% list tabs {mode} group=platform %}}\n\n- Linux {{selected}}\n\n  Instructions\n\n{{% endlist %}}"
    )


def test_code_options() -> None:
    element = CodeBlock("$ date", language="bash", wrap=True, prompt="$")

    result = element.to_yfm(profile="diplodoc")

    assert result == '```bash wrap prompt="$"\n$ date\n```'


def test_link_target_and_image_profile() -> None:
    element = Link(Image("image.png", width=100), "https://example.com", target="_blank")

    result = element.to_yfm(profile="diplodoc")

    assert result == "[![](image.png){width=100}](https://example.com){target=_blank}"


@pytest.mark.parametrize(
    "element",
    [
        Tabs(Tab("a", "b"), mode="radio"),
        Tabs(Tab("a", "b", selected=True)),
        CodeBlock("text", prompt="$"),
        Link("a", "b", target="_blank"),
    ],
)
def test_tracker_rejects_unverified_options(element: Element) -> None:
    with pytest.raises(UnsupportedFeatureError):
        element.to_yfm()
