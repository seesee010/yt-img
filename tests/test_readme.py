import re
from pathlib import Path

import pytest

from yt_img import cli

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text()


def documented_options() -> list[str]:
    return [
        opt
        for action in cli.parser()._actions
        for opt in action.option_strings
        if opt not in ("-h", "--help")
    ]


@pytest.mark.parametrize("option", documented_options())
def test_every_option_is_documented(option: str) -> None:
    assert f"`{option}`" in README


def test_no_stale_options_in_the_table() -> None:
    known = set(documented_options())
    rows = [line for line in README.splitlines() if line.startswith("| `-")]
    assert rows
    for row in rows:
        first_cell = row.split("|")[1]
        for option in re.findall(r"`(-[^`]+)`", first_cell):
            assert option in known, f"README documents unknown option {option}"


def test_documented_defaults_match_the_parser() -> None:
    args = cli.parser().parse_args(["x"])
    for option, value in [
        ("--interval", "10"),
        ("--threshold", "0.05"),
        ("--count", "16"),
        ("--columns", "4"),
        ("--width", "480"),
    ]:
        row = next(
            line
            for line in README.splitlines()
            if line.startswith("|") and f"`{option}`" in line
        )
        assert f"| `{value}` |" in row
        assert float(value) == getattr(args, option.removeprefix("--"))


def test_local_links_exist() -> None:
    targets = re.findall(r"\]\((?!https?://)([^)#]+)\)", README)
    assert targets
    for target in targets:
        assert (ROOT / target).exists(), target
