import itertools
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

VideoFactory = Callable[..., Path]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-network",
        action="store_true",
        help="run tests that need internet access",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-network"):
        return
    skip = pytest.mark.skip(reason="needs --run-network")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


@pytest.fixture
def make_video(tmp_path: Path) -> VideoFactory:
    """Build a 160x90 video of solid colours, *seconds* long each."""
    counter = itertools.count()

    def make(
        colors: Sequence[str] = ("red",),
        seconds: float = 10,
        suffix: str = ".mp4",
    ) -> Path:
        out = tmp_path / f"video{next(counter)}{suffix}"
        inputs: list[str] = []
        for color in colors:
            inputs += ["-f", "lavfi", "-i", f"color=c={color}:s=160x90:r=2:d={seconds}"]
        pads = "".join(f"[{i}:v]" for i in range(len(colors)))
        graph = f"{pads}concat=n={len(colors)}:v=1:a=0[v]"
        ffmpeg(*inputs, "-filter_complex", graph, "-map", "[v]", str(out))
        return out

    return make
