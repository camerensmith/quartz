"""Update downloader and installer"""

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
        progress_callback: Callable[[int, int], None] | None = None
    ) -> Path:
        """
        Download update file to temporary location.

        Args:
            download_url: URL to download from
            progress_callback: Optional callback(byte_count, total_bytes) for progress updates

        Returns:
            Path to downloaded file
        """
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
            return download_path
        except Exception as e:
            # Clean up on error
            if download_path.exists():
                download_path.unlink()
            raise Exception(f"Download failed: {e}") from e

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

