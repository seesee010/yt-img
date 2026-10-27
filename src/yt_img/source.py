"""Classify the input as a YouTube URL, another URL or a local file."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlsplit

from yt_img.errors import YtImgError

YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
        "youtu.be",
    }
)


class Kind(Enum):
    YOUTUBE = "youtube"
    URL = "url"
    FILE = "file"


@dataclass(frozen=True)
class Source:
    kind: Kind
    location: str


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def detect(raw: str) -> Source:
    """Return what *raw* points to; raise YtImgError if it is unusable."""
    text = raw.strip()
    if not text:
        raise YtImgError("no input given")

    scheme = urlsplit(text).scheme.lower()
    if scheme in ("http", "https"):
        kind = Kind.YOUTUBE if _host(text) in YOUTUBE_HOSTS else Kind.URL
        return Source(kind, text)
    if "://" in text:
        raise YtImgError(f"unsupported URL scheme: {scheme}")

    path = Path(text).expanduser()
    if path.is_file():
        return Source(Kind.FILE, str(path))
    if path.exists():
        raise YtImgError(f"not a file: {text}")

    # "youtu.be/ID" or "www.youtube.com/watch?v=ID" typed without a scheme.
    with_scheme = "https://" + text
    if _host(with_scheme) in YOUTUBE_HOSTS:
        return Source(Kind.YOUTUBE, with_scheme)
    raise YtImgError(f"no such file: {text}")
