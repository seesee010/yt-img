"""yt-img SOURCE: turn a video into one contact sheet of distinct frames."""

import argparse
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlsplit

from yt_img import __version__
from yt_img.download import download
from yt_img.errors import YtImgError
from yt_img.frames import sample
from yt_img.selection import distinct, spread
from yt_img.source import Kind, detect
from yt_img.tile import image_format, render, save


def _number(
    convert: Callable[[str], float], low: float, high: float | None = None
) -> Callable[[str], float]:
    def parse(text: str) -> float:
        try:
            value = convert(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
        if value < low or (high is not None and value > high):
            limit = f"between {low} and {high}" if high is not None else f">= {low}"
            raise argparse.ArgumentTypeError(f"must be {limit}, got {text}")
        return value

    return parse


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="yt-img",
        description=(
            "Sample a video every few seconds, keep the frames that differ "
            "enough from the previous one and tile them into one image."
        ),
    )
    p.add_argument(
        "source",
        help="YouTube URL, direct video URL or local video file (any ffmpeg format)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output image, .png/.jpg/.jpeg/.webp (default: <video name>.png)",
    )
    p.add_argument(
        "-i",
        "--interval",
        type=_number(float, 0.1),
        default=10.0,
        help="seconds between sampled frames (default: %(default)s)",
    )
    p.add_argument(
        "-t",
        "--threshold",
        type=_number(float, 0.0, 1.0),
        default=0.05,
        help="minimum difference to the last kept frame, 0-1 (default: %(default)s)",
    )
    p.add_argument(
        "-n",
        "--count",
        type=_number(int, 1),
        default=16,
        help="maximum number of frames on the sheet (default: %(default)s)",
    )
    p.add_argument(
        "-c",
        "--columns",
        type=_number(int, 1),
        default=4,
        help="frames per row (default: %(default)s)",
    )
    p.add_argument(
        "-w",
        "--width",
        type=_number(int, 16),
        default=480,
        help="width of each frame in pixels (default: %(default)s)",
    )
    p.add_argument(
        "--no-labels",
        dest="labels",
        action="store_false",
        help="do not print timestamps on the frames",
    )
    p.add_argument(
        "-q", "--quiet", action="store_true", help="only print the output path"
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def run(args: argparse.Namespace) -> Path:
    def say(message: str) -> None:
        if not args.quiet:
            print(message, file=sys.stderr)

    if args.output is not None:
        image_format(args.output)  # fail before any slow work
    source = detect(args.source)

    with tempfile.TemporaryDirectory(prefix="yt-img-") as tmp:
        work = Path(tmp)
        if source.kind is Kind.YOUTUBE:
            say(f"downloading {source.location}")
            video = download(source.location, work)
            location, name = str(video), video.stem
        elif source.kind is Kind.URL:
            location = source.location
            name = Path(urlsplit(location).path).stem or "video"
        else:
            location, name = source.location, Path(source.location).stem

        say(f"sampling one frame every {args.interval:g} s")
        frames_dir = work / "frames"
        frames_dir.mkdir()
        sampled = sample(location, frames_dir, args.interval, args.width)
        kept = distinct(sampled, args.threshold)
        chosen = spread(kept, args.count)
        output: Path = args.output or Path(f"{name}.png")
        save(render(chosen, args.columns, args.labels), output)

    say(f"{len(sampled)} sampled, {len(kept)} distinct, {len(chosen)} on the sheet")
    return output


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        output = run(args)
    except YtImgError as err:
        print(f"yt-img: error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("yt-img: interrupted", file=sys.stderr)
        return 130
    print(output)
    return 0
