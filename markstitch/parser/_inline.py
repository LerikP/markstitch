"""Inline extensions over markdown-it's CommonMark tokenizer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from markdown_it.helpers import parseLinkDestination, parseLinkTitle

from markstitch.core import Inline, Link
from markstitch.extensions import Footnote, ReferenceImage, ReferenceLink, Term
from markstitch.inline import (
    COLORS,
    Color,
    Emoji,
    Highlight,
    Image,
    Math,
    Mention,
    Monospace,
    RawInline,
    Strike,
    Subscript,
    Superscript,
    Text,
    Underline,
)
from markstitch.parser._syntax import (
    FOR_ARGUMENTS,
    TagScanner,
    balanced,
    find_unescaped,
    inline_tag_end,
    split_otherwise,
    take_attributes,
)
from markstitch.templates import InlineFor, InlineIf, Slice, Variable

if TYPE_CHECKING:
    from markdown_it.rules_inline import StateInline

    from markstitch.parser._engine import Parser

COLOR_START = re.compile(rf"\{{({'|'.join(sorted(COLORS))})\}}\(")


@dataclass
class LinkArguments:
    href: str
    title: str | None = None
    dimensions: list[str] = field(default_factory=list)


def inline_rule(state: StateInline, silent: bool, *, parser: Parser) -> bool:
    source = state.src[state.pos : state.posMax]
    depth = state.env.get("yfm_depth", 0)

    if state.pos > 0 and source.startswith(("@", ":")) and re.match(r"[\w.+-]", state.src[state.pos - 1]):
        return False

    tag = None

    if source.startswith("{%"):
        scanners: dict[int, TagScanner] = state.env.setdefault("yfm_tag_scanners", {})
        source_id = id(state.src)

        if source_id not in scanners:
            scanners[source_id] = TagScanner(state.src)

        tag = scanners[source_id].match(state.pos, state.posMax)

    found = read_inline(source, parser, depth, tag=tag)

    if found is None:
        return False

    element, consumed = found

    if not silent:
        token = state.push("yfm_inline", "", 0)
        token.content = source[:consumed]
        token.meta["element"] = element

    state.pos += consumed
    return True


def read_inline(source: str, parser: Parser, depth: int, *, tag: re.Match[str] | None) -> tuple[Inline, int] | None:
    parser.check_depth(depth)

    if source.startswith(("![", "[")):
        return _link(source, parser, depth)

    if source.startswith("{{"):
        end = source.find("}}", 2)

        if end >= 0:
            return _variable(source[2:end], parser, depth), end + 2

    if source.startswith("{%"):
        return _template(source, parser, depth, tag)

    if match := COLOR_START.match(source):
        end = balanced(source, match.end() - 1, "(", ")")

        if end >= 0:
            return Color(Text(*parser.inlines(source[match.end() : end], depth + 1)), match[1]), end + 1

    if match := re.match(r"@([\w.-]+)", source):
        return Mention(match[1]), match.end()

    if match := re.match(r":([\w.-]+):", source):
        return Emoji(match[1]), match.end()

    return _format(source, parser, depth)


def _format(source: str, parser: Parser, depth: int) -> tuple[Inline, int] | None:
    factories = {"++": Underline, "~~": Strike, "==": Highlight, "##": Monospace, "^": Superscript, "~": Subscript}

    for marker, factory in factories.items():
        if source.startswith(marker) and (end := find_unescaped(source, marker, len(marker), skip_code=True)) > len(
            marker
        ):
            content = source[len(marker) : end]

            if marker in {"^", "~"}:
                content = re.sub(r"\\([\\ ])", lambda match: "\\\\" if match[1] == "\\" else " ", content)

            return factory(*parser.inlines(content, depth + 1)), end + len(marker)

    if source.startswith("$") and (end := find_unescaped(source, "$", 1)) > 1:
        return Math(source[1:end]), end + 1

    return None


def _link(source: str, parser: Parser, depth: int) -> tuple[Inline, int] | None:
    if match := re.match(r"\[\^([\w.-]+)\]", source):
        return Footnote(match[1]), match.end()

    image = source.startswith("!")
    start = int(image)
    label_end = balanced(source, start, "[", "]")

    if label_end < 0 or label_end + 1 >= len(source):
        return None

    label = source[start + 1 : label_end]
    next_pos = label_end + 1

    if source[next_pos] == "[" and (end := find_unescaped(source, "]", next_pos + 1)) >= 0:
        reference = source[next_pos + 1 : end]

        if not reference:
            return None

        node = (
            ReferenceImage(parser.image_alt(label, depth + 1), reference)
            if image
            else ReferenceLink(Text(*parser.inlines(label, depth + 1)), reference)
        )
        return node, end + 1

    if source[next_pos] != "(":
        return None

    arguments, end = _link_arguments(source, next_pos + 1)
    attrs, rest = take_attributes(source[end + 1 :], "{")
    consumed = len(source) - len(rest)
    return _destination(image, label, arguments, attrs, parser, depth), consumed


def _link_arguments(source: str, start: int) -> tuple[LinkArguments, int]:
    position = len(source) - len(source[start:].lstrip())

    if position < len(source) and source[position] == ")":
        return LinkArguments(""), position

    destination = parseLinkDestination(source, position, len(source))

    if not destination.ok:
        raise ValueError("Invalid link destination")

    arguments = LinkArguments(destination.str)
    position = destination.pos
    dimensions = re.compile(r"=\d*x\d*(?=\s|\))")

    while position < len(source) and source[position] != ")":
        if not source[position].isspace():
            raise ValueError("Expected whitespace before link options")

        position = len(source) - len(source[position:].lstrip())

        if position == len(source) or source[position] == ")":
            break

        title = parseLinkTitle(source, position, len(source))

        if title.ok:
            if arguments.title is not None:
                raise ValueError("Unknown destination arguments")

            arguments.title = title.str
            position = title.pos
        elif match := dimensions.match(source, position):
            arguments.dimensions.append(match[0])
            position = match.end()
        else:
            raise ValueError("Invalid link title or image dimensions")

    if position == len(source):
        raise ValueError("Unclosed link")

    return arguments, position


def _destination(
    image: bool, label: str, args: LinkArguments, attrs: dict[str, str], parser: Parser, depth: int
) -> Inline:
    href = args.href

    if not image and href.startswith("*"):
        if args.title is not None or args.dimensions or attrs:
            raise ValueError("Unknown term attributes")

        return Term(Text(*parser.inlines(label, depth + 1)), href[1:])

    if not image:
        target = attrs.pop("target", None)

        if attrs or args.dimensions:
            raise ValueError("Unknown link attributes")

        return Link(Text(*parser.inlines(label, depth + 1)), href, title=args.title, target=target)

    size = _image_dimensions(args.dimensions, attrs)
    svg = attrs.pop("inline", None)

    if attrs or svg not in {None, "true", "false"}:
        raise ValueError("Unknown image attributes")

    return Image(
        href,
        alt=parser.image_alt(label, depth + 1),
        title=args.title,
        inline=None if svg is None else svg == "true",
        **size,
    )


def _image_dimensions(arguments: list[str], attrs: dict[str, str]) -> dict[str, int]:
    dimension_seen = False

    for word in arguments:
        if match := re.fullmatch(r"=(\d*)x(\d*)", word):
            if dimension_seen or not any(match.groups()):
                raise ValueError("Invalid image dimensions")

            dimension_seen = True
            dimensions = {
                name: value for name, value in zip(("width", "height"), match.groups(), strict=True) if value
            }

            if dimensions.keys() & attrs.keys():
                raise ValueError("Conflicting image dimensions")

            attrs.update(dimensions)
        elif word.startswith("="):
            raise ValueError("Invalid image dimensions")

    return {name: int(attrs.pop(name)) for name in ("width", "height") if name in attrs}


def _variable(source: str, parser: Parser, depth: int) -> Variable:
    expression, *filters = (part.strip() for part in source.split("|"))
    name = re.match(r"[A-Za-z_][\w.]*(?=\.slice\(|$)", expression)

    if not name:
        raise ValueError("Unknown variable expression")

    # The greedy path includes method names: split explicitly at the first call.
    path, _, calls = expression.partition(".slice(")
    value: str | Slice = path
    rest = ".slice(" + calls if calls else ""

    while rest:
        depth += 1
        parser.check_depth(depth)
        match = re.match(r"\.slice\((-?\d+)(?:,\s*(-?\d+))?\)", rest)

        if not match:
            raise ValueError("Invalid slice expression")

        value = Slice(value, int(match[1]), int(match[2]) if match[2] is not None else None)
        rest = rest[match.end() :]

    return Variable(value, filters=tuple(filters))


def _template(source: str, parser: Parser, depth: int, match: re.Match[str] | None) -> tuple[Inline, int] | None:
    if not match:
        return None

    name, args = match[1], match[2].strip()
    opening_end = match.end() - match.start()
    end = inline_tag_end(source, opening_end, name)

    if end < 0:
        raise ValueError(f"Unclosed inline directive: {name}")

    consumed = source.find("%}", end) + 2
    body = source[opening_end:end]

    if name == "if":
        content, otherwise = split_otherwise(body)
        alternative = Text(*parser.inlines(otherwise, depth + 1)) if otherwise is not None else None
        return InlineIf(args, *parser.inlines(content, depth + 1), otherwise=alternative), consumed

    if name == "for" and (loop := FOR_ARGUMENTS.fullmatch(args)):
        return InlineFor(loop[1], loop[2], *parser.inlines(body, depth + 1)), consumed

    if parser.strict:
        raise ValueError(f"Unsupported directive: {name}")

    return RawInline(source[:consumed]), consumed
