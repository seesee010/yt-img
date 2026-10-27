import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest
import yt_dlp

from yt_img import download as dl
from yt_img.errors import YtImgError

URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo", 19 s


class FakeYoutubeDL:
    """Stands in for yt_dlp.YoutubeDL; records what the code asked for."""

    instances: ClassVar[list["FakeYoutubeDL"]] = []
    info: ClassVar[dict[str, Any]] = {}
    error: ClassVar[Exception | None] = None
    create_file: ClassVar[bool] = True

    def __init__(self, params: dict[str, Any]) -> None:
        self.params = params
        self.calls: list[str] = []
        FakeYoutubeDL.instances.append(self)

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def extract_info(self, url: str, download: bool) -> dict[str, Any]:
        self.calls.append(f"extract {url} download={download}")
        # Like yt_dlp.utils.write_string, which ignores the logger.
        sys.stderr.write("WARNING: Unknown codec iamf.001.001.Opus\n")
        if self.error is not None:
            raise self.error
        return dict(self.info)

    def process_ie_result(self, info: dict[str, Any], download: bool) -> Any:
        self.calls.append(f"process download={download}")
        path = Path(self.params["outtmpl"] % {"id": info["id"], "ext": "webm"})
        if self.create_file:
            path.write_bytes(b"video")
        return {**info, "requested_downloads": [{"filepath": str(path)}]}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> type[FakeYoutubeDL]:
    monkeypatch.setattr(FakeYoutubeDL, "instances", [])
    monkeypatch.setattr(FakeYoutubeDL, "info", {"id": "x", "title": "t"})
    monkeypatch.setattr(FakeYoutubeDL, "error", None)
    monkeypatch.setattr(FakeYoutubeDL, "create_file", True)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    return FakeYoutubeDL


def test_downloads_single_video(fake: type[FakeYoutubeDL], tmp_path: Path) -> None:
    path = dl.download(URL, tmp_path)
    assert path == tmp_path / "x.webm"
    assert path.read_bytes() == b"video"
    (ydl,) = fake.instances
    assert ydl.calls == [f"extract {URL} download=False", "process download=True"]


def test_yt_dlp_output_stays_off_the_terminal(
    fake: type[FakeYoutubeDL], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dl.download(URL, tmp_path)
    assert capsys.readouterr() == ("", "")


def test_options(tmp_path: Path) -> None:
    opts = dl.options(tmp_path)
    assert opts["format"] == dl.FORMAT
    assert opts["outtmpl"] == str(tmp_path / "%(id)s.%(ext)s")
    assert opts["noplaylist"] is True
    assert opts["noprogress"] is True
    logger = opts["logger"]
    for level in ("debug", "warning", "error"):
        assert getattr(logger, level)("message") is None


def test_format_is_video_only_and_capped() -> None:
    first_choice = dl.FORMAT.split("/")[0]
    assert first_choice == "bv*[height<=720]"
    assert dl.FORMAT.endswith("/b")  # never fails for lack of a format


@pytest.mark.parametrize("kind", ["playlist", "multi_video"])
def test_playlist_rejected_before_download(
    fake: type[FakeYoutubeDL], tmp_path: Path, kind: str
) -> None:
    fake.info = {"_type": kind, "entries": []}
    with pytest.raises(YtImgError, match="playlists are not supported"):
        dl.download(URL, tmp_path)
    assert all("process" not in c for c in fake.instances[0].calls)


def test_live_stream_rejected_before_download(
    fake: type[FakeYoutubeDL], tmp_path: Path
) -> None:
    fake.info = {"id": "x", "is_live": True}
    with pytest.raises(YtImgError, match="live streams are not supported"):
        dl.download(URL, tmp_path)
    assert all("process" not in c for c in fake.instances[0].calls)


def test_download_error(fake: type[FakeYoutubeDL], tmp_path: Path) -> None:
    fake.error = yt_dlp.utils.DownloadError("ERROR: [youtube] x: Video unavailable")
    with pytest.raises(
        YtImgError, match=r"^download failed: \[youtube\] x: Video unavailable$"
    ):
        dl.download(URL, tmp_path)


def test_missing_file_after_download(fake: type[FakeYoutubeDL], tmp_path: Path) -> None:
    fake.create_file = False
    with pytest.raises(YtImgError, match="yt-dlp did not create"):
        dl.download(URL, tmp_path)


@pytest.mark.network
def test_real_youtube_download(tmp_path: Path) -> None:
    path = dl.download(URL, tmp_path)
    assert path.is_file()
    assert path.stat().st_size > 10_000
