"""Preferences/Settings dialog"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QWidget,
    QLineEdit, QSpinBox, QComboBox, QCheckBox, QGroupBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

from src.core.config import Config
from src.ui.styles import AppStyles


class PreferencesDialog(QDialog):
    """Preferences/Settings dialog"""
    
    def __init__(self, parent=None, config: Optional[Config] = None):
        super().__init__(parent)
        self.config = config
        
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self._apply_theme()
        self._init_ui()
        self._load_settings()
    
    def _apply_theme(self):
        """Apply theme stylesheet"""
        if self.config:
            # Support new theme system with color_scheme and mode
            color_scheme = self.config.get("color_scheme", "default")
            mode = self.config.get("mode", "light")
            
            # Backward compatibility: if old theme setting exists, use it
            old_theme = self.config.get("theme", None)
            if old_theme and old_theme in ["light", "dark", "system"]:
                mode = old_theme if old_theme != "system" else "light"
            
            stylesheet = AppStyles.get_theme(color_scheme=color_scheme, mode=mode)
            self.setStyleSheet(stylesheet)
    
    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Tab widget
        tabs = QTabWidget()
        
        # General tab
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "General")
        
        # Appearance tab
        appearance_tab = self._create_appearance_tab()
        tabs.addTab(appearance_tab, "Appearance")
        
        # Advanced tab
        advanced_tab = self._create_advanced_tab()
        tabs.addTab(advanced_tab, "Advanced")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._save_and_close)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
    
    def _create_general_tab(self) -> QWidget:
        """Create General tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Workspace
        workspace_group = QGroupBox("Workspace")
        workspace_layout = QVBoxLayout()
        
        workspace_path_layout = QHBoxLayout()
        workspace_path_layout.addWidget(QLabel("Workspace Path:"))
        self.workspace_path_input = QLineEdit()
        self.workspace_path_input.setReadOnly(True)
        workspace_path_layout.addWidget(self.workspace_path_input)
        
        browse_workspace_btn = QPushButton("Browse...")
        browse_workspace_btn.clicked.connect(self._browse_workspace)
        workspace_path_layout.addWidget(browse_workspace_btn)
        
        workspace_layout.addLayout(workspace_path_layout)
        workspace_group.setLayout(workspace_layout)
        layout.addWidget(workspace_group)
        
        # Data
        data_group = QGroupBox("Data")
        data_layout = QVBoxLayout()
        
        self.autosave_check = QCheckBox("Autosave changes")
        data_layout.addWidget(self.autosave_check)
        
        self.backup_check = QCheckBox("Enable automatic backups")
        data_layout.addWidget(self.backup_check)
        
        backup_freq_layout = QHBoxLayout()
        backup_freq_layout.addWidget(QLabel("Backup frequency:"))
        self.backup_freq_combo = QComboBox()
        self.backup_freq_combo.addItems(["Daily", "Weekly"])
        backup_freq_layout.addWidget(self.backup_freq_combo)
        backup_freq_layout.addStretch()
        data_layout.addLayout(backup_freq_layout)
        
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        layout.addStretch()
        return widget
    
    def _create_appearance_tab(self) -> QWidget:
        """Create Appearance tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Color Scheme
        color_scheme_group = QGroupBox("Color Scheme")
        color_scheme_layout = QVBoxLayout()
        color_scheme_layout.addWidget(QLabel("Color Scheme:"))
        self.color_scheme_combo = QComboBox()
        self.color_scheme_combo.addItems(["Default (Purple)", "Magenta", "Modern (Black/Grey)"])
        self.color_scheme_combo.currentTextChanged.connect(self._on_theme_changed)
        color_scheme_layout.addWidget(self.color_scheme_combo)
        color_scheme_group.setLayout(color_scheme_layout)
        layout.addWidget(color_scheme_group)
        
        # Table View Settings
        table_group = QGroupBox("Table View")
        table_layout = QVBoxLayout()
        table_layout.setSpacing(8)
        
        # Row Height
        row_height_layout = QHBoxLayout()
        row_height_label = QLabel("Row Height:")
        row_height_label.setMinimumWidth(120)
        row_height_layout.addWidget(row_height_label)
        self.row_height_spin = QSpinBox()
        self.row_height_spin.setMinimum(20)
        self.row_height_spin.setMaximum(50)
        self.row_height_spin.setSuffix(" px")
        self.row_height_spin.setMinimumWidth(100)
        row_height_layout.addWidget(self.row_height_spin)
        row_height_layout.addStretch()
        table_layout.addLayout(row_height_layout)
        
        # Default Column Width
        col_width_layout = QHBoxLayout()
        col_width_label = QLabel("Default Column Width:")
        col_width_label.setMinimumWidth(120)
        col_width_layout.addWidget(col_width_label)
        self.col_width_spin = QSpinBox()
        self.col_width_spin.setMinimum(50)
        self.col_width_spin.setMaximum(500)
        self.col_width_spin.setSuffix(" px")
        self.col_width_spin.setMinimumWidth(100)
        col_width_layout.addWidget(self.col_width_spin)
        col_width_layout.addStretch()
        table_layout.addLayout(col_width_layout)
        
        # Font Size
        font_size_layout = QHBoxLayout()
        font_size_label = QLabel("Font Size:")
        font_size_label.setMinimumWidth(120)
        font_size_layout.addWidget(font_size_label)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setMinimum(8)
        self.font_size_spin.setMaximum(20)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setMinimumWidth(100)
        font_size_layout.addWidget(self.font_size_spin)
        font_size_layout.addStretch()
        table_layout.addLayout(font_size_layout)
        
        # Hide table images
        self.hide_table_images_check = QCheckBox("Hide table images")
        table_layout.addWidget(self.hide_table_images_check)
        
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Date/Time Format Settings
        date_format_group = QGroupBox("Date/Time Format")
        date_format_layout = QVBoxLayout()
        date_format_layout.setSpacing(8)
        
        # Date Format
        date_format_layout.addWidget(QLabel("Date Format:"))
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems([
            "yyyy-MM-dd",  # ISO: 2024-01-15
            "MM/dd/yyyy",  # US: 01/15/2024
            "dd.MM.yyyy",  # European: 15.01.2024
            "dd/MM/yyyy",  # UK: 15/01/2024
            "MMM d, yyyy",  # Jan 15, 2024
            "ddd MMM d yyyy",  # Mon Jan 15 2024
        ])
        self.date_format_combo.setToolTip("Select date format")
        date_format_layout.addWidget(self.date_format_combo)
        
        # DateTime Format
        date_format_layout.addWidget(QLabel("DateTime Format:"))
        self.datetime_format_combo = QComboBox()
        self.datetime_format_combo.addItems([
            "yyyy-MM-dd HH:mm:ss",  # ISO: 2024-01-15 14:30:00
            "MM/dd/yyyy hh:mm AP",  # US: 01/15/2024 02:30 PM
            "dd.MM.yyyy HH:mm",  # European: 15.01.2024 14:30
            "dd/MM/yyyy HH:mm",  # UK: 15/01/2024 14:30
            "MMM d, yyyy hh:mm AP",  # Jan 15, 2024 02:30 PM
            "yyyy-MM-dd HH:mm",  # ISO short: 2024-01-15 14:30
        ])
        self.datetime_format_combo.setToolTip("Select datetime format")
        date_format_layout.addWidget(self.datetime_format_combo)
        
        date_format_group.setLayout(date_format_layout)
        layout.addWidget(date_format_group)
        
        # Reset Defaults button (moved here)
        reset_defaults_btn = QPushButton("Reset Defaults")
        reset_defaults_btn.setProperty("class", "secondary")
        reset_defaults_btn.clicked.connect(self._reset_table_defaults)
        table_layout.addWidget(reset_defaults_btn)
        
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        layout.addStretch()
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """Create Advanced tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # SQL Console
        sql_group = QGroupBox("SQL Console")
        sql_layout = QVBoxLayout()
        
        self.enable_sql_check = QCheckBox("Enable SQL Console")
        sql_layout.addWidget(self.enable_sql_check)
        
        self.allow_attach_check = QCheckBox("Allow attaching other databases")
        sql_layout.addWidget(self.allow_attach_check)
        
        self.allow_write_sql_check = QCheckBox("Allow write operations (dangerous)")
        self.allow_write_sql_check.setStyleSheet("color: red;")
        sql_layout.addWidget(self.allow_write_sql_check)
        
        sql_group.setLayout(sql_layout)
        layout.addWidget(sql_group)
        
        layout.addStretch()
        return widget
    
    def _on_theme_changed(self):
        """Handle theme change in preferences dialog - live preview"""
        if not self.config:
            return
        
        # Get current selection (mode is kept from config, not shown in UI)
        color_scheme_map = {"Default (Purple)": "default", "Magenta": "magenta", "Modern (Black/Grey)": "modern"}
        
        color_scheme = color_scheme_map.get(self.color_scheme_combo.currentText(), "default")
        mode = self.config.get("mode", "light")  # Keep current mode
        
        # Temporarily update config to preview theme
        old_color_scheme = self.config.get("color_scheme", "default")
        
        self.config.set("color_scheme", color_scheme)
        
        # Apply theme
        self._apply_theme()
        
        # Restore old values (will be saved when user clicks OK)
        self.config.set("color_scheme", old_color_scheme)
    
    def _browse_workspace(self):
        """Browse for workspace directory"""
        from PySide6.QtWidgets import QFileDialog
        dir_path = QFileDialog.getExistingDirectory(self, "Select Workspace Directory")
        if dir_path:
            self.workspace_path_input.setText(dir_path)
    
    def _load_settings(self):
        """Load current settings"""
        if not self.config:
            return
        
        # General
        self.workspace_path_input.setText(str(self.config.workspace_path))
        self.autosave_check.setChecked(self.config.get("autosave", True))
        self.backup_check.setChecked(self.config.get("backup_enabled", True))
        backup_freq = self.config.get("backup_frequency", "daily")
        self.backup_freq_combo.setCurrentText(backup_freq.capitalize())
        
        # Appearance
        # Load color scheme
        color_scheme = self.config.get("color_scheme", "default")
        color_scheme_map = {"default": "Default (Purple)", "magenta": "Magenta", "modern": "Modern (Black/Grey)"}
        self.color_scheme_combo.setCurrentText(color_scheme_map.get(color_scheme, "Default (Purple)"))
        
        self.row_height_spin.setValue(self.config.get("table_row_height", 24))
        self.col_width_spin.setValue(self.config.get("column_width_default", 120))
        self.font_size_spin.setValue(self.config.get("font_size", 10))
        self.hide_table_images_check.setChecked(self.config.get("hide_table_images", False))
        
        # Date/Time formats
        date_format = self.config.get("date_format", "yyyy-MM-dd")
        datetime_format = self.config.get("datetime_format", "yyyy-MM-dd HH:mm:ss")
        # Set combo box values (find index or add if not in list)
        date_index = self.date_format_combo.findText(date_format)
        if date_index >= 0:
            self.date_format_combo.setCurrentIndex(date_index)
        else:
            self.date_format_combo.setCurrentIndex(0)  # Default to first item
        
        datetime_index = self.datetime_format_combo.findText(datetime_format)
        if datetime_index >= 0:
            self.datetime_format_combo.setCurrentIndex(datetime_index)
        else:
            self.datetime_format_combo.setCurrentIndex(0)  # Default to first item
        
        # Advanced
        self.enable_sql_check.setChecked(self.config.get("advanced_mode_enabled", False))
        self.allow_attach_check.setChecked(self.config.get("allow_attach", False))
        self.allow_write_sql_check.setChecked(self.config.get("sql_write_enabled", False))
    
    def _save_and_close(self):
        """Save settings and close"""
        if not self.config:
            self.accept()
            return
        
        # General
        workspace_path = self.workspace_path_input.text()
        if workspace_path:
            self.config.workspace_path = Path(workspace_path)
        
        self.config.set("autosave", self.autosave_check.isChecked())
        self.config.set("backup_enabled", self.backup_check.isChecked())
        self.config.set("backup_frequency", self.backup_freq_combo.currentText().lower())
        
        # Appearance
        # Save color scheme
        color_scheme_map = {"Default (Purple)": "default", "Magenta": "magenta", "Modern (Black/Grey)": "modern"}
        self.config.set("color_scheme", color_scheme_map.get(self.color_scheme_combo.currentText(), "default"))
        
        self.config.set("table_row_height", self.row_height_spin.value())
        self.config.set("column_width_default", self.col_width_spin.value())
        self.config.set("font_size", self.font_size_spin.value())
        self.config.set("hide_table_images", self.hide_table_images_check.isChecked())
        
        # Date/Time formats
        self.config.set("date_format", self.date_format_combo.currentText())
        self.config.set("datetime_format", self.datetime_format_combo.currentText())
        
        # Advanced
        self.config.set("advanced_mode_enabled", self.enable_sql_check.isChecked())
        self.config.set("allow_attach", self.allow_attach_check.isChecked())
        self.config.set("sql_write_enabled", self.allow_write_sql_check.isChecked())
        
        self.config.save()
        self.accept()
    
    def _reset_table_defaults(self):
        """Reset table view settings to defaults"""
        self.row_height_spin.setValue(24)
        self.col_width_spin.setValue(120)
        self.font_size_spin.setValue(10)
        self.date_format_combo.setCurrentIndex(0)  # yyyy-MM-dd
        self.datetime_format_combo.setCurrentIndex(0)  # yyyy-MM-dd HH:mm:ss
