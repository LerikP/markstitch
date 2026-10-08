"""Typed conversion for block macros; unknown arguments are never discarded."""

from __future__ import annotations

import re
import textwrap
from typing import TYPE_CHECKING, Any

from markdown_it.helpers import parseLinkDestination, parseLinkTitle

from markstitch.blocks import Checklist, Comment, Cut, Heading, MathBlock, Note, Tab, Tabs, Task
from markstitch.core import MAX_HEADING_LEVEL, YFM, Element
from markstitch.extensions import (
    File,
    FootnoteDefinition,
    Grid,
    Iframe,
    Include,
    Layout,
    LinkDefinition,
    PageTree,
    RawHTML,
    StyledBlock,
    TermDefinition,
    Toc,
    Video,
    Visibility,
    WikiInclude,
)
from markstitch.inline import Text
from markstitch.parser._syntax import (
    FOR_ARGUMENTS,
    LEAF_TAGS,
    REFERENCE_DEFINITION,
    TAG,
    parameters,
    split_otherwise,
    words,
)
from markstitch.templates import For, If

if TYPE_CHECKING:
    from markstitch.parser._engine import Parser


def block(source: str, parser: Parser, depth: int) -> Element:
    first, _, rest = source.partition("\n")

    if first == "$$" and source.endswith("\n$$"):
        return MathBlock(rest.removesuffix("\n$$"))

    if first.startswith(":::") and source.endswith("\n:::"):
        return _colon(first, rest.removesuffix("\n:::"), parser, depth)

    if match := re.fullmatch(rf"(#{{1,{MAX_HEADING_LEVEL}}})\+ (.*?)(?: \{{#([\w.-]+)\}})?", first):
        return Heading(
            Text(*parser.inlines(match[2], depth + 1)), level=len(match[1]), anchor=match[3], collapsible=True
        )

    if re.match(r"\[[ xX]\] ", first):
        return _checklist(source, parser, depth)

    if first.startswith("["):
        return _definition(source, parser, depth)

    if first.startswith(("/iframe/(", "@[")):
        return _media(source)

    match = TAG.fullmatch(first)

    if not match:
        raise ValueError("Malformed YFM block")

    name, arguments = match[1], match[2].strip()

    if name in LEAF_TAGS:
        return _leaf(name, arguments, parser)

    closing = f"{{% end{name} %}}"

    if not rest.rstrip().endswith(closing):
        raise ValueError(f"Unclosed {name} block")

    body = rest.rstrip().removesuffix(closing).strip("\n")
    return _container(name, arguments, body, parser, depth)


def _container(name: str, args: str, body: str, parser: Parser, depth: int) -> Element:
    if name == "list":
        return _tabs(args, body, parser, depth)

    if name == "if":
        content, other = split_otherwise(body, block=True)
        alternative = YFM(*parser.blocks(other.strip("\n"), depth + 1)) if other is not None else None
        return If(args, *parser.blocks(content.strip("\n"), depth + 1), otherwise=alternative)

    children = parser.blocks(body, depth + 1)
    positional = words(args)

    if name == "cut" and len(positional) == 1:
        return Cut(positional[0], *children)

    if name == "note" and 1 <= len(positional) <= 2:
        return Note(*children, kind=positional[0], title=positional[1] if len(positional) == 2 else None)

    if name == "for" and (loop := FOR_ARGUMENTS.fullmatch(args)):
        return For(loop[1], loop[2], *children)

    if name in {"block", "layout"}:
        return _layout(name, args, children)

    raise ValueError(f"Unsupported directive or arguments: {name}")


def _layout(name: str, args: str, children: tuple[Element, ...]) -> Element:
    attrs: dict[str, Any] = parameters(args)

    if name == "layout":
        if not all(isinstance(child, StyledBlock) for child in children):
            raise ValueError("Layout must contain blocks")

        return Layout(*children, **attrs)  # type: ignore[arg-type]

    for key in ("width", "col"):
        if key in attrs:
            attrs[key] = int(attrs[key])

    for old, new in (("borderSize", "border_size"), ("borderColor", "border_color")):
        if old in attrs:
            attrs[new] = attrs.pop(old)

    return StyledBlock(*children, **attrs)


def _tabs(args: str, body: str, parser: Parser, depth: int) -> Tabs:
    options = words(args)

    if not options or options.pop(0) != "tabs":
        raise ValueError("Unsupported list directive")

    mode = options.pop(0) if options and options[0] in {"radio", "accordion", "dropdown"} else "tabs"
    attrs = parameters(" ".join(options))
    starts = list(re.finditer(r"(?m)^- (.+)$", body))
    tabs = []

    if not starts or body[: starts[0].start()].strip():
        raise ValueError("Tabs require named items")

    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        title = match[1]
        selected = title.endswith(" {selected}")
        content = textwrap.dedent(body[match.end() : end].strip("\n"))
        tabs.append(
            Tab(parser.text(title.removesuffix(" {selected}")), *parser.blocks(content, depth + 1), selected=selected)
        )

    return Tabs(*tabs, mode=mode, **attrs)


