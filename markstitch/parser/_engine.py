"""Translate markdown-it tokens into the public YFM tree."""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from functools import partial
from html import unescape
from typing import TYPE_CHECKING, Any

from markdown_it import MarkdownIt
from markdown_it.common.utils import normalizeReference
from markdown_it.tree import SyntaxTreeNode

from markstitch.blocks import (
    CODE_FLAGS,
    CODE_PROMPT,
    BulletList,
    Checklist,
    CodeBlock,
    Heading,
    ListItem,
    Paragraph,
    Quote,
    Rule,
)
from markstitch.core import YFM, Element, Inline, Link, NumberedList, Profile
from markstitch.extensions import LinkDefinition
from markstitch.inline import Bold, Code, Image, Italic, LineBreak, Raw, RawInline, Text
from markstitch.parser._directives import block
from markstitch.parser._inline import inline_rule
from markstitch.parser._rules import block_rule, fence_rule, nesting_rule
from markstitch.parser._tables import multiline_table, simple_table
from markstitch.parser.parse import MAX_NESTING, ParseError

if TYPE_CHECKING:
    from markdown_it.rules_inline import StateInline
    from markdown_it.token import Token


class Parser:
    def __init__(self, *, profile: Profile, strict: bool) -> None:
        self.profile = profile
        self.strict = strict
        self.references: dict[str, dict[str, str]] = {}
        self.collecting_references = False
        self.md = MarkdownIt("commonmark", {"maxNesting": MAX_NESTING + 1}).enable("table")
        self.md.inline.ruler.before("text", "yfm_nesting", self._inline_nesting)
        self.md.inline.ruler.before("text", "yfm", partial(inline_rule, parser=self))
        # Let our guard reject excessive nesting before markdown-it silently truncates it.
        self.block_md = MarkdownIt("commonmark", {"maxNesting": MAX_NESTING + 1}).enable("table")
        self.block_md.inline.ruler.before("text", "yfm_nesting", self._inline_nesting)
        self.block_md.block.ruler.before("code", "yfm_nesting", nesting_rule)
        self.block_md.block.ruler.at("fence", fence_rule)
        self.block_md.core.ruler.disable("inline")
        self.block_md.block.ruler.before(
            "fence", "yfm", block_rule, {"alt": ["paragraph", "reference", "blockquote", "list"]}
        )

    def document(self, source: str) -> YFM:
        # Discover definitions through the same block grammar, before resolving any inline links.
        self.collecting_references = True
        skeleton = YFM(*self.blocks(source))
        self.collecting_references = False

        for node in skeleton.walk():
            if isinstance(node, LinkDefinition):
                self.references.setdefault(
                    normalizeReference(node.label), {"href": node.href, "title": node.title or ""}
                )

        return YFM(*self.blocks(source), profile=self.profile)

    def blocks(self, source: str, depth: int = 0) -> tuple[Element, ...]:
        self.check_depth(depth)
        tree = SyntaxTreeNode(self.block_md.parse(source))
        return tuple(self.convert(node, source, depth + 1) for node in tree.children)

    def inlines(self, source: str, depth: int = 0) -> tuple[Inline, ...]:
        self.check_depth(depth)

        if self.collecting_references:
            return ()

        try:
            tokens = self.md.parseInline(source, {"yfm_depth": depth + 1, "references": self.references})
            self._check_inline_depth(tokens, depth)
            tree = SyntaxTreeNode(tokens)
            result = tuple(
                self._inline(node, depth + 1)
                for node in tree.children[0].children
                if node.type != "text" or node.content
            )

            for element in result:
                element.to_yfm(profile=self.profile)

        except (ValueError, TypeError) as error:
            if self.strict or isinstance(error, ParseError):
                raise

            return (RawInline(source),)

        return result

    def image_alt(self, source: str, depth: int) -> str:
        self.check_depth(depth)
        tokens = self.block_md.inline.parse(
            source, self.block_md, {"references": self.references, "yfm_depth": depth}, []
        )
        self._check_inline_depth(tokens, depth)
        pending = list(reversed(tokens))
        parts = []

        while pending:
            token = pending.pop()

            if token.type in {"text", "text_special", "code_inline"}:
                parts.append(token.content)
            elif token.type in {"softbreak", "hardbreak"}:
                parts.append(" ")
            elif token.type == "image":
                pending.extend(reversed(token.children or []))

        return "".join(parts)

    def convert(self, node: SyntaxTreeNode, source: str, depth: int) -> Element:
        self.check_depth(depth)
        line = node.map[0] + 1 if node.map else 1
        original = (
            node.content.removesuffix("\n")
            if node.type in {"yfm_block", "html_block"} or not node.map
            else "\n".join(source.splitlines()[slice(*node.map)])
        )
        original = node.meta.get("yfm_source", original)

        try:
            result = self._block(node, source, depth)
            result.to_yfm(profile=self.profile)

        except (ValueError, TypeError) as error:
            if isinstance(error, ParseError):
                raise

            return self.fallback(original, line, error)

        return result

    def fallback(self, source: str, line: int, error: Exception) -> Raw:
        if self.strict:
            raise ParseError(f"Cannot parse YFM at line {line}: {error}") from error

        return Raw(source)

    @staticmethod
    def text(source: str) -> str:
        return unescape(re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~ ])", r"\1", source))

    @staticmethod
    def check_depth(depth: int) -> None:
        if depth > MAX_NESTING:
            raise ParseError(f"Document nesting exceeds {MAX_NESTING} levels")

    def _inline_nesting(self, state: StateInline, silent: bool) -> bool:
        self.check_depth(state.level + 1 + state.env.get("yfm_depth", 0))
        return False

    def _check_inline_depth(self, tokens: list[Token], depth: int) -> None:
        # Emphasis is paired after tokenization; validate it before SyntaxTreeNode recurses.
        pending = [(tokens, depth)]

        while pending:
            children, level = pending.pop()

            for token in children:
                level += token.nesting
                self.check_depth(level)

                if token.children:
                    pending.append((token.children, level + 1))

    def _block(self, node: SyntaxTreeNode, source: str, depth: int) -> Element:
        if node.type == "yfm_block":
            return (
                multiline_table(node.content, self, depth)
                if node.content.startswith("#|")
                else block(node.content, self, depth)
            )

        if node.type == "table":
            return simple_table(node, self, depth)

        if node.type == "paragraph":
            return Paragraph(*self.inlines(node.children[0].content, depth))

        if node.type == "heading":
            return self._heading(node, depth)

        if node.type in {"fence", "code_block"}:
            return self._code(node)

        if node.type == "hr":
            return Rule()

        factories: dict[str, Callable[..., Element]] = {
            "list_item": ListItem,
            "blockquote": Quote,
        }

        if node.type == "bullet_list":
            return self._bullet(node, source, depth)

        if node.type in factories:
            return factories[node.type](*(self.convert(child, source, depth + 1) for child in node.children))

        if node.type == "ordered_list":
            return NumberedList(
                *(self.convert(child, source, depth + 1) for child in node.children),
                start=int(node.attrs.get("start", 1)),
                loose=self._loose(node),
            )

        raise ValueError(f"Unsupported block: {node.type}")

    def _bullet(self, node: SyntaxTreeNode, source: str, depth: int) -> Element:
        children = tuple(self.convert(child, source, depth + 1) for child in node.children)
        lists = [
            child.children[0]
            for child in children
            if isinstance(child, ListItem) and len(child.children) == 1 and isinstance(child.children[0], Checklist)
        ]

        if lists and len(lists) == len(children):
            return Checklist(*(task for checklist in lists for task in checklist.children))

        return BulletList(*children, loose=self._loose(node))

    @staticmethod
    def _loose(node: SyntaxTreeNode) -> bool:
        return any(
            child.children and child.children[0].type == "paragraph" and not child.children[0].to_tokens()[0].hidden
            for child in node.children
        )

    def _heading(self, node: SyntaxTreeNode, depth: int) -> Heading:
        text = node.children[0].content
        anchor = re.search(r"\s+\{#([\w.-]+)\}$", text)

        if anchor:
            text = text[: anchor.start()]

        return Heading(
            Text(*self.inlines(text, depth)),
            level=int(node.tag[1:]),
            anchor=anchor[1] if anchor else None,
        )

    @staticmethod
    def _code(node: SyntaxTreeNode) -> CodeBlock:
        words = shlex.split(node.info)
        language = ""

        prompt_prefix = f"{CODE_PROMPT}="

        if words and words[0] not in CODE_FLAGS and not words[0].startswith(prompt_prefix):
            language = words.pop(0)

        options: dict[str, Any] = {}

        for word in words:
            if word in CODE_FLAGS:
                options[CODE_FLAGS[word]] = True
            elif word.startswith(prompt_prefix):
                options[CODE_PROMPT] = unescape(word.removeprefix(prompt_prefix))
            else:
                raise ValueError(f"Unsupported code option: {word}")

        return CodeBlock(node.content.removesuffix("\n"), language=language, **options)

    def _inline(self, node: SyntaxTreeNode, depth: int) -> Inline:
        self.check_depth(depth)
        factories: dict[str, Callable[..., Inline]] = {"strong": Bold, "em": Italic}

        if node.type == "yfm_inline" and isinstance(element := node.meta.get("element"), Inline):
            return element

        if node.type in factories:
            return factories[node.type](
                *(self._inline(child, depth + 1) for child in node.children if child.type != "text" or child.content)
            )

        if node.type in {"text", "softbreak"}:
            return Text("\n" if node.type == "softbreak" else node.content)

        if node.type == "hardbreak":
            return LineBreak()

        if node.type == "code_inline":
            if node.content and not node.content.strip() and len(node.content) > 2:
                return Code(node.content[1:-1])

            return Code(node.content)

        if node.type == "link":
            title = node.attrs.get("title")
            return Link(
                Text(*(self._inline(child, depth + 1) for child in node.children)),
                href=f"{node.attrs['href']}",
                title=f"{title}" if title is not None else None,
            )

        if node.type == "image":
            title = node.attrs.get("title")
            return Image(
                src=f"{node.attrs['src']}",
                alt=self.image_alt(node.content, depth + 1),
                title=f"{title}" if title is not None else None,
            )

        if self.strict:
            raise ParseError(f"Unsupported inline token: {node.type}")

        return RawInline(node.content)
