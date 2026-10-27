"""Fetch a YouTube video with yt-dlp."""

from pathlib import Path
from typing import Any

import yt_dlp

from yt_img.errors import YtImgError

# Frames need no audio, and 720p is plenty for a tile a few hundred
# pixels wide; fall back to whatever exists if that is not offered.
FORMAT = "bv*[height<=720]/b[height<=720]/bv*/b"


class _Silent:
    """yt-dlp logger that keeps its output off the terminal.

    Errors still reach the user, as the DownloadError message.
    """

    def debug(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass


def options(out_dir: Path) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "outtmpl": str(out_dir / "video.%(ext)s"),
        "noplaylist": True,
        "logger": _Silent(),
        "noprogress": True,
    }


def download(url: str, out_dir: Path) -> Path:
    """Download the video behind *url* into *out_dir* and return its path."""
    try:
        with yt_dlp.YoutubeDL(options(out_dir)) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("_type") in ("playlist", "multi_video"):
                raise YtImgError("playlists are not supported, pass a single video")
            if info.get("is_live"):
                raise YtImgError("live streams are not supported")
            info = ydl.process_ie_result(info, download=True)
    except yt_dlp.utils.DownloadError as err:
        reason = str(err).removeprefix("ERROR: ")
        raise YtImgError(f"download failed: {reason}") from err

    path = Path(str(info["requested_downloads"][0]["filepath"]))
    if not path.is_file():
        raise YtImgError(f"download failed: yt-dlp did not create {path}")
    return path
