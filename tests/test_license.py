import hashlib
from importlib.metadata import metadata
from pathlib import Path

LICENSE = Path(__file__).resolve().parent.parent / "LICENSE"

# SHA-256 of https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
GPL2_SHA256 = "edaef632cbb643e4e7a221717a6c441a4c1a7c918e6e4d56debc3d8739b233f6"


def test_license_is_the_unmodified_gpl2_text() -> None:
    assert hashlib.sha256(LICENSE.read_bytes()).hexdigest() == GPL2_SHA256


def test_package_metadata_declares_gpl2_only() -> None:
    assert metadata("yt-img")["License-Expression"] == "GPL-2.0-only"
