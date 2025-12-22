"""Update downloader and installer"""

import os
import sys
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Callable


class UpdateDownloader:
    """Downloads and installs application updates"""
    
    @staticmethod
    def download_update(
        download_url: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
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
            raise Exception(f"Download failed: {e}")
    
    @staticmethod
    def install_update(downloaded_file: Path, current_exe_path: Optional[Path] = None) -> bool:
        """
        Install the update by replacing the current executable.
        
        Args:
            downloaded_file: Path to downloaded update file
            current_exe_path: Path to current executable (auto-detected if None)
        
        Returns:
            True if installation script was created successfully
        """
        if current_exe_path is None:
            # Auto-detect current executable path
            if hasattr(sys, '_MEIPASS'):
                # Running from PyInstaller bundle
                current_exe_path = Path(sys.executable)
            else:
                # Running from script
                current_exe_path = Path(sys.executable)
        
        if not current_exe_path.exists():
            raise Exception(f"Current executable not found: {current_exe_path}")
        
        if not downloaded_file.exists():
            raise Exception(f"Downloaded file not found: {downloaded_file}")
        
        # Create installer script
        if sys.platform == 'win32':
            return UpdateDownloader._create_windows_installer(
                downloaded_file, current_exe_path
            )
        else:
            raise Exception(f"Auto-update not supported on {sys.platform}")
    
    @staticmethod
    def _create_windows_installer(
        new_exe: Path,
        current_exe: Path
    ) -> bool:
        """Create Windows batch script to install update"""
        temp_dir = Path(tempfile.gettempdir()) / "quartz_updates"
        temp_dir.mkdir(exist_ok=True)
        
        installer_script = temp_dir / "install_update.bat"
        
        # Create batch script that:
        # 1. Waits a moment for current app to close
        # 2. Replaces the exe (with retry logic)
        # 3. Starts the new exe
        # 4. Deletes itself
        
        # Use absolute paths
        new_exe_abs = new_exe.resolve()
        current_exe_abs = current_exe.resolve()
        installer_script_abs = installer_script.resolve()
        
        script_content = f"""@echo off
REM Quartz Update Installer
echo Waiting for Quartz to close...
timeout /t 3 /nobreak >nul

REM Try to replace the executable (retry up to 5 times)
set retries=0
:retry
copy /Y "{new_exe_abs}" "{current_exe_abs}" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Update installed successfully!
    start "" "{current_exe_abs}"
    timeout /t 1 /nobreak >nul
    del /F /Q "{installer_script_abs}" >nul 2>&1
    del /F /Q "{new_exe_abs}" >nul 2>&1
    exit /B 0
) else (
    set /a retries+=1
    if %retries% LSS 5 (
        echo Retrying installation... (%retries%/5)
        timeout /t 2 /nobreak >nul
        goto retry
    ) else (
        echo Update installation failed! The executable may be in use.
        echo Please close Quartz and run this installer again: {installer_script_abs}
        pause
        exit /B 1
    )
)
"""
        
        try:
            with open(installer_script, 'w') as f:
                f.write(script_content)
            return True
        except Exception as e:
            raise Exception(f"Failed to create installer script: {e}")

