import pytest

from markstitch import Bold, BulletList, Code, Cut
from markstitch.tables import Cell, Row, Span, Table, YFMTable


def test_simple_table() -> None:
    table = Table(["Name", "Value"], [[Bold("a|b"), Code("x|y")]], align=["left", "right"])

    result = table.to_yfm()

    assert result == "| Name | Value |\n| :--- | ---: |\n| **a\\\\|b** | `x\\|y` |"


def test_multiline_table() -> None:
    table = YFMTable(Row(Bold("Title"), Bold("Details")), Row("one", Cell(BulletList("a", "b"), Cut("More", "body"))))

    result = table.to_yfm()

    assert result == (
        '#|\n|| **Title** | **Details** ||\n||\none\n|\n- a\n- b\n\n{% cut "More" %}\n\nbody\n\n{% endcut %}\n||\n|#'
    )


def test_diplodoc_table_attributes_and_spans() -> None:
    table = YFMTable(
        Row(Cell("wide", align="center"), Span.LEFT), Row(Span.ABOVE, Span.LEFT), header_rows=1, wide=True
    )

    result = table.to_yfm(profile="diplodoc")

    assert result == '#|\n|:{header-rows="1"}\n||::{align="center"} wide | > ||\n|| ^ | > ||\n|# {wide-content}'


@pytest.mark.parametrize(
    ("wide", "suffix"),
    [(False, " {sticky-header}"), (True, " {wide-content sticky-header}")],
)
def test_sticky_header_is_attached_to_table_closing_line(wide: bool, suffix: str) -> None:
    table = YFMTable(Row("header"), Row("body"), sticky_header=True, wide=wide)

    result = table.to_yfm(profile="diplodoc")

    assert result == f"#|\n|| header ||\n|| body ||\n|#{suffix}"


@pytest.mark.parametrize("table", [Table([], []), Table(["a"], [["a", "b"]]), YFMTable(Row("a"), Row("a", "b"))])
def test_rejects_invalid_table_dimensions(table: Table | YFMTable) -> None:
    with pytest.raises(ValueError):
        table.to_yfm()
