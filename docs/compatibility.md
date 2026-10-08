# YFM compatibility

The contract was checked against the documentation and pinned renderer on 2026-10-03.
`✓` means the library produces the corresponding markup, not that every deployed server supports it.
`plugin` means Diplodoc requires an additional extension. `—` means the profile rejects the construct.

| Construct / API | Tracker | Wiki | Diplodoc |
| --- | --- | --- | --- |
| `YFM`, `Paragraph`, `Text`, `LineBreak`, `Rule` | ✓ | ✓ | ✓ |
| `Heading`, `Header1` … `Header6`, anchors | ✓ | ✓ | ✓ |
| Collapsible headings: `collapsible=True` | ✓ | ✓ | — |
| `Bold`, `Italic`, `Strike`, `Monospace`, `Superscript`, `Color` | ✓ | ✓ | ✓ |
| `Underline`, `Subscript` | ✓ | ✓ | plugin |
| `Highlight`, `Mention`, `Emoji` | ✓ | ✓ | — |
| `Link`, `ReferenceLink`, `LinkDefinition`, `ReferenceImage` | ✓ | ✓ | ✓ |
| `Link(target=...)` | — | — | ✓ |
| `Image`, dimensions and tooltip | ✓ | ✓ | ✓, different dimension syntax |
| `Image(inline=True / False)` | — | — | ✓ |
| `BulletList`, `NumberedList`, `ListItem`, nested lists | ✓ | ✓ | ✓ |
| `Checklist`, `Task` | `[ ]`, blank lines | `[ ]`, blank lines | `- [ ]`, plugin |
| `Quote`, nested quotes | ✓ | ✓ | ✓ |
| `Code`, `CodeBlock`, language, line numbers | ✓ | ✓ | ✓ |
| `CodeBlock(wrap=True)` | ✓ | ✓ | ✓ |
| `CodeBlock(prompt=...)` | — | — | ✓ |
| Mermaid via `CodeBlock(..., language="mermaid")` | ✓ | ✓ | plugin |
| `Math`, `MathBlock` | ✓ | ✓ | KaTeX plugin |
| `Cut`, `Note`, `Tabs`, `Tab` | ✓ | ✓ | ✓ |
| `Tabs(mode="radio" / "dropdown" / "accordion")` | — | — | ✓ |
| `Tabs(group=...)`, `Tab(selected=True)` | — | — | ✓ |
| `Table`, column alignment | ✓ | ✓ | ✓ |
| `YFMTable`, `Row`, `Cell`, blocks inside cells | ✓ | ✓ | ✓ |
| `Span.LEFT`, `Span.ABOVE`, `Cell(align=...)` | — | — | ✓ |
| `YFMTable(header_rows=..., wide=..., sticky_header=...)` | — | — | ✓ |
| `Attributes` for `YFMTable`, `Row`, `Cell`: id, classes, styles, data/aria/title | — | — | ✓, see renderer limitations |
| `Comment` | ✓ | ✓ | ✓ |
| `File`: link to an existing file | ✓ | ✓ | ✓ |
| `StyledBlock`, `Layout` | ✓ | ✓ | — |
| `RawHTML`: trusted HTML/CSS | ✓ | ✓ | via `Raw`, depends on allowHtml |
| `Toc`, `PageTree`, `WikiInclude`, `Grid` | — | ✓ | — |
| `Iframe`: permissions and allowed domains are controlled by Wiki | — | ✓ | — |
| `Video`: `@[provider](...)` | — | — | ✓ |
| `Term`, `TermDefinition` | — | — | ✓ |
| `Footnote`, `FootnoteDefinition` | — | — | plugin |
| `Include(path, text=..., notitle=...)` | — | — | ✓ |
| `Variable(name, filters=...)`, `If`, `For` | — | — | template generation |
| `InlineIf`, `InlineFor`, `Variable(Slice(...))` | — | — | template generation |
| `Visibility("human" / "agent", ...)` | — | — | ✓ |
| `Raw`, `RawInline`, custom `Element` / `Inline` | unchecked | unchecked | unchecked |

The Diplodoc profile allows these optional constructs but does not install or enable plugins
for the caller. `Footnote` requires `markdown-it-footnote`, `Underline` requires `markdown-it-ins`,
`Subscript` requires `markdown-it-sub`, formulas require KaTeX, and Mermaid requires the
corresponding Diplodoc extension.

## Initial release scope

- The library generates YFM source and parses it into editable nodes.
  HTML rendering, Tracker/Wiki API calls, and documentation builds are outside its scope.
- Standard constructs have dedicated nodes. Use `Raw` / `RawInline` or a custom node
  for third-party plugins and nonstandard attributes outside the `Attributes` contract.
