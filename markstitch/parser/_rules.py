"""Block boundaries for YFM, leaving CommonMark tokenization to markdown-it."""

import re

from markdown_it.rules_block import StateBlock
from markdown_it.rules_block.fence import fence
from markdown_it.rules_block.reference import reference

from markstitch.core import MAX_HEADING_LEVEL
from markstitch.parser._syntax import LEAF_TAGS, REFERENCE_DEFINITION, TAG, fence_state
from markstitch.parser.parse import MAX_NESTING, ParseError


def nesting_rule(state: StateBlock, start: int, end: int, silent: bool) -> bool:
    if state.level >= MAX_NESTING:
        raise ParseError(f"Document nesting exceeds {MAX_NESTING} levels")

    return False


def fence_rule(state: StateBlock, start: int, end: int, silent: bool) -> bool:
    if not fence(state, start, end, silent):
        return False

    if not silent:
        state.tokens[-1].meta["yfm_source"] = state.getLines(start, state.line, state.blkIndent, False).rstrip("\n")

    return True


def block_rule(state: StateBlock, start: int, end: int, silent: bool) -> bool:
    first = _line(state, start)

    special = re.match(rf"^(?:#{{1,{MAX_HEADING_LEVEL}}}\+ |\[[ xX]\] |/iframe/\(|@\[)", first)

    if not (
        (TAG.fullmatch(first) and first.count("%}") == 1)
        or first.startswith(("#|", ":::"))
        or first == "$$"
        or special
        or REFERENCE_DEFINITION.match(first)
    ):
        return False

    if silent:
        return True

    stop = _end(state, start, end)
    token = state.push("yfm_block", "", 0)
    token.map = [start, stop]
    token.content = state.getLines(start, stop, state.blkIndent, False).rstrip("\n")
    state.line = stop
    return True


def _line(state: StateBlock, line: int) -> str:
    return state.src[state.bMarks[line] + state.tShift[line] : state.eMarks[line]].strip()


def _end(state: StateBlock, start: int, end: int) -> int:
    first = _line(state, start)
    match = TAG.fullmatch(first)

    if re.match(rf"^(?:#{{1,{MAX_HEADING_LEVEL}}}\+ |/iframe/\(|@\[|\[//\]:)", first):
        return start + 1

    if not first.startswith(("[^", "[*")) and REFERENCE_DEFINITION.match(first):
        return state.line if reference(state, start, end, False) else start + 1

    if re.match(r"^\[[ xX]\] ", first):
        stop = start + 1

        while stop < end and (not (text := _line(state, stop)) or re.match(r"^\[[ xX]\] ", text)):
            stop += 1

        return stop

    if first.startswith(("[^", "[*")):
        return _definition_end(state, start, end, footnote=first.startswith("[^"))

    if match and match[1] in LEAF_TAGS:
        return start + 1

    if match:
        return _tag_end(state, start, end, match[1])

    return _container_end(state, start, end, first)


def _definition_end(state: StateBlock, start: int, end: int, *, footnote: bool) -> int:
    stop = start + 1

    while stop < end and not REFERENCE_DEFINITION.match(text := _line(state, stop)):
        if footnote and text and state.tShift[stop] < 4:
            break

        stop += 1

    return stop


def _container_end(state: StateBlock, start: int, end: int, first: str) -> int:
    close = "|#" if first.startswith("#|") else "$$" if first == "$$" else ":::"
    depth = 1
    active_fence = ""

    for line in range(start + 1, end):
        text = _line(state, line)
        local = state.getLines(line, line + 1, state.blkIndent, False).rstrip("\n").expandtabs(4)
        previous = active_fence
        active_fence = fence_state(local, active_fence)

        if previous or active_fence or local.startswith("    "):
            continue

        opens_table = close == "|#" and text == "#|"
        opens_container = close == ":::" and text.startswith(":::") and text != ":::" and first != "::: html"

        if opens_table or opens_container:
            depth += 1

        elif text.startswith(close):
            depth -= 1

            if depth == 0:
                return line + 1

    return end


def _tag_end(state: StateBlock, start: int, end: int, name: str) -> int:
    stack = [name]
    active_fence = ""

    for line in range(start + 1, end):
        text = _line(state, line)
        local = state.getLines(line, line + 1, state.blkIndent, False).rstrip("\n").expandtabs(4)
        previous = active_fence
        active_fence = fence_state(local, active_fence)

        if previous or active_fence or local.startswith("    ") or not (match := TAG.fullmatch(text)):
            continue

        tag = match[1]

        if tag == f"end{stack[-1]}":
            stack.pop()

            if not stack:
                return line + 1
        elif tag not in LEAF_TAGS and tag not in {"else", "elsif"} and not tag.startswith("end"):
            stack.append(tag)

    return end
