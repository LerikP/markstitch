"""Inline content, composed without implicit whitespace."""

from collections.abc import Iterator
from dataclasses import dataclass

from markstitch.core import (
    Container,
    Element,
    Inline,
    Profile,
    choice,
    destination,
    escape,
    fence,
    identifier,
    inline,
    one_line,
    positive,
    quoted,
    require,
)

COLORS = frozenset({"gray", "yellow", "orange", "red", "green", "blue", "violet"})


class Text(Container, Inline):
    def _render(self, profile: Profile) -> str:
        return render_text(self.children, profile)


class Bold(Text):
    def _render(self, profile: Profile) -> str:
        return f"**{super()._render(profile)}**"


class Italic(Text):
    def _render(self, profile: Profile) -> str:
        return f"_{super()._render(profile)}_"


class Underline(Text):
    def _render(self, profile: Profile) -> str:
        return f"++{super()._render(profile)}++"


class Strike(Text):
    def _render(self, profile: Profile) -> str:
        return f"~~{super()._render(profile)}~~"


class Highlight(Text):
    def _render(self, profile: Profile) -> str:
        require(profile, "Highlight", Profile.TRACKER, Profile.WIKI)
        return f"=={super()._render(profile)}=="


class Monospace(Text):
    def _render(self, profile: Profile) -> str:
        return f"##{super()._render(profile)}##"


class Superscript(Text):
    def _render(self, profile: Profile) -> str:
        return f"^{super()._render(profile).replace(' ', r'\ ')}^"


class Subscript(Text):
    def _render(self, profile: Profile) -> str:
        return f"~{super()._render(profile).replace(' ', r'\ ')}~"


@dataclass
class Color(Inline):
    _child_fields = ("text",)

    text: Element | str
    color: str

    def _render(self, profile: Profile) -> str:
        choice(self.color, COLORS, "color")
        return f"{{{self.color}}}({inline(self.text, profile)})"


@dataclass
class Code(Inline):
    text: str

    def _render(self, profile: Profile) -> str:
        one_line(self.text)

        if not self.text:
            raise ValueError("Inline code must not be empty")

        delimiter = fence(self.text, minimum=1)
        needs_padding = (
            self.text.startswith("`")
            or self.text.endswith("`")
            or (self.text.startswith(" ") and self.text.endswith(" "))
        )
        padding = " " if needs_padding else ""
        return f"{delimiter}{padding}{self.text}{padding}{delimiter}"


@dataclass
class Math(Inline):
    text: str

    def _render(self, profile: Profile) -> str:
        one_line(self.text)

        if "$" in self.text:
            raise ValueError("Inline math must not contain a dollar delimiter")

        return f"${self.text}$"


@dataclass
class Mention(Inline):
    login: str

    def _render(self, profile: Profile) -> str:
        require(profile, "Mention", Profile.TRACKER, Profile.WIKI)
        return f"@{identifier(self.login)}"


@dataclass
class Emoji(Inline):
    name: str

    def _render(self, profile: Profile) -> str:
        require(profile, "Emoji", Profile.TRACKER, Profile.WIKI)
        return f":{identifier(self.name)}:"


class LineBreak(Inline):
    def _render(self, profile: Profile) -> str:
        return "  \n"


@dataclass
class Image(Inline):
    src: str
    alt: str = ""
    title: str | None = None
    width: int | None = None
    height: int | None = None
    inline: bool | None = None

    def _render(self, profile: Profile) -> str:
        dimensions = {
            name: positive(value, name)
            for name, value in (("width", self.width), ("height", self.height))
            if value is not None
        }
        title = f" {quoted(self.title)}" if self.title is not None else ""
        size = ""
        attributes = ""

        if self.inline is not None:
            require(profile, "SVG inlining", Profile.DIPLODOC)

            if not isinstance(self.inline, bool):
                raise ValueError("inline must be a boolean")

        if (dimensions or self.inline is not None) and profile == Profile.DIPLODOC:
            parts = [f"{name}={value}" for name, value in dimensions.items()]

            if self.inline is not None:
                parts.append("inline=true" if self.inline else "inline=false")

            attributes = "{" + " ".join(parts) + "}"
        elif dimensions:
            size = f" ={dimensions.get('width', '')}x{dimensions.get('height', '')}"

        return f"![{escape(one_line(self.alt))}]({destination(self.src)}{title}{size}){attributes}"


@dataclass
class Raw(Element):
    text: str

    def _render(self, profile: Profile) -> str:
        return self.text


class RawInline(Raw, Inline):
    """Explicitly trusted inline markup, without escaping or profile validation."""


def render_text(children: tuple[Element | str, ...], profile: Profile) -> str:
    """Escape adjacent plain-text fragments together so their boundaries cannot create markup."""
    parts: list[str] = []
    text: list[str] = []

    for child in _text_parts(children):
        if isinstance(child, str):
            text.append(child)
        else:
            parts.extend((escape("".join(text)), inline(child, profile)))
            text.clear()

    parts.append(escape("".join(text)))
    return "".join(parts)


def _text_parts(children: tuple[Element | str, ...]) -> Iterator[Element | str]:
    for child in children:
        if type(child) is Text:
            yield from _text_parts(child.children)
        else:
            yield child
