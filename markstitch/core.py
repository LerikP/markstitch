"""Document nodes and rendering contract."""

from __future__ import annotations

import re
from collections.abc import Collection, Iterator
from enum import StrEnum
from html import escape as html_escape
from typing import ClassVar
from urllib.parse import quote, urlsplit

MAX_HEADING_LEVEL = 6


class Profile(StrEnum):
    TRACKER = "tracker"
    WIKI = "wiki"
    DIPLODOC = "diplodoc"


class UnsupportedFeatureError(ValueError):
    """The selected target does not document support for this feature."""


class Element:
    _child_fields: ClassVar[tuple[str, ...]] = ()

    def __iter__(self) -> Iterator[Element]:
        return self.iter_children()

    def __str__(self) -> str:
        return self.to_yfm()

    def to_yfm(self, *, profile: Profile | str = Profile.TRACKER) -> str:
        return self._render(Profile(profile))

    def iter_children(self) -> Iterator[Element]:
        """Yield direct element children; scalar text and metadata remain on their owner."""
        pending = [getattr(self, name) for name in reversed(self._child_fields)]

        while pending:
            child = pending.pop()

            if isinstance(child, Element):
                yield child
            elif isinstance(child, (tuple, list)):
                pending.extend(reversed(child))

    def walk(self) -> Iterator[Element]:
        """Depth-first preorder, including self. Shared nodes are visited per occurrence."""
        pending: list[tuple[Element, bool]] = [(self, False)]
        ancestors: set[int] = set()

        while pending:
            node, leaving = pending.pop()

            if leaving:
                ancestors.remove(id(node))
                continue

            if id(node) in ancestors:
                raise ValueError("Cycle in document tree")

            ancestors.add(id(node))
            yield node
            pending.append((node, True))
            pending.extend((child, False) for child in reversed(tuple(node)))

    def _render(self, profile: Profile) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement _render")


class Inline(Element):
    """An element that can appear inside a paragraph or a link label."""


class Container(Element):
    _child_fields: ClassVar[tuple[str, ...]] = ("children",)

    def __init__(self, *children: Element | str) -> None:
        self.children = tuple(children)


class YFM(Container):
    def __init__(self, *children: Element | str, profile: Profile | str = Profile.TRACKER) -> None:
        super().__init__(*children)
        self.profile = Profile(profile)

    @classmethod
    def from_yfm(cls, source: str, *, profile: Profile | str = Profile.TRACKER, strict: bool = False) -> YFM:
        # Lazy import breaks the parser <-> document node dependency.
        from markstitch.parser import parse  # noqa: PLC0415 — parser imports the document model.

        return parse(source, profile=profile, strict=strict)

    def to_yfm(self, *, profile: Profile | str | None = None) -> str:
        return self._render(self.profile if profile is None else Profile(profile))

    def _render(self, profile: Profile) -> str:
        return blocks(self.children, profile)


class NumberedList(Container):
    def __init__(self, *children: Element | str, start: int = 1, loose: bool = False) -> None:
        super().__init__(*children)
        self.start = start
        self.loose = loose

    def _render(self, profile: Profile) -> str:
        positive(self.start, "start")
        separator = "\n\n" if self.loose else "\n"
        return separator.join(
            prefix_lines(render(child, profile), f"{number}. ")
            for number, child in enumerate(self.children, start=self.start)
        )


class Link(Inline):
    _child_fields = ("text",)

    def __init__(self, text: Inline | str, href: str, *, title: str | None = None, target: str | None = None) -> None:
        self.text = text
        self.href = href
        self.title = title
        self.target = target

    def _render(self, profile: Profile) -> str:
        title = f" {quoted(self.title)}" if self.title is not None else ""
        target = ""

        if self.target is not None:
            require(profile, "Link target", Profile.DIPLODOC)
            choice(self.target, {"_blank", "_self"}, "target")
            target = f"{{target={self.target}}}"

        return f"[{inline(self.text, profile)}]({destination(self.href)}{title}){target}"


def render(value: Element | str, profile: Profile) -> str:
    if isinstance(value, Element):
        return value._render(profile)

    if isinstance(value, str):
        return escape(value)

    raise TypeError(f"Expected an Element or str, got {type(value).__name__}")


def blocks(values: tuple[Element | str, ...], profile: Profile) -> str:
    return "\n\n".join(render(value, profile) for value in values)


def inline(value: Element | str, profile: Profile) -> str:
    if not isinstance(value, (Inline, str)):
        raise TypeError("Block content cannot be used inline")

    return render(value, profile)


def require(profile: Profile, feature: str, *supported: Profile) -> None:
    if profile not in supported:
        raise UnsupportedFeatureError(f"{feature} is not supported by the {profile.value} profile")


def one_line(text: str) -> str:
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise ValueError("Expected single-line text without control characters")

    return text


def identifier(text: str) -> str:
    if not re.fullmatch(r"[\w.-]+", text):
        raise ValueError(f"Invalid identifier: {text!r}")

    return text


def reference_label(text: str) -> str:
    if not text.strip() or len(text) > 999:
        raise ValueError("Reference label must contain 1 to 999 characters")

    normalized = one_line(" ".join(text.split()))

    if not re.fullmatch(r"(?:\\.|[^\[\]\\])+", normalized):
        raise ValueError("Reference label must escape brackets and backslashes")

    return normalized


def positive(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")

    return value


def choice(value: str, options: Collection[str], name: str) -> str:
    if value not in options:
        raise ValueError(f"Invalid {name}: {value!r}; expected one of {sorted(options)}")

    return value


def quoted(text: str) -> str:
    value = html_escape(one_line(text), quote=True).replace("\\", "&#92;").replace("%", "&#37;").replace("{", "&#123;")
    return f'"{value}"'


def directive(name: str, body: str, *, arguments: str = "", end: str | None = None) -> str:
    suffix = f" {arguments}" if arguments else ""
    return f"{{% {name}{suffix} %}}\n\n{body}\n\n{{% {end or f'end{name}'} %}}"


def indent(text: str, width: int) -> str:
    return "\n".join(f"{' ' * width}{line}" if line else "" for line in text.split("\n"))


def prefix_lines(text: str, prefix: str) -> str:
    first, separator, rest = text.partition("\n")
    return f"{prefix}{first}" + (f"\n{indent(rest, len(prefix))}" if separator else "")


def fence(text: str, minimum: int = 3) -> str:
    return "`" * max(minimum, max((len(run) + 1 for run in re.findall(r"`+", text)), default=0))


def escape(text: str) -> str:
    special = frozenset("\\`*_[](){}#|~^+=<>!$@:")
    escaped = "".join(
        f"\\{character}" if character in special else character for character in text.replace("&", "&amp;")
    )
    escaped = re.sub(r"(?m)^([ \t]*\d+)\.", r"\1\\.", escaped)
    return re.sub(r"(?m)^([ \t]*)-", r"\1\\-", escaped)


def destination(href: str) -> str:
    if any(ord(character) < 32 or ord(character) == 127 for character in href):
        raise ValueError("URL must not contain control characters")

    if urlsplit(href).scheme.lower() not in {"", "http", "https", "mailto"}:
        raise ValueError("Unsupported URL scheme")

    encoded = quote(href, safe="/:?#@!$&'*+,;=%~._-")
    return re.sub(r"&(?=(?:#\d+|#[xX][0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);)", "%26", encoded)
