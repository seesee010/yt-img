"""Render frames into one contact sheet and save it."""

import math
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from yt_img.errors import YtImgError
from yt_img.frames import Frame

FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
GAP = 4
BACKGROUND = (0, 0, 0)
LABEL_FG = (255, 255, 255)


def timestamp(seconds: float) -> str:
    """Format whole seconds as m:ss, or h:mm:ss from one hour on."""
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02}:{secs:02}"
    return f"{minutes}:{secs:02}"


def image_format(path: Path) -> str:
    """Return the Pillow format for *path*'s extension or raise YtImgError."""
    try:
        return FORMATS[path.suffix.lower()]
    except KeyError:
        known = ", ".join(FORMATS)
        raise YtImgError(
            f"unsupported output format '{path.suffix}', use one of: {known}"
        ) from None


def _label(img: Image.Image, text: str) -> None:
    size = max(12, img.width // 20)
    font = ImageFont.load_default(size=size)
    draw = ImageDraw.Draw(img)
    pad = max(2, size // 4)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x, y = pad, img.height - (bottom - top) - 2 * pad
    draw.rectangle(
        (x - pad, y - pad, x + right - left + pad, y + bottom - top + pad),
        fill=BACKGROUND,
    )
    draw.text((x - left, y - top), text, font=font, fill=LABEL_FG)


def render(frames: Sequence[Frame], columns: int, labels: bool) -> Image.Image:
    """Lay *frames* out left to right, top to bottom, *columns* per row."""
    if not frames:
        raise ValueError("no frames to render")
    images: list[Image.Image] = []
    for frame in frames:
        with Image.open(frame.path) as src:
            images.append(src.convert("RGB"))
    cell_w = max(img.width for img in images)
    cell_h = max(img.height for img in images)
    cols = min(columns, len(images))
    rows = math.ceil(len(images) / cols)
    sheet = Image.new(
        "RGB",
        (cols * cell_w + (cols + 1) * GAP, rows * cell_h + (rows + 1) * GAP),
        BACKGROUND,
    )
    for i, (frame, img) in enumerate(zip(frames, images, strict=True)):
        if labels:
            _label(img, timestamp(frame.time))
        row, col = divmod(i, cols)
        sheet.paste(img, (GAP + col * (cell_w + GAP), GAP + row * (cell_h + GAP)))
    return sheet


def save(sheet: Image.Image, path: Path) -> None:
    fmt = image_format(path)
    try:
        sheet.save(path, fmt, quality=90)
    except OSError as err:
        raise YtImgError(f"cannot write {path}: {err.strerror or err}") from err
