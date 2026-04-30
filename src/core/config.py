"""Application configuration management"""

import json
from pathlib import Path
from typing import Any


class Config:
    """Manages application settings and preferences"""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            # Default config location
            from PySide6.QtCore import QStandardPaths
            config_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "quartz_config.json"

        self.config_path = config_path
        self.data: dict[str, Any] = self.load()

    def load(self) -> dict[str, Any]:
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        return self.default_config()

    def default_config(self) -> dict[str, Any]:
        """Return default configuration"""
        return {
            "workspace_path": str(Path.home() / "Quartz"),
            "theme": "system",  # Deprecated - use color_scheme and mode instead
            "color_scheme": "default",  # default, magenta, modern
            "mode": "light",  # light, dark
            "density": "comfortable",  # compact, comfortable
            "table_row_height": 24,
            "column_width_default": 120,
            "font_size": 10,
            "autosave": True,
            "backup_enabled": True,
            "backup_frequency": "daily",  # daily, weekly
            "advanced_mode_enabled": False,
            "sql_write_enabled": False,
            "grid_size": 8,
            "shortcuts": {},
            "compact_view": False,
            "visible_collection_panel": True,
            "show_key_column": True,
            "expanded_view": False,
            "date_format": "yyyy-MM-dd",  # Default ISO date format
            "datetime_format": "yyyy-MM-dd HH:mm:ss",  # Default ISO datetime format
            "auto_check_for_updates": False,  # Auto-check for updates on startup
            "update_ignored_versions": [],  # List of versions user chose to ignore
        }

    def save(self):
        """Save configuration to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    def get(self, key: str, default=None):
        """Get a configuration value"""
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        """Set a configuration value"""
        self.data[key] = value
        self.save()

    @property
    def workspace_path(self) -> Path:
        """Get workspace path"""
        return Path(self.get("workspace_path", str(Path.home() / "Quartz")))

    @workspace_path.setter
    def workspace_path(self, value: Path):
        """Set workspace path"""
        self.set("workspace_path", str(value))
