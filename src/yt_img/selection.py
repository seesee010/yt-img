"""Keep only frames that differ enough, then spread the rest over the grid."""

from collections.abc import Sequence
from pathlib import Path
from typing import TypeVar

from PIL import Image, ImageChops, ImageStat

from yt_img.frames import Frame

T = TypeVar("T")

# Small enough to ignore noise and compression artefacts, large enough
# to notice a slide change.
FINGERPRINT_SIZE = (64, 36)


def fingerprint(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGB").resize(FINGERPRINT_SIZE, Image.Resampling.BOX)


def difference(a: Image.Image, b: Image.Image) -> float:
    """Mean absolute difference over all pixels and channels, from 0 to 1."""
    means = ImageStat.Stat(ImageChops.difference(a, b)).mean
    return sum(means) / len(means) / 255


def distinct(frames: Sequence[Frame], threshold: float) -> list[Frame]:
    """Drop every frame that is closer than *threshold* to the last kept one.

    Comparing against the last kept frame rather than the direct
    predecessor lets a slow pan or fade add up until it counts as new.
    """
    kept: list[Frame] = []
    last: Image.Image | None = None
    for frame in frames:
        current = fingerprint(frame.path)
        if last is None or difference(current, last) >= threshold:
            kept.append(frame)
            last = current
    return kept


def spread(items: Sequence[T], count: int) -> list[T]:
    """Pick *count* items evenly, always including the first and last one."""
    n = len(items)
    if n <= count:
        return list(items)
    if count == 1:
        return [items[0]]
    return [items[round(i * (n - 1) / (count - 1))] for i in range(count)]


def chunks(items: Sequence[T], size: int) -> list[list[T]]:
    """Split *items* in order into lists of *size*, the last one may be shorter."""
    return [list(items[i : i + size]) for i in range(0, len(items), size)]
