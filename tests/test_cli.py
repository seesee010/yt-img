import functools
import http.server
import runpy
import shutil
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import VideoFactory
from PIL import Image

import yt_img
from yt_img import cli
from yt_img.tile import GAP

RED, LIME, BLUE = (255, 0, 0), (0, 255, 0), (0, 0, 255)
YT_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = cli.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def grid(sheet: Image.Image, width: int, height: int) -> tuple[int, int]:
    return (sheet.width - GAP) // (width + GAP), (sheet.height - GAP) // (height + GAP)


def cell_color(
    sheet: Image.Image, index: int, cols: int, w: int, h: int
) -> tuple[int, ...]:
    row, col = divmod(index, cols)
    x = GAP + col * (w + GAP) + w * 3 // 4  # right half: away from the label
    y = GAP + row * (h + GAP) + h // 4
    pixel = sheet.getpixel((x, y))
    assert isinstance(pixel, tuple)
    return pixel


def close(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    return all(abs(x - y) <= 40 for x, y in zip(a, b, strict=True))


# -- end to end on real videos ------------------------------------------------


def test_scene_changes_end_up_on_the_sheet(
    make_video: VideoFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    video = make_video(["red", "red", "lime", "lime", "blue", "red"], seconds=10)
    out = tmp_path / "sheet.png"
    code, stdout, stderr = run([str(video), "-o", str(out), "-w", "160"], capsys)
    assert code == 0
    assert stdout == f"{out}\n"
    assert "6 sampled, 4 distinct, 4 on the sheet" in stderr
    with Image.open(out) as sheet:
        assert grid(sheet, 160, 90) == (4, 1)
        colors = [cell_color(sheet, i, 4, 160, 90) for i in range(4)]
    for got, want in zip(colors, [RED, LIME, BLUE, RED], strict=True):
        assert close(got, want), (got, want)


def test_long_video_is_capped_at_sixteen_frames(
    make_video: VideoFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    video = make_video(["red", "lime", "blue", "yellow"] * 6, seconds=10)
    out = tmp_path / "sheet.png"
    code, _, stderr = run([str(video), "-o", str(out), "-w", "64"], capsys)
    assert code == 0
    assert "24 sampled, 24 distinct, 16 on the sheet" in stderr
    with Image.open(out) as sheet:
        assert grid(sheet, 64, 36) == (4, 4)


def test_still_video_gives_one_frame(
    make_video: VideoFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    video = make_video(["gray"], seconds=40)
    out = tmp_path / "sheet.png"
    code, _, stderr = run([str(video), "-o", str(out), "-w", "64"], capsys)
    assert code == 0
    assert "4 sampled, 1 distinct, 1 on the sheet" in stderr


def test_options_change_the_result(
    make_video: VideoFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    video = make_video(["red", "lime", "blue", "yellow", "white", "black"], 5)
    out = tmp_path / "sheet.png"
    argv = [str(video), "-o", str(out), "-w", "64", "-i", "5", "-n", "4", "-c", "2"]
    code, _, stderr = run([*argv, "-t", "1"], capsys)
    assert "6 sampled, 1 distinct, 1 on the sheet" in stderr
    code, _, stderr = run(argv, capsys)
    assert code == 0
    assert "6 sampled, 6 distinct, 4 on the sheet" in stderr
    with Image.open(out) as sheet:
        assert grid(sheet, 64, 36) == (2, 2)


@pytest.mark.parametrize("suffix", [".mp4", ".mkv", ".webm", ".mov", ".avi", ".gif"])
@pytest.mark.parametrize("output", ["sheet.png", "sheet.jpg", "sheet.webp"])
def test_formats(
    make_video: VideoFactory,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    suffix: str,
    output: str,
) -> None:
    video = make_video(["red", "blue"], seconds=10, suffix=suffix)
    out = tmp_path / output
    code, _, _ = run([str(video), "-o", str(out), "-w", "64", "-q"], capsys)
    assert code == 0
    with Image.open(out) as sheet:
        assert grid(sheet, 64, 36) == (2, 1)


def test_default_output_name(
    make_video: VideoFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    video = make_video(suffix=".mkv")
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    code, stdout, _ = run([str(video), "-w", "64"], capsys)
    assert code == 0
    assert stdout == f"{video.stem}.png\n"
    assert (workdir / f"{video.stem}.png").is_file()


def test_labels_can_be_turned_off(
    make_video: VideoFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    video = make_video(seconds=1)
    with_labels, without = tmp_path / "a.png", tmp_path / "b.png"
    run([str(video), "-o", str(with_labels), "-w", "64"], capsys)
    run([str(video), "-o", str(without), "-w", "64", "--no-labels"], capsys)
    with Image.open(with_labels) as a, Image.open(without) as b:
        assert a.size == b.size
        assert a.tobytes() != b.tobytes()
        assert len(b.getcolors(4096) or []) <= 3  # solid frame on black


def test_quiet(
    make_video: VideoFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "sheet.png"
    code, stdout, stderr = run(
        [str(make_video(seconds=1)), "-o", str(out), "-q"], capsys
    )
    assert (code, stdout, stderr) == (0, f"{out}\n", "")


@pytest.fixture
def http_dir(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    root = tmp_path / "www"
    root.mkdir()

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

    handler = functools.partial(Quiet, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_direct_url(
    make_video: VideoFactory,
    http_dir: tuple[Path, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, base = http_dir
    shutil.copy(make_video(["red", "blue"], seconds=10), root / "talk.mp4")
    monkeypatch.chdir(tmp_path)
    code, stdout, stderr = run([f"{base}/talk.mp4?token=1", "-w", "64"], capsys)
    assert code == 0, stderr
    assert stdout == "talk.png\n"
    assert "2 sampled, 2 distinct" in stderr


def test_url_without_file_name(
    make_video: VideoFactory,
    http_dir: tuple[Path, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, base = http_dir
    # The server answers "/" with index.html; ffmpeg probes the content.
    shutil.copy(make_video(seconds=1), root / "index.html")
    monkeypatch.chdir(tmp_path)
    code, stdout, stderr = run([f"{base}/", "-w", "64"], capsys)
    assert code == 0, stderr
    assert stdout == "video.png\n"


def test_youtube_goes_through_download(
    make_video: VideoFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_download(url: str, out_dir: Path) -> Path:
        assert url == YT_URL
        target = out_dir / "jNQXAC9IVRw.webm"
        shutil.copy(make_video(["red", "blue"], 10, ".webm"), target)
        return target

    monkeypatch.setattr(cli, "download", fake_download)
    monkeypatch.chdir(tmp_path)
    code, stdout, stderr = run([YT_URL, "-w", "64"], capsys)
    assert code == 0
    assert stdout == "jNQXAC9IVRw.png\n"
    assert f"downloading {YT_URL}" in stderr
    assert (tmp_path / "jNQXAC9IVRw.png").is_file()


@pytest.mark.network
def test_real_youtube_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    code, stdout, stderr = run([YT_URL], capsys)
    assert code == 0, stderr
    assert stdout == "jNQXAC9IVRw.png\n"
    with Image.open(tmp_path / "jNQXAC9IVRw.png") as sheet:
        assert sheet.width > 480


# -- --pages -----------------------------------------------------------------


def test_pages_keep_every_distinct_frame(
    make_video: VideoFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    colors = ["red", "lime", "blue", "yellow"] * 6
    video = make_video(colors, seconds=10)
    out = tmp_path / "sheet.png"
    code, stdout, stderr = run(
        [str(video), "-o", str(out), "-w", "64", "--pages"], capsys
    )
    assert code == 0
    assert "24 sampled, 24 distinct, 2 sheets" in stderr
    first, second = tmp_path / "sheet-1.png", tmp_path / "sheet-2.png"
    assert stdout == f"{first}\n{second}\n"
    assert not out.exists()
    want = {"red": RED, "lime": LIME, "blue": BLUE, "yellow": (255, 255, 0)}
    with Image.open(first) as a, Image.open(second) as b:
        assert grid(a, 64, 36) == (4, 4)
        assert grid(b, 64, 36) == (4, 2)
        got = [cell_color(a, i, 4, 64, 36) for i in range(16)]
        got += [cell_color(b, i, 4, 64, 36) for i in range(8)]
    # In order, nothing skipped: frame k shows colour k.
    for k, (pixel, name) in enumerate(zip(got, colors, strict=True)):
        assert close(pixel, want[name]), (k, pixel, name)


def test_pages_with_a_single_sheet(
    make_video: VideoFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    video = make_video(["red", "blue"], seconds=10)
    out = tmp_path / "sheet.webp"
    code, stdout, stderr = run([str(video), "-o", str(out), "-p", "-w", "64"], capsys)
    assert code == 0
    assert "2 sampled, 2 distinct, 1 sheet\n" in stderr
    assert stdout == f"{tmp_path / 'sheet-1.webp'}\n"


def test_pages_are_zero_padded(
    make_video: VideoFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    video = make_video(["red", "lime", "blue", "yellow", "white"] * 2, seconds=10)
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run([str(video), "--pages", "-n", "1", "-w", "64"], capsys)
    assert code == 0
    names = stdout.split()
    assert names == [f"{video.stem}-{i:02}.png" for i in range(1, 11)]
    assert names == sorted(names)
    assert all((tmp_path / n).is_file() for n in names)


@pytest.mark.parametrize(
    ("name", "page", "total", "expected"),
    [
        ("a.png", 1, 1, "a-1.png"),
        ("a.png", 3, 9, "a-3.png"),
        ("a.png", 3, 10, "a-03.png"),
        ("a.png", 42, 100, "a-042.png"),
        ("dir/b.c.jpg", 2, 2, "dir/b.c-2.jpg"),
    ],
)
def test_numbered(name: str, page: int, total: int, expected: str) -> None:
    assert cli.numbered(Path(name), page, total) == Path(expected)


# -- errors and argument checking ---------------------------------------------


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["/no/such/video.mp4"], "yt-img: error: no such file: /no/such/video.mp4"),
        (["ftp://x/y.mp4"], "yt-img: error: unsupported URL scheme: ftp"),
        (["x.mp4", "-o", "out.gif"], "yt-img: error: unsupported output format"),
    ],
)
def test_runtime_errors(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, stdout, stderr = run(argv, capsys)
    assert code == 1
    assert stdout == ""
    assert stderr.startswith(message)


def test_bad_output_format_fails_before_reading_the_video(
    make_video: VideoFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "detect", lambda _: pytest.fail("detect was called"))
    code, _, stderr = run(["whatever", "-o", "x.bmp"], capsys)
    assert code == 1
    assert "unsupported output format '.bmp'" in stderr


def test_not_a_video(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junk = tmp_path / "junk.mp4"
    junk.write_text("nope")
    code, _, stderr = run([str(junk), "-q"], capsys)
    assert code == 1
    assert stderr.startswith("yt-img: error: cannot read ")


def test_interrupt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupted(_: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "detect", interrupted)
    code, _, stderr = run(["x.mp4"], capsys)
    assert (code, stderr) == (130, "yt-img: interrupted\n")


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["x", "-i", "0"], "must be >= 0.1, got 0"),
        (["x", "-i", "abc"], "not a number: 'abc'"),
        (["x", "-t", "1.5"], "must be between 0.0 and 1.0, got 1.5"),
        (["x", "-t", "-0.1"], "must be between 0.0 and 1.0, got -0.1"),
        (["x", "-n", "0"], "must be >= 1, got 0"),
        (["x", "-n", "2.5"], "not a number: '2.5'"),
        (["x", "-c", "0"], "must be >= 1, got 0"),
        (["x", "-w", "8"], "must be >= 16, got 8"),
        ([], "the following arguments are required: source"),
    ],
)
def test_usage_errors(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2
    assert message in capsys.readouterr().err


def test_defaults() -> None:
    args = cli.parser().parse_args(["video.mp4"])
    assert (args.interval, args.threshold, args.count, args.columns) == (
        10.0,
        0.05,
        16,
        4,
    )
    assert (args.width, args.labels, args.quiet, args.output, args.pages) == (
        480,
        True,
        False,
        None,
        False,
    )


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out == f"yt-img {yt_img.__version__}\n"


def test_python_dash_m(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["yt-img", "--version"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("yt_img", run_name="__main__")
    assert exc.value.code == 0
    assert yt_img.__version__ in capsys.readouterr().out


def test_console_script_is_installed() -> None:
    script = shutil.which("yt-img", path=str(Path(sys.executable).parent))
    assert script is not None
