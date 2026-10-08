"""Block-level YFM constructs."""

from dataclasses import dataclass

from markstitch.core import (
    MAX_HEADING_LEVEL,
    Container,
    Element,
    Profile,
    blocks,
    choice,
    directive,
    escape,
    fence,
    identifier,
    indent,
    inline,
    one_line,
    positive,
    prefix_lines,
    quoted,
    render,
    require,
)
from markstitch.inline import render_text

CODE_FLAGS = {"showLineNumbers": "line_numbers", "wrap": "wrap"}
CODE_PROMPT = "prompt"


class Paragraph(Container):
    def _render(self, profile: Profile) -> str:
        return render_text(self.children, profile)


@dataclass
class Heading(Element):
    _child_fields = ("text",)

    text: Element | str
    level: int = 1
    anchor: str | None = None
    collapsible: bool = False

    def _render(self, profile: Profile) -> str:
        if positive(self.level, "level") > MAX_HEADING_LEVEL:
            raise ValueError(f"Heading level must be between 1 and {MAX_HEADING_LEVEL}")

        if self.collapsible:
            require(profile, "Collapsible heading", Profile.TRACKER, Profile.WIKI)

        anchor = f" {{#{identifier(self.anchor)}}}" if self.anchor else ""
        collapse = "+" if self.collapsible else ""
        return f"{'#' * self.level}{collapse} {one_line(inline(self.text, profile))}{anchor}"


class FixedHeading(Heading):
    LEVEL = 1

    def __init__(self, text: Element | str, *, anchor: str | None = None, collapsible: bool = False) -> None:
        super().__init__(text=text, level=self.LEVEL, anchor=anchor, collapsible=collapsible)


class Header1(FixedHeading):
    LEVEL = 1


class Header2(FixedHeading):
    LEVEL = 2


class Header3(FixedHeading):
    LEVEL = 3


class Header4(FixedHeading):
    LEVEL = 4


class Header5(FixedHeading):
    LEVEL = 5


class Header6(FixedHeading):
    LEVEL = 6


class BulletList(Container):
    def __init__(self, *children: Element | str, loose: bool = False) -> None:
        super().__init__(*children)
        self.loose = loose

    def _render(self, profile: Profile) -> str:
        separator = "\n\n" if self.loose else "\n"
        return separator.join(prefix_lines(render(child, profile), "- ") for child in self.children)


class ListItem(Container):
    def _render(self, profile: Profile) -> str:
        return blocks(self.children, profile)


class Quote(Container):
    def _render(self, profile: Profile) -> str:
        return "\n".join(f"> {line}" if line else ">" for line in blocks(self.children, profile).split("\n"))


@dataclass
class CodeBlock(Element):
    text: str
    language: str = ""
    line_numbers: bool = False
    wrap: bool = False
    prompt: str | None = None

    def _render(self, profile: Profile) -> str:
        if self.language:
            identifier(self.language)

        delimiter = fence(self.text)
        flags = "".join(f" {name}" for name, field in CODE_FLAGS.items() if getattr(self, field))
        prompt = ""

        if self.prompt is not None:
            require(profile, "Code prompt", Profile.DIPLODOC)
            prompt = f" {CODE_PROMPT}={quoted(self.prompt)}"

        newline = "" if self.text.endswith("\n") else "\n"
        return f"{delimiter}{self.language}{flags}{prompt}\n{self.text}{newline}{delimiter}"


@dataclass
class MathBlock(Element):
    text: str

    def _render(self, profile: Profile) -> str:
        if "$$" in self.text:
            raise ValueError("Math block must not contain a closing delimiter")

        return f"$$\n{self.text}\n$$"


class Rule(Element):
    def _render(self, profile: Profile) -> str:
        return "---"


@dataclass
class Comment(Element):
    text: str

    def _render(self, profile: Profile) -> str:
        return f"[//]: # ({escape(one_line(self.text))})"


class Cut(Container):
    def __init__(self, title: str, *children: Element | str) -> None:
        super().__init__(*children)
        self.title = title

    def _render(self, profile: Profile) -> str:
        return directive("cut", blocks(self.children, profile), arguments=quoted(self.title))


class Note(Container):
    def __init__(self, *children: Element | str, kind: str = "info", title: str | None = None) -> None:
        super().__init__(*children)
        self.kind = kind
        self.title = title

    def _render(self, profile: Profile) -> str:
        choice(self.kind, {"info", "tip", "warning", "alert"}, "note kind")
        title = f" {quoted(self.title)}" if self.title is not None else ""
        return directive("note", blocks(self.children, profile), arguments=f"{self.kind}{title}")


class Tab(Container):
    def __init__(self, title: str, *children: Element | str, selected: bool = False) -> None:
        super().__init__(*children)
        self.title = title
        self.selected = selected

    def _render(self, profile: Profile) -> str:
        selected = ""

        if self.selected:
            require(profile, "Selected tab", Profile.DIPLODOC)
            selected = " {selected}"

        return f"- {escape(one_line(self.title))}{selected}\n\n{indent(blocks(self.children, profile), 2)}"


class Tabs(Container):
    def __init__(self, *children: Tab, mode: str = "tabs", group: str | None = None) -> None:
        super().__init__(*children)
        self.mode, self.group = mode, group

    def _render(self, profile: Profile) -> str:
        if not self.children or any(not isinstance(child, Tab) for child in self.children):
            raise TypeError("Tabs requires one or more Tab elements")

        choice(self.mode, {"tabs", "radio", "dropdown", "accordion"}, "tabs mode")
        mode = ""
        group = ""

        if self.mode != "tabs":
            require(profile, "Interactive tabs mode", Profile.DIPLODOC)
            mode = f" {self.mode}"

        if self.group is not None:
            require(profile, "Tabs synchronization", Profile.DIPLODOC)
            group = f" group={identifier(self.group)}"

        return directive("list", blocks(self.children, profile), arguments=f"tabs{mode}{group}", end="endlist")


@dataclass
class Task(Element):
    _child_fields = ("text",)

    text: Element | str
    checked: bool = False

    def _render(self, profile: Profile) -> str:
        prefix = "- " if profile == Profile.DIPLODOC else ""
        check = "x" if self.checked else " "
        return f"{prefix}[{check}] {one_line(inline(self.text, profile))}"


class Checklist(Container):
    def _render(self, profile: Profile) -> str:
        if any(not isinstance(child, Task) for child in self.children):
            raise TypeError("Checklist requires Task elements")

        separator = "\n" if profile == Profile.DIPLODOC else "\n\n"
        return separator.join(render(child, profile) for child in self.children)