def _leaf(name: str, args: str, parser: Parser) -> Element:
    if name == "include":
        return _include(args, parser)

    attrs: dict[str, Any] = parameters(args)

    if name == "file":
        if "type" in attrs:
            attrs["mime_type"] = attrs.pop("type")

        return File(**attrs)

    if name == "toc":
        attrs["start"] = int(attrs.pop("from", "h1").removeprefix("h"))
        attrs["end"] = int(attrs.pop("to", f"h{MAX_HEADING_LEVEL}").removeprefix("h"))
        return Toc(**attrs)

    if name == "tree":
        attrs["depth"] = int(attrs.get("depth", "3"))
        return PageTree(**attrs)

    if name == "wgrid":
        return _grid(attrs)

    raise ValueError(f"Unsupported leaf: {name}")


def _include(args: str, parser: Parser) -> Include | WikiInclude:
    if match := re.fullmatch(r"(notitle\s+)?\[(.*)\)", args):
        label, separator, path = match[2].rpartition("](")

        if separator:
            return Include(path, text=parser.text(label), notitle=bool(match[1]))

    attrs: dict[str, Any] = parameters(args)

    if "from" in attrs:
        attrs["start"] = attrs.pop("from")

    if "to" in attrs:
        attrs["end"] = attrs.pop("to")

    attrs["warning"] = _boolean(attrs.get("warning", "true"))
    return WikiInclude(**attrs)


def _grid(attrs: dict[str, Any]) -> Grid:
    for old, new in (("readonly", "readonly"), ("num", "numbers")):
        attrs[new] = _boolean(attrs.pop(old, "1"))

    if "columns" in attrs:
        attrs["columns"] = tuple(column.strip() for column in attrs["columns"].split(","))

    return Grid(**attrs)


def _boolean(value: str) -> bool:
    if value not in {"0", "1", "true", "false"}:
        raise ValueError("Invalid boolean attribute")

    return value in {"1", "true"}


def _checklist(source: str, parser: Parser, depth: int) -> Checklist:
    tasks = []

    for line in source.splitlines():
        if not line.strip():
            continue

        match = re.fullmatch(r"\[([ xX])\] (.*)", line)

        if not match:
            raise ValueError("Malformed checklist")

        tasks.append(Task(Text(*parser.inlines(match[2], depth + 1)), checked=match[1].lower() == "x"))

    return Checklist(*tasks)


def _colon(first: str, body: str, parser: Parser, depth: int) -> Element:
    if first == "::: html":
        return RawHTML(body.strip("\n"))

    if first.startswith(":::visibility "):
        return Visibility(first.removeprefix(":::visibility "), *parser.blocks(body, depth + 1))

    raise ValueError("Unknown colon container")


def _definition(source: str, parser: Parser, depth: int) -> Element:
    if match := re.fullmatch(r"\[//\]: # \((.*)\)", source):
        return Comment(parser.text(match[1]))

    match = REFERENCE_DEFINITION.match(source)

    if not match:
        raise ValueError("Invalid definition")

    label = match[1]
    content = source[match.end() :].lstrip()

    if label.startswith("*"):
        return TermDefinition(label[1:], *parser.blocks(content, depth + 1))

    if label.startswith("^"):
        first, separator, rest = content.partition("\n")
        content = first + separator + textwrap.dedent(rest)
        return FootnoteDefinition(label[1:], *parser.blocks(content, depth + 1))

    content = content.strip()
    destination = parseLinkDestination(content, 0, len(content))

    if not destination.ok:
        raise ValueError("Invalid link definition destination")

    title_source = content[destination.pos :]
    title = None

    if title_source:
        if not title_source[0].isspace():
            raise ValueError("Expected whitespace before link definition title")

        title_source = title_source.strip()
        parsed_title = parseLinkTitle(title_source, 0, len(title_source))

        if not parsed_title.ok or parsed_title.pos != len(title_source):
            raise ValueError("Invalid link definition title")

        title = parsed_title.str

    return LinkDefinition(label, destination.str, title)


def _media(source: str) -> Element:
    if match := re.fullmatch(r"@\[([\w]*)\]\((.*)\)", source):
        return Video(match[2], provider=match[1])

    if not source.startswith("/iframe/(") or not source.endswith(")"):
        raise ValueError("Invalid iframe")

    attrs: dict[str, Any] = parameters(source[len("/iframe/(") : -1])

    for name in ("width", "height"):
        if name in attrs:
            attrs[name] = int(attrs[name])

    if "frameborder" in attrs:
        attrs["frameborder"] = _boolean(attrs["frameborder"])

    return Iframe(**attrs)
