import pytest

from markstitch import Row, Span, YFMTable


@pytest.mark.parametrize(
    "table",
    [
        YFMTable(Row("a", Span.LEFT), Row(Span.ABOVE, "b")),
        YFMTable(Row("a", "b"), Row(Span.ABOVE, Span.LEFT)),
        YFMTable(Row("a", Span.LEFT), Row("b", Span.ABOVE)),
        YFMTable(Row("a", Span.LEFT), Row(Span.ABOVE, Span.ABOVE)),
        YFMTable(Row("a", Span.LEFT, Span.LEFT), Row(Span.ABOVE, Span.LEFT, "b")),
        YFMTable(Row("a", "b", "c"), Row(Span.ABOVE, Span.LEFT, Span.ABOVE)),
    ],
)
def test_rejects_nonrectangular_or_ambiguous_spans(table: YFMTable) -> None:
    with pytest.raises(ValueError, match=r"[Ss]pan"):
        table.to_yfm(profile="diplodoc")


def test_combined_spans_with_independent_neighbors() -> None:
    table = YFMTable(
        Row("a", Span.LEFT, "b"),
        Row(Span.ABOVE, Span.LEFT, Span.ABOVE),
        Row("c", "d", Span.ABOVE),
    )

    result = table.to_yfm(profile="diplodoc")

    assert result == "#|\n|| a | > | b ||\n|| ^ | > | ^ ||\n|| c | d | ^ ||\n|#"


def test_text_span_symbols_do_not_merge() -> None:
    table = YFMTable(Row("^", ">"))

    result = table.to_yfm(profile="diplodoc")

    assert result == "#|\n|| \\^ | \\> ||\n|#"
