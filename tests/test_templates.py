import pytest

from markstitch import Bold, For, InlineFor, InlineIf, Paragraph, Slice, UnsupportedFeatureError, Variable


def test_inline_conditional_and_loop_composition() -> None:
    document = Paragraph(
        "Hello ",
        InlineIf("user.admin", Bold("admin"), otherwise="guest"),
        ": ",
        InlineFor("item", "items", Variable("item.name"), "; "),
    )

    result = document.to_yfm(profile="diplodoc")

    assert result == (
        "Hello {% if user.admin %}**admin**{% else %}guest{% endif %}\\: "
        "{% for item in items %}{{ item.name }}; {% endfor %}"
    )


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("user.name", "user.name"),
        (Slice("user.name", 1), "user.name.slice(1)"),
        (Slice("users", 1, 3), "users.slice(1, 3)"),
        (Slice(Slice("users", 1), 0, 2), "users.slice(1).slice(0, 2)"),
    ],
)
def test_variable_expressions(expression: str | Slice, expected: str) -> None:
    variable = Variable(expression, filters=("length",))

    result = variable.to_yfm(profile="diplodoc")

    assert result == f"{{{{ {expected} | length }}}}"


@pytest.mark.parametrize("element", [InlineIf("enabled", "yes"), InlineFor("user", "users", Variable("user"))])
def test_inline_templates_reject_tracker(element: InlineIf | InlineFor) -> None:
    with pytest.raises(UnsupportedFeatureError):
        element.to_yfm()


@pytest.mark.parametrize("element", [InlineIf("x %}{% include evil", "text"), InlineFor("user", "items%}", "text")])
def test_inline_templates_reject_delimiter_injection(element: InlineIf | InlineFor) -> None:
    with pytest.raises(ValueError):
        element.to_yfm(profile="diplodoc")


def test_inline_condition_rejects_block_content() -> None:
    element = InlineIf("enabled", Paragraph("block"))

    with pytest.raises(TypeError, match="inline"):
        element.to_yfm(profile="diplodoc")


@pytest.mark.parametrize("expression", [Slice("users", True), Slice("users", 0, False), Slice("users;evil", 0)])
def test_invalid_slice_arguments(expression: Slice) -> None:
    with pytest.raises(ValueError):
        expression.to_yfm()


@pytest.mark.parametrize(
    ("variable", "collection"),
    [
        ("1item", "items"),
        ("user-name", "items"),
        ("\u044f", "items"),
        (".", "items"),
        ("item..name", "items"),
        ("item", "user-list"),
        ("item", "1items"),
        ("item", "."),
        ("item", "data..items"),
        ("item", "data.1items"),
    ],
)
def test_block_for_rejects_invalid_paths(variable: str, collection: str) -> None:
    element = For(variable, collection, "body")

    with pytest.raises(ValueError, match="dotted variable path"):
        element.to_yfm(profile="diplodoc")


@pytest.mark.parametrize(("variable", "collection"), [("item", "data.items"), ("_item", "_items2")])
def test_block_for_accepts_variable_paths(variable: str, collection: str) -> None:
    element = For(variable, collection, "body")

    result = element.to_yfm(profile="diplodoc")

    assert result == f"{{% for {variable} in {collection} %}}\n\nbody\n\n{{% endfor %}}"
