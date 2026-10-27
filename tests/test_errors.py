from yt_img.errors import YtImgError


def test_is_an_exception_with_message() -> None:
    err = YtImgError("boom")
    assert isinstance(err, Exception)
    assert str(err) == "boom"
