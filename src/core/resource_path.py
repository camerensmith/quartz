"""Helper module for finding resource paths in both development and PyInstaller builds"""

import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """
    Get absolute path to resource, works for dev and PyInstaller.
    
    Args:
        relative_path: Path relative to project root (e.g., "assets/icon.png")
    
    Returns:
        Absolute Path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Running in development mode
        base_path = Path(__file__).parent.parent.parent
    
    return base_path / relative_path


def asset_path(asset_name: str) -> Path:
    """
    Get path to an asset file.
    
    Args:
        asset_name: Asset filename (e.g., "create_collection.png")
    
    Returns:
        Path to the asset file
    """
    return resource_path(f"assets/{asset_name}")


def get_quartz_icon_path() -> Path:
    """Get path to the main quartz.png icon"""
    return resource_path("quartz.png")

