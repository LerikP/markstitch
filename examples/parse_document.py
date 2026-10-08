"""Parse, traverse and edit a document without sending it to any service."""

from markstitch import YFM, Link


def update_links(source: str) -> str:
    document = YFM.from_yfm(source, profile="tracker", strict=True)

    for node in document.walk():
        if isinstance(node, Link) and node.href == "/old":
            node.href = "/new"

    return document.to_yfm()


if __name__ == "__main__":
    source = '### Report\n\n{% cut "Details" %}\n\nSee **[result](/old)**\n\n{% endcut %}'
    print(update_links(source))  # noqa: T201 — this example intentionally prints the edited document.
