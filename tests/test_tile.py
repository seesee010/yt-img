from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from yt_img.errors import YtImgError
from yt_img.frames import Frame
from yt_img.tile import GAP, image_format, render, save, timestamp

RGB = tuple[int, int, int]
FrameFactory = Callable[..., Frame]
W, H = 64, 36


@pytest.fixture
def frame_of(tmp_path: Path) -> FrameFactory:
    def make(time: float, color: RGB = (200, 30, 30)) -> Frame:
        path = tmp_path / f"{time:010.3f}.png"
        Image.new("RGB", (W, H), color).save(path)
        return Frame(time, path)

    return make


def cell_origin(index: int, cols: int) -> tuple[int, int]:
    row, col = divmod(index, cols)
    return GAP + col * (W + GAP), GAP + row * (H + GAP)


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0, "0:00"),
        (9.99, "0:09"),
        (65, "1:05"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (36061, "10:01:01"),
    ],
)
def test_timestamp(seconds: float, text: str) -> None:
    assert timestamp(seconds) == text


@pytest.mark.parametrize(
    ("n", "columns", "grid"),
    [(16, 4, (4, 4)), (5, 4, (4, 2)), (2, 4, (2, 1)), (1, 4, (1, 1)), (9, 3, (3, 3))],
)
def test_grid_size(
    frame_of: FrameFactory, n: int, columns: int, grid: tuple[int, int]
) -> None:
    sheet = render([frame_of(t) for t in range(n)], columns, labels=False)
    cols, rows = grid
    assert sheet.size == (cols * W + (cols + 1) * GAP, rows * H + (rows + 1) * GAP)


def test_frames_are_placed_in_reading_order(frame_of: FrameFactory) -> None:
    colors: list[RGB] = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                         (0, 255, 255)]  # fmt: skip
    frames = [frame_of(i, c) for i, c in enumerate(colors)]
    sheet = render(frames, columns=2, labels=False)
    for i, color in enumerate(colors):
        x, y = cell_origin(i, 2)
        assert sheet.getpixel((x + W // 2, y + H // 2)) == color
    # The unused sixth cell and the gaps stay background.
    x, y = cell_origin(5, 2)
    assert sheet.getpixel((x + W // 2, y + H // 2)) == (0, 0, 0)
    assert sheet.getpixel((0, 0)) == (0, 0, 0)


def test_labels_are_drawn_bottom_left(frame_of: FrameFactory) -> None:
    frames = [frame_of(75)]
    plain = render(frames, 4, labels=False)
    labelled = render(frames, 4, labels=True)
    assert plain.size == labelled.size
    x, y = cell_origin(0, 1)
    bottom_left = (x, y + H // 2, x + W // 2, y + H)
    top_right = (x + W // 2, y, x + W, y + H // 2)
    assert plain.crop(bottom_left).tobytes() != labelled.crop(bottom_left).tobytes()
    assert plain.crop(top_right).tobytes() == labelled.crop(top_right).tobytes()
    colors = {
        c
        for _, c in labelled.crop(bottom_left).getcolors(4096) or []
        if isinstance(c, tuple)
    }
    assert any(min(c) > 230 for c in colors)  # antialiased white text
    assert (0, 0, 0) in colors  # on a black box


def test_render_without_frames() -> None:
    with pytest.raises(ValueError, match="no frames"):
        render([], 4, labels=True)


def test_render_converts_other_modes(tmp_path: Path) -> None:
    path = tmp_path / "gray.png"
    Image.new("L", (W, H), 100).save(path)
    sheet = render([Frame(0, path)], 4, labels=False)
    assert sheet.mode == "RGB"
    assert sheet.getpixel((GAP + 1, GAP + 1)) == (100, 100, 100)


@pytest.mark.parametrize(
    ("name", "fmt"),
    [
        ("a.png", "PNG"),
        ("a.jpg", "JPEG"),
        ("a.jpeg", "JPEG"),
        ("a.JPG", "JPEG"),
        ("a.webp", "WEBP"),
    ],
)
def test_save_formats(
    frame_of: FrameFactory, tmp_path: Path, name: str, fmt: str
) -> None:
    sheet = render([frame_of(0), frame_of(10)], 4, labels=True)
    out = tmp_path / name
    save(sheet, out)
    with Image.open(out) as img:
        assert img.format == fmt
        assert img.size == sheet.size


@pytest.mark.parametrize("name", ["a.gif", "a.txt", "noext"])
def test_unsupported_format(name: str) -> None:
    with pytest.raises(YtImgError, match="unsupported output format"):
        image_format(Path(name))


def test_save_into_missing_directory(frame_of: FrameFactory, tmp_path: Path) -> None:
    sheet = render([frame_of(0)], 4, labels=False)
    with pytest.raises(YtImgError, match=r"^cannot write .*sheet\.png: "):
        save(sheet, tmp_path / "missing" / "sheet.png")
