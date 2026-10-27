import itertools
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from yt_img.frames import Frame
from yt_img.selection import (
    FINGERPRINT_SIZE,
    chunks,
    difference,
    distinct,
    fingerprint,
    spread,
)

RGB = tuple[int, int, int]
FrameFactory = Callable[..., Frame]


@pytest.fixture
def frame_of(tmp_path: Path) -> FrameFactory:
    def make(time: float, color: RGB, size: tuple[int, int] = (160, 90)) -> Frame:
        path = tmp_path / f"{time:08.2f}.png"
        Image.new("RGB", size, color).save(path)
        return Frame(time, path)

    return make


def solid(color: RGB) -> Image.Image:
    return Image.new("RGB", FINGERPRINT_SIZE, color)


def test_fingerprint_is_small_rgb(frame_of: FrameFactory) -> None:
    img = fingerprint(frame_of(0, (1, 2, 3), (480, 270)).path)
    assert img.size == FINGERPRINT_SIZE
    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (1, 2, 3)


def test_fingerprint_of_grayscale_png(tmp_path: Path) -> None:
    path = tmp_path / "gray.png"
    Image.new("L", (100, 100), 128).save(path)
    assert fingerprint(path).getpixel((5, 5)) == (128, 128, 128)


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ((0, 0, 0), (0, 0, 0), 0.0),
        ((0, 0, 0), (255, 255, 255), 1.0),
        ((255, 0, 0), (0, 0, 0), 1 / 3),
        ((10, 10, 10), (61, 61, 61), 0.2),
    ],
)
def test_difference(a: RGB, b: RGB, expected: float) -> None:
    assert difference(solid(a), solid(b)) == pytest.approx(expected)
    assert difference(solid(b), solid(a)) == pytest.approx(expected)


def test_difference_sees_colour_changes_with_equal_brightness() -> None:
    # Pure red and a green of the same luma are identical in grayscale.
    assert difference(solid((255, 0, 0)), solid((0, 130, 0))) > 0.3


def test_distinct_keeps_scene_changes(frame_of: FrameFactory) -> None:
    frames = [
        frame_of(0, (255, 0, 0)),
        frame_of(10, (255, 0, 0)),
        frame_of(20, (0, 0, 255)),
        frame_of(30, (0, 0, 255)),
        frame_of(40, (255, 0, 0)),
    ]
    kept = distinct(frames, threshold=0.05)
    assert [f.time for f in kept] == [0, 20, 40]


def test_distinct_ignores_small_noise(frame_of: FrameFactory) -> None:
    frames = [frame_of(t, (100 + t // 10, 100, 100)) for t in range(0, 50, 10)]
    assert [f.time for f in distinct(frames, threshold=0.05)] == [0]


def test_distinct_compares_with_last_kept_frame(frame_of: FrameFactory) -> None:
    # Each step changes 10/255 per channel; only the drift adds up.
    frames = [frame_of(t, (t, t, t)) for t in range(0, 70, 10)]
    kept = distinct(frames, threshold=25 / 255)
    assert [f.time for f in kept] == [0, 30, 60]


def test_distinct_threshold_zero_keeps_everything(frame_of: FrameFactory) -> None:
    frames = [frame_of(t, (0, 0, 0)) for t in (0, 10, 20)]
    assert distinct(frames, threshold=0) == frames


def test_distinct_of_nothing() -> None:
    assert distinct([], threshold=0.05) == []


@pytest.mark.parametrize(
    ("n", "count", "expected"),
    [
        (0, 16, []),
        (5, 16, [0, 1, 2, 3, 4]),
        (16, 16, list(range(16))),
        (10, 1, [0]),
        (10, 2, [0, 9]),
        (5, 3, [0, 2, 4]),
        (17, 16, [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16]),
    ],
)
def test_spread(n: int, count: int, expected: list[int]) -> None:
    assert spread(list(range(n)), count) == expected


def test_spread_of_many_is_even_and_unique() -> None:
    picked = spread(list(range(721)), 16)
    assert len(picked) == len(set(picked)) == 16
    assert picked[0] == 0 and picked[-1] == 720
    gaps = {b - a for a, b in itertools.pairwise(picked)}
    assert gaps == {48}


@pytest.mark.parametrize(
    ("n", "size", "expected"),
    [
        (0, 16, []),
        (3, 16, [[0, 1, 2]]),
        (16, 16, [list(range(16))]),
        (17, 16, [list(range(16)), [16]]),
        (5, 2, [[0, 1], [2, 3], [4]]),
        (3, 1, [[0], [1], [2]]),
    ],
)
def test_chunks(n: int, size: int, expected: list[list[int]]) -> None:
    assert chunks(list(range(n)), size) == expected
