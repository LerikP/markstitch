# Markstitch

[![CI][ci-badge]][ci-url]
[![Publish to PyPI][publish-badge]][publish-url]
[![PyPI version][pypi-badge]][pypi-url]
[![Python 3.12+][python-badge]][pypi-url]
[![MIT License][license-badge]][license-url]
[![Type checks: mypy, ty, Pyrefly][types-badge]][ci-url]

Compose, parse, and edit YFM documents in Python.

Build documents for **Yandex Tracker**, Yandex Wiki, and Diplodoc using Python objects.
Requires Python 3.12+. Import the library as `markstitch`. Document generation has no
runtime dependencies; parsing requires the `parser` extra.

## Installation

Install from [PyPI][pypi-url]:

```sh
pip install markstitch
```

To parse and edit existing documents, include the optional parser:

```sh
pip install "markstitch[parser]"
```

Or add it to a uv project:

```sh
uv add "markstitch[parser]"
```

## Quick start

```python
from markstitch import YFM, Header3, Link, NumberedList

document = YFM(
    Header3("Test1"),
    NumberedList("One", "Two", "Three"),
    Link(text="link", href="example.com"),
)

text = document.to_yfm()
```

Output:

```markdown
### Test1

1. One
2. Two
3. Three

[link](example.com)
```

Pass `text` to any description or comment field that accepts YFM.
The library produces a string; network requests and attachment uploads are the caller's responsibility.

## Composition

```python
from markstitch import (
    YFM,
    Bold,
    BulletList,
    Cell,
    Checklist,
    CodeBlock,
    Cut,
    Header2,
    Link,
    ListItem,
    Note,
    Paragraph,
    Row,
    Tab,
    Tabs,
    Task,
    YFMTable,
)

document = YFM(
    Header2("Results", anchor="results", collapsible=True),
    Paragraph("Status: ", Bold("ready"), ". ", Link("Report", "https://example.com")),
    Note("Verify after deployment", kind="warning", title="Important"),
    Cut(
        "Details",
        BulletList(ListItem("First stage", BulletList("Substep")), "Second stage"),
        CodeBlock("print('hello')", language="python", line_numbers=True),
    ),
    Tabs(Tab("Linux", "Instructions"), Tab("macOS", "Instructions")),
    Checklist(Task("Implementation", checked=True), Task("Verification")),
    YFMTable(
        Row(Bold("Stage"), Bold("Steps")),
        Row("Run", Cell(BulletList("Install", "Execute"))),
    ),
)
```

- `YFM(*elements)` and block containers separate their children with a blank line.
- `Paragraph(*parts)` and `Text(*parts)` join inline elements **without inserting spaces**.
- `ListItem(*blocks)` nests multiple blocks inside a single list item.
- `Heading(text, level=1)` and `Header1` through `Header6` accept inline content,
  `anchor=`, and `collapsible=`.
- `NumberedList(*items, start=1)` calculates indentation from the number's width, including after `9.`.
- `Table(headers, rows, align=...)` creates a simple table; `YFMTable(Row(...), ...)` creates a multiline table.
- All nodes support `.to_yfm(profile=...)`. `str(element)` uses the Tracker profile.
- The returned string has no automatically appended trailing newline.
- Repeated rendering does not mutate the tree.

## Parsing and tree traversal

The optional `parser` extra uses `markdown-it-py>=4.0.0`.
When working from source, run `uv sync --locked --extra parser`.

```python
from markstitch import Link, parse

document = parse(
    "### Report\n\nSee **[result](/old)**",
    profile="tracker",
    strict=True,
)

# Immediate children: Heading and Paragraph.
top_level = list(document)

# Depth-first traversal, visiting each parent before its children.
for node in document.walk():
    if isinstance(node, Link):
        node.href = "/new"

updated = document.to_yfm()
```

The equivalent class method is `YFM.from_yfm(source, profile="wiki", strict=False)`.
Both return a regular `YFM` document, using the same node types as document construction.
The profile is stored in `document.profile` and used by `.to_yfm()` unless explicitly overridden.

### Tree behavior

- `iter(element)` / `element.iter_children()` return immediate child **elements**.
  `walk()` visits all elements in depth-first preorder, including the root.
- Traversal returns the original objects. Changing `Link.href`, `Heading.text`, `Task.checked`,
  or other fields affects subsequent serialization.
- Traversal includes inline content in headings and links, `YFMTable` rows and cells,
  regular `Table` headers and cells, and both branches of `If` / `InlineIf`.
- URLs, CSS attributes, and other metadata are not child nodes. Strings passed to constructors
  remain scalar values on their owning node. Parsed plain text becomes `Text` nodes visible
  to `walk()`, with its parts stored in `Text.children`.
- `Row` is an iterable structural node whose `.to_yfm()` returns a table row fragment.
  Full span validation happens when serializing the entire `YFMTable`.
- A shared node used twice is visited twice. Cycles raise `ValueError`.
  Traversal is iterative, so tree depth does not consume the Python call stack.
- Custom nodes can override `iter_children()` to participate in traversal.

