"""Export dialog for collections"""

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from src.core.export_service import ExportService
from src.core.workspace import Workspace


class ExportDialog(QDialog):
    """Dialog for exporting collection data"""

    def __init__(self, parent=None, export_service: ExportService | None = None,
                 selected_record_ids: list[int] | None = None,
                 workspace: Workspace | None = None):
        super().__init__(parent)
        self.export_service = export_service
        self.workspace = workspace
        self.selected_record_ids = selected_record_ids
        self.export_path: Path | None = None
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
        self.scope_group_box = QGroupBox("Export Scope")
        scope_layout = QVBoxLayout()
        self.scope_button_group = QButtonGroup()

        self.all_radio = QRadioButton("All records")
        self.all_radio.setChecked(True)
        self.scope_button_group.addButton(self.all_radio, 0)
        scope_layout.addWidget(self.all_radio)

        if self.selected_record_ids:
            count = len(self.selected_record_ids)
            self.selected_radio = QRadioButton(f"Selected records ({count})")
            self.scope_button_group.addButton(self.selected_radio, 1)
            scope_layout.addWidget(self.selected_radio)
        else:
            self.selected_radio = None

        self.scope_group_box.setLayout(scope_layout)
        layout.addWidget(self.scope_group_box)

        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout()

        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "CSV",
            "Excel (.xlsx)",
            "JSON",
            "SQLite DB",
            "Pack (DB+Attachments)",
            "Quartz Workspace (.qz)",
        ])
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addWidget(self.format_combo)

        self.qz_hint_label = QLabel(
            "Exports the entire workspace (all collections, icons, subcollections, "
            "and asset bytes). Other formats export only the current collection."
        )
        self.qz_hint_label.setWordWrap(True)
        self.qz_hint_label.setStyleSheet("color: #666; font-size: 11px;")
        self.qz_hint_label.hide()
        format_layout.addWidget(self.qz_hint_label)

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
            1: ("Excel files (*.xlsx)", "xlsx"),
            2: ("JSON files (*.json)", "json"),
            3: ("SQLite Database (*.sqlite)", "sqlite"),
            4: ("Zip files (*.zip)", "zip"),
            5: ("Quartz Workspace (*.qz)", "qz"),
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
        if not self.export_path:
            QMessageBox.warning(self, "Error", "Please select a file path")
            return

        format_index = self.format_combo.currentIndex()
        formats = ["csv", "xlsx", "json", "db", "pack", "qz"]
        export_format = formats[format_index]

        if export_format == "qz":
            self._export_qz()
            return

        if not self.export_service:
            QMessageBox.warning(self, "Error", "No export service available")
            return

        # Determine scope
        if self.selected_radio and self.selected_radio.isChecked():
            record_ids = self.selected_record_ids
        else:
            record_ids = None

        # Perform export
        success = False
        try:
            if export_format == "csv":
                include_headers = self.include_headers_check.isChecked()
                delimiter = self.delimiter_combo.currentText()
                success = self.export_service.export_csv(
                    self.export_path, record_ids, include_headers, delimiter
                )
            elif export_format == "xlsx":
                include_headers = self.include_headers_check.isChecked()
                success = self.export_service.export_excel(
                    self.export_path, record_ids, include_headers
                )
            elif export_format == "json":
                success = self.export_service.export_json(self.export_path, record_ids)
            elif export_format == "db":
                success = self.export_service.export_db(self.export_path)
            elif export_format == "pack":
                success = self.export_service.export_pack(self.export_path)
        except Exception as e:  # noqa: BLE001
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

    def _export_qz(self):
        """Export the full workspace as a lossless .qz bundle."""
        if not self.workspace:
            QMessageBox.warning(self, "Error", "No workspace is open.")
            return
        try:
            from src.core.qz_packager import QzPackager

            QzPackager(self.workspace).pack(self.export_path)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export workspace:\n{e}")
            return

        QMessageBox.information(
            self,
            "Success",
            f"Workspace exported to:\n{self.export_path}\n\n"
            "This .qz bundle includes all collections, metadata, and asset bytes. "
            "Raw .sqlite / spreadsheet exports do not include images.",
        )
        self.accept()

    def _on_format_changed(self):
        """Handle format selection change - show/hide CSV options"""
        format_index = self.format_combo.currentIndex()
        is_qz = format_index == 5
        self.qz_hint_label.setVisible(is_qz)
        self.scope_group_box.setEnabled(not is_qz)
        # Show CSV options for CSV and Excel formats (index 0 and 1)
        self.csv_options_group.setVisible(format_index in [0, 1] and not is_qz)
        # Hide delimiter option for Excel (only show for CSV)
        delimiter_parent = self.delimiter_combo.parent()
        if delimiter_parent:
            delimiter_parent.setVisible(format_index == 0)

