"""Update checker service using GitHub Releases API"""

import json
import urllib.request

from PySide6.QtCore import QThread, Signal

from src.core.version import VERSION


class UpdateCheckWorker(QThread):
    """Background thread that checks GitHub for the latest release."""

    update_available = Signal(dict)   # emitted when a newer version exists
    no_update = Signal()              # emitted when already on latest version
    error = Signal(str)               # emitted on any failure

    def run(self):
        try:
            update_info = UpdateChecker.check_for_updates()
            if update_info:
                self.update_available.emit(update_info)
            else:
                self.no_update.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class UpdateChecker:
    """Checks for application updates via GitHub Releases"""

    GITHUB_REPO = "camerensmith/quartz"
    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

    @staticmethod
    def check_for_updates() -> dict | None:
        """
        Check for updates from GitHub Releases.
        Returns update info dict if newer version available, None otherwise.

        Returns:
            Dict with keys: version, url, download_url, changelog, published_at, assets
            None if no update available or check failed
        """
        try:
            # Make request to GitHub API
            req = urllib.request.Request(UpdateChecker.GITHUB_API_URL)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            req.add_header('User-Agent', 'Quartz-UpdateChecker/1.0')

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Extract version from tag (remove 'v' prefix if present)
            latest_version = data.get('tag_name', '').lstrip('v')
            current_version = VERSION

            # Compare versions
            if UpdateChecker._is_newer(latest_version, current_version):
                # Find download URL for Windows .exe
                download_url = UpdateChecker._find_download_url(data.get('assets', []))

                return {
                    'version': latest_version,
                    'url': data.get('html_url', ''),
                    'download_url': download_url,
                    'changelog': data.get('body', 'No changelog available.'),
                    'published_at': data.get('published_at', ''),
                    'assets': data.get('assets', [])
                }
        except urllib.error.URLError as e:
            print(f"Update check failed (network error): {e}")
        except json.JSONDecodeError as e:
            print(f"Update check failed (invalid JSON): {e}")
        except Exception as e:
            print(f"Update check failed: {e}")

        return None

    @staticmethod
    def _is_newer(version1: str, version2: str) -> bool:
        """Check if version1 is newer than version2 using semantic versioning"""
        try:
            from packaging import version
            return version.parse(version1) > version.parse(version2)
        except Exception:
            # Fallback: simple string comparison if packaging not available
            return version1 > version2

    @staticmethod
    def _find_download_url(assets: list) -> str | None:
        """
        Find the Windows .exe download URL from release assets.
        Prefers files with 'windows' in name, falls back to any .exe
        """
        # First try to find Windows-specific .exe
        for asset in assets:
            name = asset.get('name', '').lower()
            if name.endswith('.exe') and 'windows' in name:
                return asset.get('browser_download_url')

        # Fallback: any .exe file
        for asset in assets:
            if asset.get('name', '').lower().endswith('.exe'):
                return asset.get('browser_download_url')

        return None

