import os
from pathlib import Path

CHECK = Path(__file__).resolve().parent.parent / "scripts" / "check"


def test_check_script_is_executable() -> None:
    assert CHECK.is_file()
    assert os.access(CHECK, os.X_OK)


def test_check_script_runs_every_gate() -> None:
    text = CHECK.read_text()
    for gate in ("ruff check", "ruff format --check", "mypy", "pytest"):
        assert f"uv run {gate}" in text
    assert "set -euo pipefail" in text
