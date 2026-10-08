import subprocess
import sys
from pathlib import Path


def test_document_generation_without_parser_dependency() -> None:
    source = "from markstitch import YFM, Header3; print(YFM(Header3('Hello')).to_yfm())"

    result = subprocess.run(  # noqa: S603 — fixed interpreter and source; -S excludes third-party packages.
        [sys.executable, "-S", "-c", source],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "### Hello\n"