### Parser behavior

The parser supports CommonMark blocks and inline formatting, the library's YFM node syntax,
both table types, spans and attributes, profile-specific macros, block and inline templates,
link definitions, terms, and footnotes.

- By default, unknown or profile-unsupported constructs are preserved as `Raw` / `RawInline`.
  If an unknown argument prevents part of a block from being parsed correctly, the entire
  original block is preserved.
- With `strict=True`, these cases raise `ParseError` instead. The message includes the reason
  and, for block errors, the line number within the parsed fragment.
- The parser normalizes list and formatting markers, item numbers, indentation, blank lines,
  line endings, and attributes. Original formatting is **not preserved byte for byte**.
  Unknown raw fragments retain their internal text; separators follow the usual `YFM` behavior.
- Tight and loose lists remain distinct through
  `BulletList(..., loose=True)` / `NumberedList(..., loose=True)`.
- A shortcut reference `[label]` with a definition resolves to `Link`;
  the explicit form `[text][label]` remains a `ReferenceLink`.
- Recursive parsing is limited to 64 internal levels. Exceeding this limit raises `ParseError`,
  even in non-strict mode.
- The parser does not execute templates or fetch includes, images, or files.
  **Parsing is not sanitization:** preserved `Raw` nodes may contain original HTML/YFM markup.
  Safe display is the responsibility of the target renderer.

Runnable example: `uv run --extra parser python examples/parse_document.py`.

## Profiles

```python
from markstitch import Profile

text = document.to_yfm()  # Tracker by default
text = document.to_yfm(profile=Profile.WIKI)  # or "wiki"
text = document.to_yfm(profile=Profile.DIPLODOC)  # or "diplodoc"
```

Profiles select syntax and validate extension support. For example, Tracker/Wiki image
dimensions appear inside the link as `=100x200`, while Diplodoc uses
`{width=100 height=200}` attributes. Checklist serialization also differs.

Features without confirmed support in a profile raise `UnsupportedFeatureError`,
including in deeply nested nodes. Invalid values raise `ValueError`; incompatible content
types raise `TypeError`. Validation happens during `.to_yfm()`, not node construction.

**Profiles follow published documentation; they do not detect server capabilities.**
The target service's editor version and enabled plugins may differ.

The `Grid.sort` parameter is an optional **column slug**, for example
`Grid(grid_id, sort="case")`. It defaults to `None`, which omits the attribute.
Boolean values are rejected: the Wiki widget interprets `sort="1"` as sorting by a column
named `1`, not as enabling sorting.

Dynamic cell formatting is configured separately on the Wiki resource: a string column
needs `format="yfm"` when created. `format=null` means plain text, even if the entire grid
has `rich_text_format="yfm"`. `Grid` embeds a resource by ID without changing its column schema.

## Text and raw markup

Plain strings are escaped. Use nodes such as `Bold`, `Link`, `Color`, and `Code` for formatting.
Use `Raw` (block) or `RawInline` (inline) for trusted, preformatted markup.
`RawHTML` wraps trusted HTML/CSS in a Tracker/Wiki HTML block; it is **not a sanitizer**.

`If.expression` is a Diplodoc condition explicitly written by the document author.
`Variable`, `For`, `If`, and `Include` only generate syntax: they neither execute templates
nor read files. Do not pass untrusted input to `Raw`, `RawInline`, `RawHTML`, or `If.expression`.
Rendering, allowed iframe domains, and HTML policies are controlled by the target service.

URLs may be relative or use the `http`, `https`, or `mailto` scheme.
Other schemes, including `tel`, are rejected when serializing typed nodes.

Place `TermDefinition` nodes at the end of the document, as required by Diplodoc.
`ReferenceLink` / `ReferenceImage` nodes need a matching `LinkDefinition`.

## Table attributes and SVG (Diplodoc)

```python
from markstitch import Attributes, Cell, Image, Row, YFMTable

table = YFMTable(
    Row(
        Cell("Value", align="center", attributes=Attributes(style={"width": "300px"})),
        attributes=Attributes(classes=("summary",)),
    ),
    attributes=Attributes(id="report", extra={"data-kind": "summary"}),
)
text = table.to_yfm(profile="diplodoc")
image = Image("_images/icon.svg", width=40, inline=False)
```

