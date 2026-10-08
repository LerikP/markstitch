"""Small scanners shared by YFM token rules. No expression evaluation or I/O."""

import re
import shlex
from bisect import bisect_left
from collections.abc import Iterator
from html import unescape

REFERENCE_DEFINITION = re.compile(r"^\[((?:\\.|[^\]\\])+)\]:")
TAG = re.compile(r"\{%\s*+([\w-]++)(.*?)%\}")
TAG_NAME = re.compile(r"\{%\s*+[\w-]++")
FOR_ARGUMENTS = re.compile(r"([\w.]+)\s+in\s+([\w.]+)")
LEAF_TAGS = frozenset({"include", "file", "toc", "tree", "wgrid"})


class TagScanner:
    """Index terminators once; malformed openers never rescan the remaining document."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.closings = [match.start() for match in re.finditer(r"%\}", source)]
        self.newlines = [match.start() for match in re.finditer("\n", source)]

    def match(self, position: int, end: int | None = None) -> re.Match[str] | None:
        opening = TAG_NAME.match(self.source, position)

        if opening is None:
            return None

        closing_index = bisect_left(self.closings, opening.end())

        if closing_index == len(self.closings):
            return None

        closing = self.closings[closing_index]
        newline_index = bisect_left(self.newlines, opening.end())

        if (end is not None and closing + 2 > end) or (
            newline_index < len(self.newlines) and self.newlines[newline_index] < closing
        ):
            return None

        return TAG.match(self.source, position, closing + 2)


def words(source: str) -> list[str]:
    return [unescape(word) for word in shlex.split(source)]


def parameters(source: str) -> dict[str, str]:
    result = {}

    for word in words(source):
        name, separator, value = word.partition("=")

        if not separator or name in result:
            raise ValueError("Expected unique name=value attributes")

        result[name] = value

    return result


def take_attributes(source: str, prefix: str) -> tuple[dict[str, str], str]:
    if not source.startswith(prefix):
        return {}, source

    end = source.find("}", len(prefix))

    if end < 0:
        raise ValueError("Unclosed attribute block")

    return parameters(source[len(prefix) : end]), source[end + 1 :]


def find_unescaped(source: str, marker: str, start: int = 0, *, skip_code: bool = False) -> int:
    position = start

    while position < len(source):
        if source[position] == "\\":
            position += 2
        elif skip_code and (end := code_end(source, position, block=False)) is not None:
            position = end
        elif source.startswith(marker, position):
            return position
        else:
            position += 1

    return -1


def balanced(source: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    position = start

    while position < len(source):
        if source[position] == "\\":
            position += 2
            continue

        if source[position] == opening:
            depth += 1
        elif source[position] == closing:
            depth -= 1

            if depth == 0:
                return position

        position += 1

    return -1


def split_otherwise(source: str, *, block: bool = False) -> tuple[str, str | None]:
    depth = 0

    for match in _tags(source, block=block):
        if match[1] == "if":
            depth += 1
        elif match[1] == "endif":
            depth -= 1
        elif match[1] == "else" and depth == 0:
            return source[: match.start()], source[match.end() :]

    return source, None


def inline_tag_end(source: str, start: int, name: str) -> int:
    depth = 1

    for match in _tags(source[start:]):
        if match[1] == name:
            depth += 1
        elif match[1] == f"end{name}":
            depth -= 1

            if depth == 0:
                return start + match.start()

    return -1


def fence_state(line: str, current: str = "") -> str:
    """CommonMark fences: <=3 spaces, same marker, no text after a closing fence."""
    match = re.fullmatch(r" {0,3}(`{3,}|~{3,})([^\n]*)", line)

    if not match:
        return current

    marker, suffix = match.groups()

    if current:
        if marker[0] == current[0] and len(marker) >= len(current) and not suffix.strip(" \t"):
            return ""

        return current

    return marker if marker[0] == "~" or "`" not in suffix else ""


def code_end(source: str, position: int, *, block: bool = True) -> int | None:
    """Skip a fenced block or an exactly matched CommonMark backtick span."""

    if source[position] not in {"`", "~"}:
        return None

    line_start = source.rfind("\n", 0, position) + 1
    line_end = source.find("\n", position)
    line_end = len(source) if line_end < 0 else line_end
    prefix = source[line_start:position]
    marker = fence_state(source[line_start:line_end]) if block and not prefix.strip(" ") else ""

    if marker:
        stop = line_end + 1

        while stop < len(source):
            end = source.find("\n", stop)
            end = len(source) if end < 0 else end

            if not fence_state(source[stop:end], marker):
                return end

            stop = end + 1

        return len(source)

    if source[position] != "`" or (position > 0 and source[position - 1] == "`"):
        return None

    if not (opening := re.match(r"`+", source[position:])):
        return None

    for closing in re.finditer(r"`+", source[position + len(opening[0]) :]):
        if len(closing[0]) == len(opening[0]):
            return position + len(opening[0]) + closing.end()

    return None


def _tags(source: str, *, block: bool = False) -> Iterator[re.Match[str]]:
    scanner = TagScanner(source)
    position = 0

    while position < len(source):
        if source[position] == "\\":
            position += 2
        elif (end := code_end(source, position, block=block)) is not None:
            position = end
        elif block and (position == 0 or source[position - 1] == "\n") and source.startswith(("    ", "\t"), position):
            end = source.find("\n", position)
            position = len(source) if end < 0 else end + 1
        elif tag := scanner.match(position):
            yield tag
            position = tag.end()
        else:
            position += 1
