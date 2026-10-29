"""Update checker service using GitHub Releases API"""

import json
import logging
import re
import urllib.error
import urllib.request

from PySide6.QtCore import QThread, Signal

from src.core.version import VERSION

logger = logging.getLogger(__name__)


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

        Returns:
            Dict with keys: version, url, download_url, sha256, changelog, published_at, assets
            None if already on the latest version

        Raises:
            RuntimeError: if the release information couldn't be fetched
        """
        try:
            # Make request to GitHub API
            req = urllib.request.Request(UpdateChecker.GITHUB_API_URL)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            req.add_header('User-Agent', 'Quartz-UpdateChecker/1.0')

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            logger.warning("Update check failed (network error): %s", e)
            raise RuntimeError(f"Network error: {e.reason}") from e
        except json.JSONDecodeError as e:
            logger.warning("Update check failed (invalid JSON): %s", e)
            raise RuntimeError("GitHub returned an invalid response") from e

        # Extract version from tag (remove 'v' prefix if present)
        latest_version = data.get('tag_name', '').lstrip('v')
        if not UpdateChecker._is_newer(latest_version, VERSION):
            return None

        asset = UpdateChecker._find_download_asset(data.get('assets', []))
        return {
            'version': latest_version,
            'url': data.get('html_url', ''),
            'download_url': asset.get('browser_download_url') if asset else None,
            'sha256': UpdateChecker._asset_sha256(asset) if asset else None,
            'changelog': data.get('body', 'No changelog available.'),
            'published_at': data.get('published_at', ''),
            'assets': data.get('assets', [])
        }

    @staticmethod
    def _version_tuple(version: str) -> tuple[int, ...] | None:
        """Parse the numeric part of a version ("4.10.0-beta" -> (4, 10, 0)), or None"""
        match = re.match(r"\d+(?:\.\d+)*", version.strip())
        return tuple(int(part) for part in match.group().split(".")) if match else None

    @staticmethod
    def _is_newer(version1: str, version2: str) -> bool:
        """Check if version1 is newer than version2, comparing numerically (4.10 > 4.9)"""
        v1 = UpdateChecker._version_tuple(version1)
        v2 = UpdateChecker._version_tuple(version2)
        if v1 is None or v2 is None:
            return False
        # Pad so 4.2 == 4.2.0
        width = max(len(v1), len(v2))
        return v1 + (0,) * (width - len(v1)) > v2 + (0,) * (width - len(v2))

    @staticmethod
    def _find_download_asset(assets: list) -> dict | None:
        """
        Find the Windows .exe asset among the release assets.
        Prefers files with 'windows' in name, falls back to any .exe
        """
        # First try to find Windows-specific .exe
        for asset in assets:
            name = asset.get('name', '').lower()
            if name.endswith('.exe') and 'windows' in name:
                return asset

        # Fallback: any .exe file
        for asset in assets:
            if asset.get('name', '').lower().endswith('.exe'):
                return asset

        return None

    @staticmethod
    def _asset_sha256(asset: dict) -> str | None:
        """SHA-256 GitHub records for a release asset ("digest": "sha256:<hex>"), if present"""
        digest = asset.get('digest') or ''
        algorithm, _, value = digest.partition(':')
        if algorithm == 'sha256' and re.fullmatch(r"[0-9a-f]{64}", value):
            return value
        return None
