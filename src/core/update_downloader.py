"""Update downloader and installer"""

import hashlib
import os
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path


class UpdateDownloader:
    """Downloads and installs application updates"""

    @staticmethod
    def download_update(
        download_url: str,
        progress_callback: Callable[[int, int], None] | None = None,
        expected_sha256: str | None = None,
    ) -> Path:
        """
        Download update file to temporary location and verify its checksum.

        Args:
            download_url: URL to download from
            progress_callback: Optional callback(byte_count, total_bytes) for progress updates
            expected_sha256: Hex SHA-256 the release publishes for this file

        Returns:
            Path to downloaded file

        Raises:
            Exception: if there's no checksum to verify against, the download fails,
                or the file doesn't match the checksum (the file is deleted)
        """
        # Never hand an unverified executable to the installer
        if not expected_sha256:
            raise Exception("This release has no checksum to verify the download against")

        # Create temp file for download
        temp_dir = Path(tempfile.gettempdir()) / "quartz_updates"
        temp_dir.mkdir(exist_ok=True)

        # Get filename from URL
        filename = download_url.split('/')[-1].split('?')[0]
        if not filename.endswith('.exe'):
            filename = "quartz_update.exe"

        download_path = temp_dir / filename

        # Download with progress tracking
        def report_progress(block_num, block_size, total_size):
            if progress_callback and total_size > 0:
                downloaded = block_num * block_size
                progress_callback(min(downloaded, total_size), total_size)

        try:
            urllib.request.urlretrieve(
                download_url,
                str(download_path),
                reporthook=report_progress
            )
        except Exception as e:
            # Clean up on error
            if download_path.exists():
                download_path.unlink()
            raise Exception(f"Download failed: {e}") from e

        actual_sha256 = UpdateDownloader._sha256(download_path)
        if actual_sha256 != expected_sha256.lower():
            download_path.unlink()
            raise Exception(
                "Downloaded file failed checksum verification and was deleted "
                f"(expected {expected_sha256}, got {actual_sha256})"
            )
        return download_path

    @staticmethod
    def _sha256(path: Path) -> str:
        """Hex SHA-256 of a file"""
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def install_update(downloaded_file: Path, current_exe_path: Path | None = None) -> bool:
        """
        Install the update by launching the downloaded installer executable.

        The installer handles replacing the existing installation in-place.
        The calling code should quit the application shortly after this returns.

        Args:
            downloaded_file: Path to downloaded installer executable
            current_exe_path: Unused; kept for API compatibility

        Returns:
            True if the installer was launched successfully
        """
        if not downloaded_file.exists():
            raise Exception(f"Downloaded file not found: {downloaded_file}")

        if sys.platform == 'win32':
            return UpdateDownloader._launch_windows_installer(downloaded_file)
        else:
            raise Exception(f"Auto-update not supported on {sys.platform}")

    @staticmethod
    def _launch_windows_installer(installer_exe: Path) -> bool:
        """Launch the Windows installer executable via the shell so it runs independently."""
        try:
            # os.startfile is the Windows-native way to open a file as if double-clicked;
            # the process is fully detached from the current app.
            os.startfile(str(installer_exe))
            return True
        except Exception as e:
            raise Exception(f"Failed to launch installer: {e}") from e

