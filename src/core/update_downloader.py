"""Update downloader and installer"""

import hashlib
import os
import subprocess
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
        Install the update and restart Quartz on the new version.

        Releases are single portable executables, so installing means replacing the
        running Quartz.exe. A running exe can't be overwritten, so a helper script
        waits for Quartz to exit, moves the new exe over the old one and starts it.
        The calling code should quit the application shortly after this returns.

        Args:
            downloaded_file: Path to the downloaded executable
            current_exe_path: Executable to replace; defaults to the running one when frozen

        Returns:
            True if the update was handed off successfully
        """
        if not downloaded_file.exists():
            raise Exception(f"Downloaded file not found: {downloaded_file}")

        if sys.platform != 'win32':
            raise Exception(f"Auto-update not supported on {sys.platform}")

        if current_exe_path is None and getattr(sys, "frozen", False):
            current_exe_path = Path(sys.executable)
        if current_exe_path is None:
            # Running from source: there's no Quartz.exe to replace
            return UpdateDownloader._launch_windows_installer(downloaded_file)

        script = downloaded_file.with_suffix(".update.cmd")
        try:
            # cmd reads batch files in the console (OEM) code page; the script has its own \r\n
            script.write_text(
                UpdateDownloader._replace_script(downloaded_file, current_exe_path),
                encoding="oem",
                newline="",
            )
        except UnicodeEncodeError:
            # A path the console code page can't represent: run the new version where it is
            return UpdateDownloader._launch_windows_installer(downloaded_file)
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", str(script)],
                creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
                close_fds=True,
            )
            return True
        except OSError:
            # Couldn't start the helper: run the new version from where it was downloaded
            return UpdateDownloader._launch_windows_installer(downloaded_file)

    @staticmethod
    def _replace_script(new_exe: Path, current_exe: Path, attempts: int = 60) -> str:
        """Batch script that replaces *current_exe* with *new_exe* once Quartz exits, then starts it.

        Retries the move about once a second (Windows refuses while the exe is running).
        If it never succeeds, e.g. the install folder isn't writable, the new version is
        started from the download folder instead, so the user still ends up on it.
        """
        def quote(path: Path) -> str:
            # cmd expands %VAR% even inside quotes
            return '"' + str(path).replace("%", "%%") + '"'

        new, current = quote(new_exe), quote(current_exe)
        return "\r\n".join([
            "@echo off",
            "rem Quartz updater: replace Quartz.exe with the new version once Quartz has exited",
            "set tries=0",
            ":move",
            f"move /Y {new} {current} >NUL 2>&1 && goto relaunch",
            "set /a tries+=1",
            f"if %tries% GEQ {attempts} goto fallback",
            # ping is the usual sleep for scripts without a console (timeout needs one)
            "ping -n 2 127.0.0.1 >NUL",
            "goto move",
            ":relaunch",
            f'start "" {current}',
            "goto cleanup",
            ":fallback",
            f'start "" {new}',
            ":cleanup",
            # Delete this script after it finishes
            '(goto) 2>NUL & del "%~f0"',
            "",
        ])

    @staticmethod
    def _launch_windows_installer(installer_exe: Path) -> bool:
        """Launch the downloaded executable via the shell so it runs independently."""
        try:
            # os.startfile is the Windows-native way to open a file as if double-clicked;
            # the process is fully detached from the current app.
            os.startfile(str(installer_exe))  # type: ignore[attr-defined]
            return True
        except Exception as e:
            raise Exception(f"Failed to launch installer: {e}") from e
