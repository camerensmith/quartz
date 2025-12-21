"""Export dialog for collections"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup,
    QComboBox, QPushButton, QFileDialog, QMessageBox, QGroupBox, QCheckBox
)
from PySide6.QtCore import Qt

from src.core.export_service import ExportService


class ExportDialog(QDialog):
    """Dialog for exporting collection data"""
    
    def __init__(self, parent=None, export_service: Optional[ExportService] = None,
                 selected_record_ids: Optional[List[int]] = None):
        super().__init__(parent)
        self.export_service = export_service
        self.selected_record_ids = selected_record_ids
        self.export_path: Optional[Path] = None
        self.export_format: str = "csv"
        self.export_scope: str = "all"
        
        self.setWindowTitle("Export Collection")
        self.setMinimumWidth(500)
        
        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Scope selection
        scope_group = QGroupBox("Export Scope")
        scope_layout = QVBoxLayout()
        self.scope_group = QButtonGroup()
        
        self.all_radio = QRadioButton("All records")
        self.all_radio.setChecked(True)
        self.scope_group.addButton(self.all_radio, 0)
        scope_layout.addWidget(self.all_radio)
        
        if self.selected_record_ids:
            count = len(self.selected_record_ids)
            self.selected_radio = QRadioButton(f"Selected records ({count})")
            self.scope_group.addButton(self.selected_radio, 1)
            scope_layout.addWidget(self.selected_radio)
        else:
            self.selected_radio = None
        
        scope_group.setLayout(scope_layout)
        layout.addWidget(scope_group)
        
        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["CSV", "JSON", "SQLite DB", "Pack (DB+Attachments)"])
        format_layout.addWidget(self.format_combo)
        
        # CSV options
        self.csv_options_group = QGroupBox("CSV Options")
        csv_layout = QVBoxLayout()
        
        self.include_headers_check = QCheckBox("Include headers")
        self.include_headers_check.setChecked(True)
        csv_layout.addWidget(self.include_headers_check)
        
        delimiter_layout = QHBoxLayout()
        delimiter_layout.addWidget(QLabel("Delimiter:"))
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems([",", ";", "\t"])
        delimiter_layout.addWidget(self.delimiter_combo)
        delimiter_layout.addStretch()
        csv_layout.addLayout(delimiter_layout)
        
        self.csv_options_group.setLayout(csv_layout)
        format_layout.addWidget(self.csv_options_group)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # File path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Save to:"))
        self.path_label = QLabel("(not selected)")
        self.path_label.setStyleSheet("color: gray;")
        path_layout.addWidget(self.path_label)
        path_layout.addStretch()
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        
        export_btn = QPushButton("Export")
        export_btn.setDefault(True)
        export_btn.clicked.connect(self._export)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(export_btn)
        layout.addLayout(button_layout)
    
    def _browse_file(self):
        """Browse for export file"""
        format_index = self.format_combo.currentIndex()
        formats = {
            0: ("CSV files (*.csv)", "csv"),
            1: ("JSON files (*.json)", "json"),
            2: ("SQLite Database (*.sqlite)", "sqlite"),
            3: ("Zip files (*.zip)", "zip")
        }
        file_filter, ext = formats.get(format_index, ("All files (*)", ""))
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Collection", "", file_filter
        )
        
        if file_path:
            # Ensure correct extension
            if ext and not file_path.endswith(f".{ext}"):
                file_path = f"{file_path}.{ext}"
            
            self.export_path = Path(file_path)
            self.path_label.setText(str(self.export_path))
            self.path_label.setStyleSheet("")
    
    def _export(self):
        """Perform export"""
        if not self.export_service:
            QMessageBox.warning(self, "Error", "No export service available")
            return
        
        if not self.export_path:
            QMessageBox.warning(self, "Error", "Please select a file path")
            return
        
        # Determine scope
        if self.selected_radio and self.selected_radio.isChecked():
            record_ids = self.selected_record_ids
            scope = "selected"
        else:
            record_ids = None
            scope = "all"
        
        # Determine format
        format_index = self.format_combo.currentIndex()
        formats = ["csv", "json", "db", "pack"]
        export_format = formats[format_index]
        
        # Perform export
        success = False
        try:
            if export_format == "csv":
                include_headers = self.include_headers_check.isChecked()
                delimiter = self.delimiter_combo.currentText()
                success = self.export_service.export_csv(
                    self.export_path, record_ids, include_headers, delimiter
                )
            elif export_format == "json":
                success = self.export_service.export_json(self.export_path, record_ids)
            elif export_format == "db":
                success = self.export_service.export_db(self.export_path)
            elif export_format == "pack":
                success = self.export_service.export_pack(self.export_path)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")
            return
        
        if success:
            QMessageBox.information(
                self, "Success",
                f"Collection exported successfully to:\n{self.export_path}"
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Export failed. Please check the file path and try again.")
