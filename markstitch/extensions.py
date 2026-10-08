"""Profile-specific constructs. These serialize markup; they perform no I/O."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from markstitch.core import (
    MAX_HEADING_LEVEL,
    Container,
    Element,
    Inline,
    Profile,
    blocks,
    choice,
    destination,
    directive,
    escape,
    identifier,
    indent,
    inline,
    one_line,
    positive,
    quoted,
    reference_label,
    require,
)


@dataclass
class File(Element):
    src: str
    name: str
    mime_type: str | None = None

    def _render(self, profile: Profile) -> str:
        mime = f" type={quoted(self.mime_type)}" if self.mime_type is not None else ""
        return f"{{% file src={quoted(destination(self.src))} name={quoted(self.name)}{mime} %}}"


@dataclass
class Video(Element):
    src: str
    provider: str = ""

    def _render(self, profile: Profile) -> str:
        require(profile, "Video", Profile.DIPLODOC)
        choice(
            self.provider, {"", "yandex", "rutube", "vk", "youtube", "vimeo", "vine", "osf", "prezi"}, "video provider"
        )
        return f"@[{self.provider}]({destination(self.src)})"


@dataclass
class Iframe(Element):
    src: str
    width: int = 640
    height: int = 360
    scrolling: str = "auto"
    frameborder: bool = False
    allow: str = ""

    def _render(self, profile: Profile) -> str:
        require(profile, "Iframe", Profile.WIKI)
        url = destination(self.src)

        if urlsplit(self.src).scheme != "https":
            raise ValueError("Iframe requires an HTTPS URL")

        positive(self.width, "width")
        positive(self.height, "height")
        choice(self.scrolling, {"auto", "yes", "no"}, "scrolling")
        return (
            f'/iframe/(src={quoted(url)} width="{self.width}" height="{self.height}" '
            f'frameborder="{int(self.frameborder)}" scrolling="{self.scrolling}" allow={quoted(self.allow)})'
        )


@dataclass
class RawHTML(Element):
    html: str

    def _render(self, profile: Profile) -> str:
        require(profile, "RawHTML", Profile.TRACKER, Profile.WIKI)

        if any(line.strip().startswith(":::") for line in self.html.splitlines()):
            raise ValueError("HTML must not contain a container delimiter")

        return f"::: html\n\n{self.html}\n\n:::"


class StyledBlock(Container):
    def __init__(
        self,
        *children: Element | str,
        align: str | None = None,
        width: int | None = None,
        padding: str | None = None,
        border: str | None = None,
        border_size: str | None = None,
        border_color: str | None = None,
        col: int | None = None,
    ) -> None:
        super().__init__(*children)
        self.align, self.width, self.padding = align, width, padding
        self.border, self.border_size, self.border_color = border, border_size, border_color
        self.col = col

    def _render(self, profile: Profile) -> str:
        require(profile, "StyledBlock", Profile.TRACKER, Profile.WIKI)
        options = {
            "align": (self.align, {"left", "center", "right"}),
            "padding": (self.padding, {"xs", "s", "m", "l", "xl"}),
            "border": (self.border, {"solid", "dashed"}),
            "borderSize": (self.border_size, {"xs", "s", "m", "l"}),
            "borderColor": (self.border_color, {"info", "tip", "warning", "alert"}),
        }
        attributes = {
            name: choice(value, allowed, name) for name, (value, allowed) in options.items() if value is not None
        }

        if self.width is not None:
            attributes["width"] = f"{positive(self.width, 'width')}"

        if self.col is not None:
            if positive(self.col, "col") > 12:
                raise ValueError("Column width must be between 1 and 12")

            attributes["col"] = f"{self.col}"

        order = ("align", "width", "padding", "border", "borderSize", "borderColor", "col")
        arguments = " ".join(f"{name}={attributes[name]}" for name in order if name in attributes)
        return directive("block", blocks(self.children, profile), arguments=arguments)


class Layout(Container):
    def __init__(self, *children: StyledBlock, gap: str = "l", cols: str = "auto", justify: str = "start") -> None:
        super().__init__(*children)
        self.gap, self.cols, self.justify = gap, cols, justify

    def _render(self, profile: Profile) -> str:
        require(profile, "Layout", Profile.TRACKER, Profile.WIKI)

        if not self.children or any(not isinstance(child, StyledBlock) for child in self.children):
            raise TypeError("Layout requires StyledBlock children")

        choice(self.gap, {"xs", "s", "m", "l", "xl"}, "gap")
        choice(self.cols, {"auto"}, "cols")
        choice(self.justify, {"start", "center", "end"}, "justify")
        return directive(
            "layout",
            blocks(self.children, profile),
            arguments=f"gap={self.gap} cols={self.cols} justify={self.justify}",
        )


@dataclass
class Toc(Element):
    page: str | None = None
    start: int = 1
    end: int = MAX_HEADING_LEVEL

    def _render(self, profile: Profile) -> str:
        require(profile, "Toc", Profile.WIKI)

        if not 1 <= self.start <= self.end <= MAX_HEADING_LEVEL:
            raise ValueError(f"Expected 1 <= start <= end <= {MAX_HEADING_LEVEL}")

        page = f"page={quoted(self.page)} " if self.page is not None else ""
        return f'{{% toc {page}from="h{self.start}" to="h{self.end}" %}}'


@dataclass
class PageTree(Element):
    page: str
    depth: int = 3
    sort: str = "asc"
    sort_by: str = "title"

    def _render(self, profile: Profile) -> str:
        require(profile, "PageTree", Profile.WIKI)
        positive(self.depth, "depth")
        choice(self.sort, {"asc", "desc"}, "sort")
        choice(self.sort_by, {"title", "created_at", "modified_at"}, "sort_by")
        return (
            f'{{% tree page={quoted(self.page)} depth="{self.depth}" sort="{self.sort}" sort_by="{self.sort_by}" %}}'
        )


@dataclass
class WikiInclude(Element):
    page: str
    start: str | None = None
    end: str | None = None
    warning: bool = True

    def _render(self, profile: Profile) -> str:
        require(profile, "WikiInclude", Profile.WIKI)
        warning = "true" if self.warning else "false"
        start = f" from={quoted(identifier(self.start))}" if self.start is not None else ""
        end = f" to={quoted(identifier(self.end))}" if self.end is not None else ""
        return f'{{% include page={quoted(self.page)} warning="{warning}"{start}{end} %}}'


@dataclass
class Grid(Element):
    id: str
    readonly: bool = True
    numbers: bool = True
    sort: str | None = None
    columns: tuple[str, ...] = ()
    filter: str | None = None

    def _render(self, profile: Profile) -> str:
        require(profile, "Grid", Profile.WIKI)

        if self.sort is not None and not isinstance(self.sort, str):
            raise ValueError("sort must be a column slug or None, not a boolean")

        sorting = f" sort={quoted(identifier(self.sort))}" if self.sort is not None else ""
        columns = (
            f" columns={quoted(', '.join(identifier(column) for column in self.columns))}" if self.columns else ""
        )
        filtering = f" filter={quoted(self.filter)}" if self.filter is not None else ""
        return (
            f'{{% wgrid id={quoted(identifier(self.id))} readonly="{int(self.readonly)}" '
            f'num="{int(self.numbers)}"{sorting}{columns}{filtering} %}}'
        )


@dataclass
class Include(Element):
    path: str
    text: str = ""
    notitle: bool = False

    def _render(self, profile: Profile) -> str:
        require(profile, "Include", Profile.DIPLODOC)
        modifier = " notitle" if self.notitle else ""
        return f"{{% include{modifier} [{escape(one_line(self.text))}]({destination(self.path)}) %}}"


@dataclass
class ReferenceLink(Inline):
    _child_fields = ("text",)

    text: Inline | str
    label: str

    def _render(self, profile: Profile) -> str:
        return f"[{inline(self.text, profile)}][{reference_label(self.label)}]"


@dataclass
class ReferenceImage(Inline):
    alt: str
    label: str

    def _render(self, profile: Profile) -> str:
        return f"![{escape(one_line(self.alt))}][{reference_label(self.label)}]"


@dataclass
class LinkDefinition(Element):
    label: str
    href: str
    title: str | None = None

    def _render(self, profile: Profile) -> str:
        title = f" {quoted(self.title)}" if self.title is not None else ""
        return f"[{reference_label(self.label)}]: {destination(self.href)}{title}"


@dataclass
class Term(Inline):
    _child_fields = ("text",)

    text: Inline | str
    label: str

    def _render(self, profile: Profile) -> str:
        require(profile, "Term", Profile.DIPLODOC)
        return f"[{inline(self.text, profile)}](*{identifier(self.label)})"


class TermDefinition(Container):
    def __init__(self, label: str, *children: Element | str) -> None:
        super().__init__(*children)
        self.label = label

    def _render(self, profile: Profile) -> str:
        require(profile, "TermDefinition", Profile.DIPLODOC)
        return f"[*{identifier(self.label)}]: {blocks(self.children, profile)}"


@dataclass
class Footnote(Inline):
    label: str

    def _render(self, profile: Profile) -> str:
        require(profile, "Footnote (requires markdown-it-footnote)", Profile.DIPLODOC)
        return f"[^{identifier(self.label)}]"


class FootnoteDefinition(Container):
    def __init__(self, label: str, *children: Element | str) -> None:
        super().__init__(*children)
        self.label = label

    def _render(self, profile: Profile) -> str:
        require(profile, "FootnoteDefinition (requires markdown-it-footnote)", Profile.DIPLODOC)
        first, separator, rest = blocks(self.children, profile).partition("\n")
        continuation = f"\n{indent(rest, 4)}" if separator else ""
        return f"[^{identifier(self.label)}]: {first}{continuation}"


class Visibility(Container):
    def __init__(self, audience: str, *children: Element | str) -> None:
        super().__init__(*children)
        self.audience = audience

    def _render(self, profile: Profile) -> str:
        require(profile, "Visibility", Profile.DIPLODOC)
        choice(self.audience, {"human", "agent"}, "audience")
        return f":::visibility {self.audience}\n{blocks(self.children, profile)}\n:::"