- `If` and `For` are block constructs; `InlineIf` and `InlineFor` are inline constructs.
  Nest a condition in `otherwise` to represent `elsif`. `Slice` generates a method call
  inside a `Variable` expression, including chained calls and filters.
- Project metadata, front matter, `toc.yaml`, presets, localization, redirects, and
  page-constructor belong to the Diplodoc build process and are not modeled by the library.
- Wiki dynamic grids are embedded by ID; creating grids and modifying their data require a separate API.
- Span validation builds a grid of cell owners and checks that each region is rectangular.
  `Span.ABOVE` continues the region's first column, and `Span.LEFT` continues the remaining columns.
  Multiple `Span.ABOVE` markers below one wide cell are rejected because the pinned renderer
  does not handle that alternative notation correctly.
- Complete compatibility with any particular Tracker/Wiki deployment has not been verified.
  Extensions with uncertain support are only allowed in profiles backed by documentation,
  without automatic fallback.

## Parsing and the document tree

`parse()` / `YFM.from_yfm()` convert supported markup into the same classes used for
document construction. Tests cover typed trees, node editing, round trips, directive-like
strings in code, nested tables, and conditions. Composite parsed documents are also
checked using the actual Diplodoc renderer.

Unknown constructs and profile-unsupported extensions are preserved as opaque
`Raw` / `RawInline` nodes in normal mode and raise `ParseError` in strict mode.
This is an intentional **parser** fallback; profile validation for explicitly constructed
typed nodes is unchanged. Parsing does not guarantee exact whitespace preservation or
support for arbitrary markdown-it plugins.

`walk()` traverses the original objects in depth-first preorder; `iter(node)` returns
only immediate children. See the [README](../README.md) for the full contract and an editing example.

<a id="renderer"></a>

## Pinned renderer limitations

Integration tests use `@diplodoc/transform@4.78.3`.

- Attributes `|:{...}`, `||:{...}`, and `::{...}` are recognized at their respective levels
  and stored in `token.meta.rawAttrs`. This version does not propagate all general attributes
  (`class`, `style`, `id`, `data-*`) from the new syntax into HTML; tests verify correct parsing.
  `align`, `header-rows`, and spans are separately checked in HTML. The library does not
  replace or patch the renderer.
- Liquid strips trailing spaces from each loop iteration. Use a meaningful separator
  such as `;` instead of whitespace alone when needed.
- If the entire document is a single substitution with a numeric result, such as
  `{{ users | length }}`, this version of `transform` fails with `input.split is not a function`.
  The same substitution works within text (`Count: {{ users | length }}`). This is a limitation
  of the external renderer, not a change to the syntax generated by the library.

## References

### Tracker (primary profile)

- [Inline formatting, headings, lists, code, formulas, mentions, comments](https://yandex.ru/support/tracker/ru/user/syntax-yfm.md)
- [Notes, cuts, tabs, code blocks, layout, block](https://yandex.ru/support/tracker/ru/wysiwyg/block-format.md)
- [Tables](https://yandex.ru/support/tracker/ru/wysiwyg/tables-format.md)
- [Images](https://yandex.ru/support/tracker/ru/wysiwyg/images.md)
- [Files](https://yandex.ru/support/tracker/ru/wysiwyg/file.md)
- [Mermaid](https://yandex.ru/support/tracker/ru/wysiwyg/diagrams.md)
- [HTML blocks](https://yandex.ru/support/tracker/ru/wysiwyg/html-block.md)

The Tracker documentation explicitly reuses `yfmeditor` sources from the Wiki documentation.

### Wiki

- [Table of contents and section structure](https://yandex.ru/support/wiki/ru/wysiwyg/toc-structure.md)
- [Include](https://yandex.ru/support/wiki/ru/wysiwyg/include.md)
- [Dynamic grids](https://yandex.ru/support/wiki/ru/wysiwyg/grid.md)
- [Iframe](https://yandex.ru/support/wiki/ru/wysiwyg/embed-content.md)

### Diplodoc

- [Syntax and basic markup](https://diplodoc.com/docs/en/syntax/)
- [Links](https://diplodoc.com/docs/en/syntax/links.md)
- [Multiline tables and attributes](https://diplodoc.com/docs/en/syntax/tables/multiline.md)
- [Interactive element parameters](https://diplodoc.com/docs/en/syntax/interactive-elements/common-params.md)
- [Media](https://diplodoc.com/docs/en/syntax/media.md)
- [Code](https://diplodoc.com/docs/en/syntax/code.md)
- [Terms](https://diplodoc.com/docs/en/syntax/term.md)
- [Variables, conditions, loops](https://diplodoc.com/docs/en/syntax/vars.md)
- [Includes](https://diplodoc.com/docs/en/syntax/includes.md)
- [Additional plugins](https://diplodoc.com/docs/en/syntax/additional.md)
- [Audience-specific content](https://diplodoc.com/docs/en/syntax/audience.md)
