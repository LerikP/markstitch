"""Parse YFM source into editable document nodes."""

from markstitch.core import YFM, Profile

MAX_NESTING = 64


class ParseError(ValueError):
    """Unsupported or malformed source in strict parsing mode."""


def parse(source: str, *, profile: Profile | str = Profile.TRACKER, strict: bool = False) -> YFM:
    from markstitch.parser._engine import Parser  # noqa: PLC0415 — load the optional dependency only when parsing.

    if not isinstance(source, str):
        raise TypeError("source must be a string")

    return Parser(profile=Profile(profile), strict=strict).document(source)
