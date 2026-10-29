"""Tests for update checks and checksum-verified downloads"""

import hashlib
import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from src.core.update_downloader import UpdateDownloader

pytest.importorskip("PySide6.QtCore")
from src.core.update_checker import UpdateChecker  # noqa: E402

DIGEST = "866fd9a0016feb1545d64d9afd3f574f5563dd1ae67b17d0ffc0a50c0d55631e"


@pytest.fixture
def release_file(tmp_path, monkeypatch):
    # download_update saves into <tempdir>/quartz_updates
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path / "tmp"))
    path = tmp_path / "Quartz-windows-9.9.9.exe"
    path.write_bytes(b"new quartz build")
    return path, hashlib.sha256(b"new quartz build").hexdigest()


def test_download_with_matching_checksum(release_file):
    path, sha256 = release_file
    downloaded = UpdateDownloader.download_update(path.as_uri(), expected_sha256=sha256.upper())
    assert downloaded == path.parent / "tmp" / "quartz_updates" / path.name
    assert downloaded.read_bytes() == b"new quartz build"


def test_download_with_wrong_checksum_is_deleted(release_file):
    path, _ = release_file
    with pytest.raises(Exception, match="checksum verification"):
        UpdateDownloader.download_update(path.as_uri(), expected_sha256="0" * 64)
    assert not (path.parent / "tmp" / "quartz_updates" / path.name).exists()


def test_download_without_checksum_is_refused(release_file):
    path, _ = release_file
    with patch("urllib.request.urlretrieve") as retrieve:
        with pytest.raises(Exception, match="no checksum"):
            UpdateDownloader.download_update(path.as_uri())
    retrieve.assert_not_called()


@pytest.mark.parametrize(
    ("newer", "older"),
    [("4.10.0", "4.9.0"), ("4.2.1", "4.2.0"), ("5", "4.99.99"), ("4.2.0.1", "4.2")],
)
def test_is_newer(newer, older):
    assert UpdateChecker._is_newer(newer, older)
    assert not UpdateChecker._is_newer(older, newer)


@pytest.mark.parametrize(("a", "b"), [("4.2.0", "4.2.0"), ("4.2", "4.2.0"), ("4.2.0-beta", "4.2.0"), ("", "4.2.0")])
def test_is_not_newer(a, b):
    assert not UpdateChecker._is_newer(a, b)


def release_response(tag, assets):
    body = json.dumps({"tag_name": tag, "html_url": "https://example/release", "assets": assets})
    return io.BytesIO(body.encode())


def test_check_for_updates_returns_asset_checksum():
    assets = [
        {"name": "notes.txt", "browser_download_url": "https://example/notes.txt"},
        {
            "name": "Quartz-windows-99.0.0.exe",
            "browser_download_url": "https://example/Quartz-windows-99.0.0.exe",
            "digest": f"sha256:{DIGEST}",
        },
    ]
    with patch("urllib.request.urlopen", return_value=release_response("v99.0.0", assets)):
        info = UpdateChecker.check_for_updates()
    assert info["version"] == "99.0.0"
    assert info["download_url"] == "https://example/Quartz-windows-99.0.0.exe"
    assert info["sha256"] == DIGEST


def test_check_for_updates_without_digest():
    assets = [{"name": "Quartz-windows-99.0.0.exe", "browser_download_url": "https://example/q.exe"}]
    with patch("urllib.request.urlopen", return_value=release_response("v99.0.0", assets)):
        info = UpdateChecker.check_for_updates()
    assert info["download_url"] == "https://example/q.exe"
    assert info["sha256"] is None


def test_check_for_updates_when_current():
    with patch("urllib.request.urlopen", return_value=release_response("v0.0.1", [])):
        assert UpdateChecker.check_for_updates() is None


def test_check_for_updates_network_error_raises():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
        with pytest.raises(RuntimeError, match="Network error"):
            UpdateChecker.check_for_updates()
