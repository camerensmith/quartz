"""Search results dialog with export and copy functionality"""

import csv
import json
from io import StringIO

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class SearchResultsDialog(QDialog):
    """Dialog for displaying search results with export and copy functionality"""

    def __init__(self, parent=None, results: list[dict] = None):
        super().__init__(parent)
        self.results = results or []

        self.setWindowTitle("Search Results")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)

        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())

        self._init_ui()
        self._display_results()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Results count
        self.results_label = QLabel("No results")
        layout.addWidget(self.results_label)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Collection", "Record ID", "Preview"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.results_table.itemDoubleClicked.connect(self._on_result_double_clicked)
        layout.addWidget(self.results_table)

        # Buttons
        button_layout = QHBoxLayout()

        # Copy selected to clipboard
        copy_selected_btn = QPushButton("Copy Selected to Clipboard")
        copy_selected_btn.clicked.connect(self._copy_selected_to_clipboard)
        button_layout.addWidget(copy_selected_btn)

        # Copy all to clipboard
        copy_all_btn = QPushButton("Copy All to Clipboard")
        copy_all_btn.clicked.connect(self._copy_all_to_clipboard)
        button_layout.addWidget(copy_all_btn)

        button_layout.addStretch()

        # Export selected
        export_selected_btn = QPushButton("Export Selected...")
        export_selected_btn.clicked.connect(self._export_selected)
        button_layout.addWidget(export_selected_btn)

        # Export all
        export_all_btn = QPushButton("Export All...")
        export_all_btn.clicked.connect(self._export_all)
        button_layout.addWidget(export_all_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "secondary")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _display_results(self):
        """Display search results in table"""
        self.results_table.setRowCount(len(self.results))

        for row, result in enumerate(self.results):
            collection = result["collection"]
            record = result["record"]
            record_id = record.get("id", "")

            # Collection name
            collection_item = QTableWidgetItem(collection)
            collection_item.setFlags(collection_item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, 0, collection_item)

            # Record ID
            id_item = QTableWidgetItem(str(record_id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, 1, id_item)

            # Preview (first few field values)
            preview_parts = []
            for key, value in list(record.items())[:3]:  # First 3 fields
                if key != "id" and value:
                    preview_parts.append(f"{key}: {str(value)[:30]}")
            preview = " | ".join(preview_parts) if preview_parts else "(empty record)"

            preview_item = QTableWidgetItem(preview)
            preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, 2, preview_item)

        self.results_table.resizeColumnsToContents()

        # Update results count
        count = len(self.results)
        collections_count = len({r['collection'] for r in self.results})
        self.results_label.setText(f"Found {count} result(s) across {collections_count} collection(s)")

    def _get_selected_results(self) -> list[dict]:
        """Get selected results"""
        selected_rows = set()
        for item in self.results_table.selectedItems():
            selected_rows.add(item.row())

        return [self.results[row] for row in sorted(selected_rows)]

    def _results_to_csv(self, results: list[dict]) -> str:
        """Convert results to CSV string"""
        if not results:
            return ""

        output = StringIO()

        # Get all unique field keys from all records
        all_fields = set()
        for result in results:
            record = result["record"]
            all_fields.update(record.keys())

        # Remove 'id' from fields and add it as first column
        all_fields.discard("id")
        field_order = ["collection", "id"] + sorted(all_fields)

        writer = csv.DictWriter(output, fieldnames=field_order, extrasaction='ignore')
        writer.writeheader()

        for result in results:
            row = {"collection": result["collection"]}
            row.update(result["record"])
            # Convert all values to strings
            row = {k: str(v) if v is not None else "" for k, v in row.items()}
            writer.writerow(row)

        return output.getvalue()

    def _results_to_json(self, results: list[dict]) -> str:
        """Convert results to JSON string"""
        return json.dumps(results, indent=2, default=str)

    def _copy_selected_to_clipboard(self):
        """Copy selected results to clipboard"""
        selected = self._get_selected_results()
        if not selected:
            QMessageBox.information(self, "Info", "Please select one or more results to copy")
            return

        # Format as CSV for clipboard
        csv_data = self._results_to_csv(selected)
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(csv_data)
        QMessageBox.information(self, "Copied", f"Copied {len(selected)} result(s) to clipboard")

    def _copy_all_to_clipboard(self):
        """Copy all results to clipboard"""
        if not self.results:
            QMessageBox.information(self, "Info", "No results to copy")
            return

        # Format as CSV for clipboard
        csv_data = self._results_to_csv(self.results)
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(csv_data)
        QMessageBox.information(self, "Copied", f"Copied {len(self.results)} result(s) to clipboard")

    def _export_selected(self):
        """Export selected results to file"""
        selected = self._get_selected_results()
        if not selected:
            QMessageBox.information(self, "Info", "Please select one or more results to export")
            return

        self._export_results(selected, "selected")

    def _export_all(self):
        """Export all results to file"""
        if not self.results:
            QMessageBox.information(self, "Info", "No results to export")
            return

        self._export_results(self.results, "all")

    def _export_results(self, results: list[dict], suffix: str):
        """Export results to file (CSV or JSON)"""
        file_path, file_type = QFileDialog.getSaveFileName(
            self,
            f"Export {suffix} results",
            f"search_results_{suffix}.csv",
            "CSV Files (*.csv);;JSON Files (*.json)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.json'):
                data = self._results_to_json(results)
            else:
                data = self._results_to_csv(results)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(data)

            QMessageBox.information(self, "Success", f"Exported {len(results)} result(s) to {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to export results:\n{str(e)}")

    def _on_result_double_clicked(self, item: QTableWidgetItem):
        """Handle double-click on result to open collection and record"""
        row = item.row()
        if row < len(self.results):
            result = self.results[row]
            collection_name = result["collection"]
            record_id = result["record"].get("id")

            # Call parent method to open this collection and record
            parent = self.parent()
            if parent and hasattr(parent, '_open_collection_and_record'):
                try:
                    parent._open_collection_and_record(collection_name, record_id)
                    self.accept()
                except Exception as e:
                    QMessageBox.warning(
                        self, "Error",
                        f"Failed to open collection and record:\n{str(e)}"
                    )