`Attributes` supports `id`, `classes`, CSS declarations in `style`, and additional
`data-*`, `aria-*`, and `title` attributes through `extra`. CSS values can be keywords,
dimensions, or colors; functions, URLs, embedded declarations, and markup delimiters
are rejected. Attribute handling in HTML depends on the renderer version:
see [pinned renderer limitations](https://github.com/LerikP/markstitch/blob/main/docs/compatibility.md#renderer).

The document author should supply trusted values for `classes` and `style`. Do not pass
user input to them: CSS classes may activate JavaScript behavior in the target service,
and CSS syntax validation does not make arbitrary styling safe.
`Attributes` is not a sanitizer for user-supplied CSS or HTML attributes.

Use `Span.LEFT` and `Span.ABOVE` to merge cells. To continue a multi-column rectangle
on the next row, put `Span.ABOVE` in its first column and `Span.LEFT` in the remaining columns.
The entire grid and each merged rectangle are validated: partial continuations, wider
lower rows, and L-shaped regions raise `ValueError`.

## Inline templates and slicing (Diplodoc)

```python
from markstitch import Bold, InlineFor, InlineIf, Paragraph, Slice, Variable

template = Paragraph(
    "Role: ",
    InlineIf("user.admin == true", Bold("admin"), otherwise="guest"),
    "; names: ",
    InlineFor("user", "users", Variable(Slice("user.name", 0, 3)), ";"),
)
text = template.to_yfm(profile="diplodoc")
```

`InlineIf` and `InlineFor` accept only inline elements. Pass an `InlineIf` as `otherwise`
to nest conditions. `Slice(source, begin, end=None)` supports integer indices, including
negative values, and another `Slice` as its source. Pass it to `Variable` with or without
filters, such as `filters=("length",)`. Diplodoc executes the template; the library only serializes it.

## Syntax coverage

See the [compatibility matrix and references](https://github.com/LerikP/markstitch/blob/main/docs/compatibility.md)
for built-in constructs, optional plugins, and remaining limitations. Custom nodes can represent third-party syntax:

```python
from markstitch import Element, Profile


class CustomBlock(Element):
    def _render(self, profile: Profile) -> str:
        return "trusted preformatted markup"
```

Inherit from `Inline` to define a custom inline element.

## Checks and builds

Set up a source checkout to run the examples, tests, and development tools:

```sh
git clone https://github.com/LerikP/markstitch.git
cd markstitch
uv sync --locked --extra parser
uv run python examples/tracker.py
uv run ruff format --check .
uv run ruff check .
uv run --extra parser mypy markstitch
uv run --extra parser ty check markstitch
uv run --extra parser pyrefly check markstitch
# Python behavior without Node.js:
uv run --extra parser pytest -m 'not renderer'

# Integration with the pinned YFM renderer (requires Node.js 24+):
npm ci --registry=https://registry.npmjs.org/ --ignore-scripts --no-audit --no-fund
uv run --extra parser pytest

uv build
uv run twine check --strict dist/*
```

Renderer tests use `@diplodoc/transform` to check HTML structure, nesting, spans,
attribute parsing, and escaping. Template tests explicitly enable Liquid and cover
both conditional branches, loops, slicing, and filters. Wiki-specific macros and
Tracker editor syntax are checked against their text contracts.

Ruff, mypy, ty, Pyrefly, pytest, and Twine are development dependencies with versions pinned in `uv.lock`.
Python dependencies come from PyPI; the renderer comes from npm.

## CI and publishing

GitHub Actions runs the full test suite on Python 3.12, 3.13, and 3.14 for pull requests
and pushes to `main`. It checks formatting and lint with Ruff and types with mypy, ty, and Pyrefly.
It also builds the wheel and source distribution, validates their metadata, and smoke-tests both installed distributions
with and without the parser extra. Successful builds expose a `python-distributions` artifact.

Publishing a GitHub Release runs the same checks and uploads the resulting distributions
to PyPI through Trusted Publishing. The release tag must match the package version exactly,
for example `v0.1.0` for version `0.1.0`. Pushing a commit or tag alone does not publish a package.

See [releasing](https://github.com/LerikP/markstitch/blob/main/docs/releasing.md) for the one-time PyPI setup and release procedure.

## Package structure

- `core.py`: node interfaces, profiles, escaping, links, and document composition.
- `inline.py`: inline formatting, images, and inline code.
- `blocks.py`: headings, lists, code blocks, cuts, notes, and tabs.
- `tables.py`: simple and multiline tables.
- `attributes.py`: typed attributes for tables, rows, and cells.
- `extensions.py`: service macros, link definitions, terms, and footnotes.
- `templates.py`: Diplodoc template syntax generation.
- `parser/`: CommonMark/YFM tokenization and conversion to public nodes.

The API is inspired by [SnakeMD](https://www.snakemd.io/en/latest/); no source code was copied.

## License

Markstitch is licensed under the [MIT License][license-url].

[ci-badge]: https://github.com/LerikP/markstitch/actions/workflows/ci.yml/badge.svg?branch=main
[ci-url]: https://github.com/LerikP/markstitch/actions/workflows/ci.yml
[publish-badge]: https://github.com/LerikP/markstitch/actions/workflows/publish.yml/badge.svg?event=release
[publish-url]: https://github.com/LerikP/markstitch/actions/workflows/publish.yml
[pypi-badge]: https://img.shields.io/pypi/v/markstitch?logo=pypi&logoColor=white
[pypi-url]: https://pypi.org/project/markstitch/
[python-badge]: https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white
[license-badge]: https://img.shields.io/pypi/l/markstitch
[license-url]: https://github.com/LerikP/markstitch/blob/main/LICENSE
[types-badge]: https://img.shields.io/badge/types-mypy%20%7C%20ty%20%7C%20Pyrefly-3776AB
