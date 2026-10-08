import pytest

from markstitch import Grid, parse


def test_grid_default_does_not_request_nonexistent_column_one() -> None:
    grid = Grid("4334c572-65e3-4a0b-a465-a748f49a0c23")

    result = grid.to_yfm(profile="wiki")

    assert result == '{% wgrid id="4334c572-65e3-4a0b-a465-a748f49a0c23" readonly="1" num="1" %}'


def test_grid_sort_is_column_slug() -> None:
    grid = Grid("test-grid", sort="case")

    result = grid.to_yfm(profile="wiki")

    assert result == '{% wgrid id="test-grid" readonly="1" num="1" sort="case" %}'


def test_parser_preserves_sort_column_slug() -> None:
    source = '{% wgrid id="test-grid" readonly="1" num="1" sort="case" %}'

    document = parse(source, profile="wiki", strict=True)

    grid = next(node for node in document.walk() if isinstance(node, Grid))
    assert grid.sort == "case"
    assert document.to_yfm() == source


def test_parser_does_not_invent_sort_when_absent() -> None:
    source = '{% wgrid id="test-grid" readonly="1" num="1" %}'

    document = parse(source, profile="wiki", strict=True)

    grid = next(node for node in document.walk() if isinstance(node, Grid))
    assert grid.sort is None
    assert document.to_yfm() == source


@pytest.mark.parametrize("value", [True, False])
def test_boolean_sort_is_rejected(value: bool) -> None:
    grid = Grid("test-grid", sort=value)

    with pytest.raises(ValueError, match="column slug"):
        grid.to_yfm(profile="wiki")
