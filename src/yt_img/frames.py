"""Sample one frame every N seconds from a video with ffmpeg."""

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from yt_img.errors import YtImgError

_PTS_TIME = re.compile(r"\bpts_time:(-?[0-9.]+)")


@dataclass(frozen=True)
class Frame:
    time: float
    path: Path


def _reason(stderr: str) -> str:
    if "matches no streams" in stderr:
        return "it has no video stream"
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "unknown ffmpeg error"


def sample(src: str, out_dir: Path, interval: float, width: int) -> list[Frame]:
    """Write frames of *src* as PNGs into the empty *out_dir* and return them.

    The first frame is always taken, then every frame that lies at least
    *interval* seconds after the previously taken one. Frames are scaled
    to *width* pixels, keeping the aspect ratio.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise YtImgError("ffmpeg not found, install it and make sure it is on PATH")

    select = f"isnan(prev_selected_t)+gte(t-prev_selected_t,{interval})"
    cmd = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-i",
        src,
        "-map",
        "0:v:0",
        "-vf",
        f"select='{select}',scale={width}:-2,showinfo",
        "-fps_mode",
        "vfr",
        str(out_dir / "%06d.png"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise YtImgError(f"cannot read {src}: {_reason(proc.stderr)}")

    paths = sorted(out_dir.glob("*.png"))
    if not paths:
        raise YtImgError(f"no frames could be read from {src}")
    times = [float(t) for t in _PTS_TIME.findall(proc.stderr)]
    if len(times) != len(paths):
        raise YtImgError(
            f"ffmpeg wrote {len(paths)} frames but reported {len(times)} timestamps"
        )
    return [Frame(t, p) for t, p in zip(times, paths, strict=True)]
