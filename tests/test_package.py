from importlib.metadata import version

import yt_img


def test_version_matches_metadata() -> None:
    assert yt_img.__version__ == version("yt-img")
