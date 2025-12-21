"""CSV import dialog with column mapping"""

from pathlib import Path
from typing import List, Dict, Optional
import csv

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QComboBox, QFileDialog, QMessageBox, QGroupBox, QCheckBox, QHeaderView
)
from PySide6.QtCore import Qt

import pandas as pd


class ImportDialog(QDialog):
    """Dialog for importing CSV files"""
    
    def __init__(self, parent=None, store=None, fields: Optional[List[Dict]] = None):
        super().__init__(parent)
        self.store = store
        self.fields = fields or []
        self.csv_data = []
        self.csv_headers = []
        self.file_path: Optional[Path] = None
        
        self.setWindowTitle("Import CSV")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # File selection
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("CSV File:"))
        self.file_label = QLabel("(not selected)")
        self.file_label.setStyleSheet("color: gray;")
        file_layout.addWidget(self.file_label)
        file_layout.addStretch()
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)
        
        # Options
        options_group = QGroupBox("Import Options")
        options_layout = QVBoxLayout()
        
        self.skip_first_row_check = QCheckBox("Skip first row (header)")
        self.skip_first_row_check.setChecked(True)
        options_layout.addWidget(self.skip_first_row_check)
        
        self.create_fields_check = QCheckBox("Create new fields for unmapped columns")
        self.create_fields_check.setChecked(False)
        options_layout.addWidget(self.create_fields_check)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Column mapping table
        layout.addWidget(QLabel("Column Mapping:"))
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(3)
        self.mapping_table.setHorizontalHeaderLabels(["CSV Column", "Map to Field", "Sample Data"])
        self.mapping_table.horizontalHeader().setStretchLastSection(True)
        self.mapping_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.mapping_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self._preview_import)
        button_layout.addWidget(preview_btn)
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        
        import_btn = QPushButton("Import")
        import_btn.setDefault(True)
        import_btn.clicked.connect(self._import_data)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(import_btn)
        layout.addLayout(button_layout)
    
    def _browse_file(self):
        """Browse for CSV file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if file_path:
            self.file_path = Path(file_path)
            self.file_label.setText(self.file_path.name)
            self.file_label.setStyleSheet("")
            self._load_csv()
    
    def _load_csv(self):
        """Load and parse CSV file"""
        if not self.file_path or not self.file_path.exists():
            return
        
        try:
            # Try pandas first (handles encoding better)
            try:
                df = pd.read_csv(self.file_path, nrows=100)  # Preview first 100 rows
                self.csv_headers = df.columns.tolist()
                self.csv_data = df.values.tolist()
            except:
                # Fallback to csv module
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    self.csv_headers = next(reader)
                    self.csv_data = []
                    for i, row in enumerate(reader):
                        if i >= 100:  # Limit preview
                            break
                        self.csv_data.append(row)
            
            self._populate_mapping_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load CSV file:\n{str(e)}")
    
    def _populate_mapping_table(self):
        """Populate column mapping table"""
        self.mapping_table.setRowCount(len(self.csv_headers))
        
        # Get field names
        field_names = ["(ignore)"] + [f["label"] for f in self.fields]
        
        for row, header in enumerate(self.csv_headers):
            # CSV Column
            header_item = QTableWidgetItem(header)
            header_item.setFlags(header_item.flags() & ~Qt.ItemIsEditable)
            self.mapping_table.setItem(row, 0, header_item)
            
            # Map to Field (combo)
            combo = QComboBox()
            combo.addItems(field_names)
            
            # Try to auto-match by name
            matching_field = next(
                (f for f in self.fields
                 if f["key"].lower() == header.lower() or f["label"].lower() == header.lower()),
                None
            )
            if matching_field:
                combo.setCurrentText(matching_field["label"])
            
            self.mapping_table.setCellWidget(row, 1, combo)
            
            # Sample data
            sample = ""
            if self.csv_data and row < len(self.csv_data[0]):
                sample = str(self.csv_data[0][row])[:50]
            
            sample_item = QTableWidgetItem(sample)
            sample_item.setFlags(sample_item.flags() & ~Qt.ItemIsEditable)
            self.mapping_table.setItem(row, 2, sample_item)
        
        self.mapping_table.resizeColumnsToContents()
    
    def _preview_import(self):
        """Preview import (show how many records will be imported)"""
        if not self.file_path:
            QMessageBox.warning(self, "Error", "Please select a CSV file first")
            return
        
        try:
            # Count total rows
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                row_count = sum(1 for _ in reader) - (1 if self.skip_first_row_check.isChecked() else 0)
            
            QMessageBox.information(
                self, "Import Preview",
                f"Will import approximately {row_count} records.\n\n"
                f"CSV has {len(self.csv_headers)} columns.\n"
                f"Mapping to {len(self.fields)} existing fields."
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to preview:\n{str(e)}")
    
    def _import_data(self):
        """Perform the import"""
        if not self.file_path or not self.store:
            QMessageBox.warning(self, "Error", "Please select a CSV file and ensure a collection is open")
            return
        
        # Build mapping
        mapping = {}
        new_fields_to_create = []
        
        for row in range(self.mapping_table.rowCount()):
            csv_col = self.mapping_table.item(row, 0).text()
            combo = self.mapping_table.cellWidget(row, 1)
            field_name = combo.currentText()
            
            if field_name == "(ignore)":
                # If "create new fields" is checked, still create fields for ignored columns
                if self.create_fields_check.isChecked():
                    # Create new field for this column
                    field_key = csv_col.lower().replace(" ", "").replace("-", "")
                    field_key = "".join(c for c in field_key if c.isalnum() or c == "_")
                    new_fields_to_create.append({
                        "key": field_key,
                        "label": csv_col,
                        "type": "text"  # Default to text
                    })
                    mapping[csv_col] = field_key
                # Otherwise, skip this column
                continue
            
            # Find field
            field = next((f for f in self.fields if f["label"] == field_name), None)
            if field:
                mapping[csv_col] = field["key"]
            elif self.create_fields_check.isChecked():
                # Create new field
                field_key = csv_col.lower().replace(" ", "").replace("-", "")
                field_key = "".join(c for c in field_key if c.isalnum() or c == "_")
                new_fields_to_create.append({
                    "key": field_key,
                    "label": csv_col,
                    "type": "text"  # Default to text
                })
                mapping[csv_col] = field_key
        
        # Validation: need at least one mapped column
        # If "create new fields" is checked, columns set to "(ignore)" should have been converted to new fields
        if not mapping:
            if self.create_fields_check.isChecked():
                # This shouldn't happen if create_fields is checked and CSV has columns
                QMessageBox.warning(self, "Error", "No columns to import. Please ensure your CSV file has columns.")
            else:
                QMessageBox.warning(self, "Error", "Please map at least one column to a field, or enable 'Create new fields for unmapped columns'")
            return
        
        # Create new fields if needed
        for field_def in new_fields_to_create:
            try:
                self.store.add_field(
                    field_key=field_def["key"],
                    field_type=field_def["type"],
                    label=field_def["label"],
                    required=False
                )
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Failed to create field {field_def['label']}:\n{str(e)}")
        
        # Import records
        try:
            imported = 0
            errors = []
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f) if self.skip_first_row_check.isChecked() else csv.reader(f)
                
                for row_idx, row in enumerate(reader):
                    try:
                        # Convert row to dict if needed
                        if isinstance(row, list):
                            row_dict = {self.csv_headers[i]: val for i, val in enumerate(row)}
                        else:
                            row_dict = row
                        
                        # Map to field keys
                        record_data = {}
                        for csv_col, field_key in mapping.items():
                            value = row_dict.get(csv_col, "")
                            if value:
                                record_data[field_key] = value
                        
                        # Add record
                        if record_data:
                            self.store.add_record(record_data)
                            imported += 1
                    except Exception as e:
                        errors.append(f"Row {row_idx+1}: {str(e)}")
                        if len(errors) >= 10:  # Limit error messages
                            break
            
            # Show results
            if errors:
                QMessageBox.warning(
                    self, "Import Complete with Errors",
                    f"Imported {imported} records.\n\n"
                    f"Errors: {len(errors)}\n" + "\n".join(errors[:5])
                )
            else:
                QMessageBox.information(
                    self, "Import Complete",
                    f"Successfully imported {imported} records."
                )
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import:\n{str(e)}")
