import pytest

from markstitch import Attributes, BulletList, Cell, Image, Row, UnsupportedFeatureError, YFMTable


def test_attributes_at_each_table_level() -> None:
    table = YFMTable(
        Row(
            Cell("text", align="center", attributes=Attributes(style={"width": "400px"})),
            attributes=Attributes(classes=("header",), extra={"data-kind": "total"}),
        ),
        attributes=Attributes(id="report", classes=("wide",), style={"border-width": "1px"}),
    )

    result = table.to_yfm(profile="diplodoc")

    assert result == (
        '#|\n|:{id="report" class="wide" style="border-width: 1px"}\n'
        '||:{class="header" data-kind="total"}::{align="center" style="width: 400px"} text ||\n|#'
    )


def test_attributes_stay_on_delimiter_line_with_multiline_content() -> None:
    table = YFMTable(
        Row(
            Cell(BulletList("one", "two"), attributes=Attributes(classes=("steps",))),
            attributes=Attributes(classes=("row",)),
        )
    )

    result = table.to_yfm(profile="diplodoc")

    assert result == '#|\n||:{class="row"}::{class="steps"}\n- one\n- two\n||\n|#'


@pytest.mark.parametrize(
    "element",
    [
        YFMTable(Row("x"), attributes=Attributes(id="table")),
        YFMTable(Row("x", attributes=Attributes(id="row"))),
        YFMTable(Row(Cell("x", attributes=Attributes(id="cell")))),
    ],
)
def test_tracker_rejects_table_attributes(element: YFMTable) -> None:
    with pytest.raises(UnsupportedFeatureError):
        element.to_yfm()


@pytest.mark.parametrize(
    "attributes",
    [
        Attributes(id='a"}'),
        Attributes(classes=("a b",)),
        Attributes(style={"width": "1px; color: red"}),
        Attributes(style={"background": "url(https://example.com)"}),
        Attributes(extra={"onclick": "alert(1)"}),
        Attributes(extra={"data-note": "bad|value"}),
    ],
)
def test_attributes_reject_markup_and_css_injection(attributes: Attributes) -> None:
    with pytest.raises(ValueError):
        attributes.to_yfm()


@pytest.mark.parametrize(("inline_svg", "expected"), [(False, "false"), (True, "true")])
def test_svg_inline_setting(inline_svg: bool, expected: str) -> None:
    image = Image("icon.svg", width=40, inline=inline_svg)

    result = image.to_yfm(profile="diplodoc")

    assert result == f"![](icon.svg){{width=40 inline={expected}}}"


def test_tracker_rejects_svg_inline_setting() -> None:
    image = Image("icon.svg", inline=False)

    with pytest.raises(UnsupportedFeatureError):
        image.to_yfm()
