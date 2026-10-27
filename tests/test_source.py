import re
from pathlib import Path

import pytest

from yt_img.errors import YtImgError
from yt_img.source import Kind, Source, detect


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://youtube.com/watch?v=dQw4w9WgXcQ&t=42",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/abcdefghijk",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/abcdefghijk",
        "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        "HTTPS://WWW.YOUTUBE.COM/watch?v=dQw4w9WgXcQ",
    ],
)
def test_youtube_urls(url: str) -> None:
    assert detect(url) == Source(Kind.YOUTUBE, url)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("youtu.be/dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ"),
        (
            "www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
    ],
)
def test_youtube_without_scheme(raw: str, expected: str) -> None:
    assert detect(raw) == Source(Kind.YOUTUBE, expected)


def test_surrounding_whitespace_is_ignored() -> None:
    url = "https://youtu.be/dQw4w9WgXcQ"
    assert detect(f"  {url}\n") == Source(Kind.YOUTUBE, url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/video.mp4",
        "http://notyoutube.com/watch?v=x",
        "https://youtube.com.evil.example/watch?v=x",
    ],
)
def test_other_urls(url: str) -> None:
    assert detect(url) == Source(Kind.URL, url)


def test_local_file(tmp_path: Path) -> None:
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"")
    assert detect(str(video)) == Source(Kind.FILE, str(video))


def test_local_file_with_tilde(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "clip.webm").write_bytes(b"")
    assert detect("~/clip.webm") == Source(Kind.FILE, str(tmp_path / "clip.webm"))


def test_local_file_named_like_youtube_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "youtu.be").mkdir()
    (tmp_path / "youtu.be" / "x").write_bytes(b"")
    assert detect("youtu.be/x") == Source(Kind.FILE, "youtu.be/x")


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("", "no input given"),
        ("   ", "no input given"),
        ("ftp://example.com/a.mp4", "unsupported URL scheme: ftp"),
        ("/definitely/not/here.mp4", "no such file: /definitely/not/here.mp4"),
    ],
)
def test_rejected(raw: str, message: str) -> None:
    with pytest.raises(YtImgError, match=f"^{re.escape(message)}$"):
        detect(raw)


def test_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(YtImgError, match=r"^not a file: "):
        detect(str(tmp_path))
