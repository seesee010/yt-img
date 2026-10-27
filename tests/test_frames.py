import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import VideoFactory, ffmpeg
from PIL import Image

from yt_img.errors import YtImgError
from yt_img.frames import sample

FORMATS = [".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts", ".gif",
           ".m4v", ".ogv"]  # fmt: skip


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    path = tmp_path / "frames"
    path.mkdir()
    return path


def test_one_frame_per_interval(make_video: VideoFactory, out_dir: Path) -> None:
    video = make_video(["red", "lime", "blue"], seconds=10)
    got = sample(str(video), out_dir, interval=10, width=64)
    assert [f.time for f in got] == [0, 10, 20]
    assert [f.path.name for f in got] == ["000001.png", "000002.png", "000003.png"]


def test_frames_follow_the_video(make_video: VideoFactory, out_dir: Path) -> None:
    video = make_video(["red", "blue"], seconds=10)
    got = sample(str(video), out_dir, interval=10, width=64)
    with Image.open(got[0].path) as first, Image.open(got[1].path) as second:
        r, _, b = first.convert("RGB").getpixel((32, 18))  # type: ignore[misc]
        assert r > 200 and b < 50
        r, _, b = second.convert("RGB").getpixel((32, 18))  # type: ignore[misc]
        assert r < 50 and b > 200


def test_custom_interval(make_video: VideoFactory, out_dir: Path) -> None:
    video = make_video(seconds=12)
    got = sample(str(video), out_dir, interval=2.5, width=64)
    assert [f.time for f in got] == [0, 2.5, 5, 7.5, 10]


def test_frames_are_scaled(make_video: VideoFactory, out_dir: Path) -> None:
    video = make_video(seconds=1)
    (frame,) = sample(str(video), out_dir, interval=10, width=320)
    with Image.open(frame.path) as img:
        assert img.size == (320, 180)


def test_video_shorter_than_interval(make_video: VideoFactory, out_dir: Path) -> None:
    video = make_video(seconds=0.5)
    assert [f.time for f in sample(str(video), out_dir, 10, 64)] == [0]


@pytest.mark.parametrize("suffix", FORMATS)
def test_container_formats(
    make_video: VideoFactory, out_dir: Path, suffix: str
) -> None:
    video = make_video(["red", "blue"], seconds=10, suffix=suffix)
    assert len(sample(str(video), out_dir, interval=10, width=64)) == 2


def test_audio_only_file(tmp_path: Path, out_dir: Path) -> None:
    audio = tmp_path / "tone.mp3"
    ffmpeg("-f", "lavfi", "-i", "sine=d=1", str(audio))
    with pytest.raises(YtImgError, match="has no video stream"):
        sample(str(audio), out_dir, 10, 64)


def test_not_a_video(tmp_path: Path, out_dir: Path) -> None:
    junk = tmp_path / "notes.mp4"
    junk.write_text("hello")
    with pytest.raises(YtImgError, match=r"^cannot read .*notes\.mp4: "):
        sample(str(junk), out_dir, 10, 64)


def test_ffmpeg_missing(monkeypatch: pytest.MonkeyPatch, out_dir: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(YtImgError, match="ffmpeg not found"):
        sample("x.mp4", out_dir, 10, 64)


def fake_ffmpeg(
    monkeypatch: pytest.MonkeyPatch, code: int, stderr: str, files: int = 0
) -> None:
    def run(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        pattern = cmd[-1]
        for i in range(1, files + 1):
            Path(pattern % i).write_bytes(b"")
        return subprocess.CompletedProcess(cmd, code, "", stderr)

    monkeypatch.setattr(subprocess, "run", run)


def test_error_without_message(monkeypatch: pytest.MonkeyPatch, out_dir: Path) -> None:
    fake_ffmpeg(monkeypatch, 1, "\n  \n")
    with pytest.raises(YtImgError, match=r"^cannot read x\.mp4: unknown ffmpeg error$"):
        sample("x.mp4", out_dir, 10, 64)


def test_no_frames_written(monkeypatch: pytest.MonkeyPatch, out_dir: Path) -> None:
    fake_ffmpeg(monkeypatch, 0, "")
    with pytest.raises(YtImgError, match=r"^no frames could be read from x\.mp4$"):
        sample("x.mp4", out_dir, 10, 64)


def test_timestamps_missing(monkeypatch: pytest.MonkeyPatch, out_dir: Path) -> None:
    fake_ffmpeg(monkeypatch, 0, "n:0 pts_time:0\n", files=2)
    with pytest.raises(YtImgError, match="wrote 2 frames but reported 1 timestamps"):
        sample("x.mp4", out_dir, 10, 64)


def test_command_line(monkeypatch: pytest.MonkeyPatch, out_dir: Path) -> None:
    seen: list[list[str]] = []

    def run(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        Path(cmd[-1] % 1).write_bytes(b"")
        return subprocess.CompletedProcess(cmd, 0, "", "pts_time:0")

    monkeypatch.setattr(subprocess, "run", run)
    sample("https://example.com/a.mp4", out_dir, 10, 480)
    (cmd,) = seen
    assert cmd[cmd.index("-i") + 1] == "https://example.com/a.mp4"
    assert cmd[cmd.index("-map") + 1] == "0:v:0"
    assert "scale=480:-2" in cmd[cmd.index("-vf") + 1]
