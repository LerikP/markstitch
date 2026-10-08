"""Explicit, author-controlled Diplodoc template syntax; no template evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from markstitch.core import (
    Container,
    Element,
    Inline,
    Profile,
    blocks,
    choice,
    directive,
    inline,
    one_line,
    render,
    require,
)


@dataclass(frozen=True)
class Slice:
    source: str | Slice
    begin: int
    end: int | None = None

    def to_yfm(self) -> str:
        source = self.source.to_yfm() if isinstance(self.source, Slice) else _path(self.source)

        if type(self.begin) is not int or (self.end is not None and type(self.end) is not int):
            raise ValueError("Slice indices must be integers")

        end = f", {self.end}" if self.end is not None else ""
        return f"{source}.slice({self.begin}{end})"


@dataclass
class Variable(Inline):
    name: str | Slice
    filters: tuple[str, ...] = ()

    def _render(self, profile: Profile) -> str:
        require(profile, "Variable", Profile.DIPLODOC)
        name = self.name.to_yfm() if isinstance(self.name, Slice) else _path(self.name)
        filters = "".join(f" | {choice(value, {'capitalize', 'length'}, 'filter')}" for value in self.filters)
        return f"{{{{ {name}{filters} }}}}"


class If(Container):
    _child_fields = ("children", "otherwise")

    def __init__(self, expression: str, *children: Element | str, otherwise: Element | str | None = None) -> None:
        super().__init__(*children)
        self.expression, self.otherwise = expression, otherwise

    def _render(self, profile: Profile) -> str:
        require(profile, "If", Profile.DIPLODOC)
        expression = _condition(self.expression)

        body = blocks(self.children, profile)

        if self.otherwise is not None:
            body += f"\n\n{{% else %}}\n\n{render(self.otherwise, profile)}"

        return directive("if", body, arguments=expression)


class For(Container):
    def __init__(self, variable: str, collection: str, *children: Element | str) -> None:
        super().__init__(*children)
        self.variable, self.collection = variable, collection

    def _render(self, profile: Profile) -> str:
        require(profile, "For", Profile.DIPLODOC)
        return directive(
            "for",
            blocks(self.children, profile),
            arguments=f"{_path(self.variable)} in {_path(self.collection)}",
        )


class InlineIf(If, Inline):
    def _render(self, profile: Profile) -> str:
        require(profile, "InlineIf", Profile.DIPLODOC)
        expression = _condition(self.expression)
        body = "".join(inline(child, profile) for child in self.children)

        if self.otherwise is not None:
            body += "{% else %}" + inline(self.otherwise, profile)

        return f"{{% if {expression} %}}{body}{{% endif %}}"


class InlineFor(For, Inline):
    def _render(self, profile: Profile) -> str:
        require(profile, "InlineFor", Profile.DIPLODOC)
        variable = _path(self.variable)
        collection = _path(self.collection)
        body = "".join(inline(child, profile) for child in self.children)
        return f"{{% for {variable} in {collection} %}}{body}{{% endfor %}}"


def _condition(expression: str) -> str:
    one_line(expression)

    if not expression or any(character in expression for character in "{}%"):
        raise ValueError("Expected an author-controlled condition without template delimiters")

    return expression


def _path(value: str) -> str:
    if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in value.split(".")):
        raise ValueError("Expected a dotted variable path")

    return value
