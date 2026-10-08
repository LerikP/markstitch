"""Typed presentation attributes for Diplodoc tables."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from markstitch.core import identifier, one_line


@dataclass(frozen=True)
class Attributes:
    """Presentation chosen by the document author; classes/style must be trusted, not user input."""

    id: str | None = None
    classes: tuple[str, ...] = ()
    style: Mapping[str, str] = field(default_factory=dict)
    extra: Mapping[str, str] = field(default_factory=dict)

    def to_yfm(self) -> str:
        values: dict[str, str] = {}

        if self.id is not None:
            values["id"] = identifier(self.id)

        if self.classes:
            values["class"] = " ".join(identifier(name) for name in self.classes)

        if self.style:
            values["style"] = "; ".join(self._declaration(name, value) for name, value in self.style.items())

        for name, value in self.extra.items():
            if not re.fullmatch(r"(?:data-|aria-)[a-z][a-z0-9-]*|title", name):
                raise ValueError("Extra attributes must be data-*, aria-* or title")

            values[name] = self._value(value)

        return " ".join(f'{name}="{value}"' for name, value in values.items())

    @staticmethod
    def _value(value: str) -> str:
        one_line(value)

        if any(character in value for character in "\\\"'{}|<>&"):
            raise ValueError("Attribute value contains a markup delimiter")

        return value

    @classmethod
    def _declaration(cls, name: str, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z-]*|--[a-z][a-z0-9-]*", name):
            raise ValueError("Invalid CSS property name")

        if not value or not re.fullmatch(r"[\w\s#.,%+/-]+", value) or "/*" in value or "*/" in value:
            raise ValueError("Expected a CSS keyword, color or dimension without functions or delimiters")

        return f"{name}: {cls._value(value)}"
