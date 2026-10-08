from markstitch import YFM, Header3, Link, NumberedList


def test_requested_document() -> None:
    document = YFM(
        Header3("Test1"),
        NumberedList("One", "Two", "Three"),
        Link(text="link", href="example.com"),
    )

    result = document.to_yfm()

    assert result == "### Test1\n\n1. One\n2. Two\n3. Three\n\n[link](example.com)"
