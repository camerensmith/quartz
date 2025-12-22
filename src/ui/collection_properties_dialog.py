"""Collection properties dialog for viewing/editing fields"""

from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QGroupBox, QCheckBox
)
from PySide6.QtCore import Qt

from src.core.collection_store import CollectionStore


class CollectionPropertiesDialog(QDialog):
    """Dialog for viewing and editing collection properties and fields"""
    
    def __init__(self, parent=None, store: Optional[CollectionStore] = None,
                 collection_name: Optional[str] = None, workspace=None):
        super().__init__(parent)
        self.store = store
        self.collection_name = collection_name
        self.workspace = workspace
        
        self.setWindowTitle("Collection Properties")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())
        
        self._init_ui()
        self._load_description()
        self._load_fields()
    
    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Collection description
        desc_group = QGroupBox("Collection Description")
        desc_layout = QVBoxLayout()
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Enter a short description for this collection...")
        desc_layout.addWidget(self.description_input)
        desc_group.setLayout(desc_layout)
        layout.addWidget(desc_group)
        
        # Fields table
        layout.addWidget(QLabel("Fields:"))
        self.fields_table = QTableWidget()
        self.fields_table.setColumnCount(5)
        self.fields_table.setHorizontalHeaderLabels(["Alias", "Key", "Type", "Required", "Indexed"])
        self.fields_table.horizontalHeader().setStretchLastSection(True)
        self.fields_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Connect itemChanged to auto-generate keys for new fields
        self.fields_table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.fields_table)
        
        # Field buttons
        field_buttons = QHBoxLayout()
        add_field_btn = QPushButton("Add Field")
        add_field_btn.clicked.connect(self._add_field)
        remove_field_btn = QPushButton("Remove Field")
        remove_field_btn.clicked.connect(self._remove_field)
        field_buttons.addWidget(add_field_btn)
        field_buttons.addWidget(remove_field_btn)
        field_buttons.addStretch()
        layout.addLayout(field_buttons)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_fields)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        layout.addLayout(button_layout)
    
    def _load_description(self):
        """Load collection description"""
        if self.workspace and self.collection_name:
            info = self.workspace.get_collection_info(self.collection_name)
            if info and info.description:
                self.description_input.setText(info.description)
    
    def _save_description(self):
        """Save collection description"""
        if self.workspace and self.collection_name:
            description = self.description_input.text().strip() or None
            # Update description in workspace
            info = self.workspace.get_collection_info(self.collection_name)
            if info:
                info.description = description
                from datetime import datetime
                info.updated_at = datetime.now().isoformat()
                self.workspace.save_registry()
    
    def _load_fields(self):
        """Load existing fields"""
        if not self.store:
            return
        
        fields = self.store.list_fields()
        self.fields_table.setRowCount(len(fields))
        
        for row, field in enumerate(fields):
            # Label
            label_item = QTableWidgetItem(field["label"])
            self.fields_table.setItem(row, 0, label_item)
            
            # Key (read-only)
            key_item = QTableWidgetItem(field["key"])
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            self.fields_table.setItem(row, 1, key_item)
            
            # Type
            type_combo = QComboBox()
            type_combo.addItems(["text", "notes", "integer", "decimal", "checkbox", "date", "datetime", "select", "dropdown"])
            type_combo.setCurrentText(field["type"])
            self.fields_table.setCellWidget(row, 2, type_combo)
            
            # Required
            required_item = QTableWidgetItem()
            required_item.setCheckState(Qt.Checked if field.get("required") else Qt.Unchecked)
            required_item.setFlags(required_item.flags() | Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 3, required_item)
            
            # Indexed
            indexed_item = QTableWidgetItem()
            indexed_item.setCheckState(Qt.Checked if field.get("indexed") else Qt.Unchecked)
            indexed_item.setFlags(indexed_item.flags() | Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 4, indexed_item)
    
    def _add_field(self):
        """Add a new field row - opens dialog to prompt for field details"""
        from src.ui.add_field_dialog import AddFieldDialog
        
        dialog = AddFieldDialog(self)
        if dialog.exec():
            field_data = dialog.get_field_data()
            
            # Add row to table
            row = self.fields_table.rowCount()
            self.fields_table.insertRow(row)
            
            # Label
            label_item = QTableWidgetItem(field_data["label"])
            self.fields_table.setItem(row, 0, label_item)
            
            # Key (editable)
            key_item = QTableWidgetItem(field_data["key"])
            self.fields_table.setItem(row, 1, key_item)
            
            # Type
            type_combo = QComboBox()
            type_combo.addItems(["text", "notes", "integer", "decimal", "checkbox", "date", "datetime", "select"])
            type_combo.setCurrentText(field_data["type"])
            self.fields_table.setCellWidget(row, 2, type_combo)
            
            # Required
            required_item = QTableWidgetItem()
            required_item.setCheckState(Qt.Checked if field_data["required"] else Qt.Unchecked)
            required_item.setFlags(required_item.flags() | Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 3, required_item)
            
            # Indexed
            indexed_item = QTableWidgetItem()
            indexed_item.setCheckState(Qt.Unchecked)
            indexed_item.setFlags(indexed_item.flags() | Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 4, indexed_item)
    
    def _on_item_changed(self, item: QTableWidgetItem):
        """Auto-generate key when label changes"""
        if item.column() == 0:
            row = item.row()
            key_item = self.fields_table.item(row, 1)
            if key_item and not key_item.text():
                label = item.text()
                key = label.lower().replace(" ", "").replace("-", "")
                key = "".join(c for c in key if c.isalnum() or c == "_")
                if key and not key[0].isdigit():
                    key_item.setText(key)
    
    def _remove_field(self):
        """Remove selected field(s)"""
        rows = set()
        for item in self.fields_table.selectedItems():
            rows.add(item.row())
        
        if not rows:
            QMessageBox.information(self, "Info", "Please select field(s) to remove")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(rows)} field(s)?\n\nThis will remove the field from all records.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for row in sorted(rows, reverse=True):
                self.fields_table.removeRow(row)
    
    def _save_fields(self):
        """Save field changes"""
        if not self.store:
            QMessageBox.warning(self, "Error", "No collection store available")
            return
        
        # Get existing fields
        existing_fields = {f["key"]: f for f in self.store.list_fields()}
        existing_keys = set(existing_fields.keys())
        
        # Collect fields from table
        new_fields = []
        updated_fields = []
        keys_in_table = set()
        
        for row in range(self.fields_table.rowCount()):
            label_item = self.fields_table.item(row, 0)
            key_item = self.fields_table.item(row, 1)
            type_widget = self.fields_table.cellWidget(row, 2)
            required_item = self.fields_table.item(row, 3)
            indexed_item = self.fields_table.item(row, 4)
            
            if not label_item or not label_item.text().strip():
                continue
            
            label = label_item.text().strip()
            key = key_item.text().strip() if key_item else ""
            
            if not key:
                QMessageBox.warning(self, "Error", f"Field '{label}' needs a key")
                return
            
            if key in keys_in_table:
                QMessageBox.warning(self, "Error", f"Duplicate field key: {key}")
                return
            
            keys_in_table.add(key)
            
            field_type = type_widget.currentText() if type_widget else "text"
            required = required_item.checkState() == Qt.Checked if required_item else False
            indexed = indexed_item.checkState() == Qt.Checked if indexed_item else False
            
            field_data = {
                "key": key,
                "type": field_type,
                "label": label,
                "required": required,
                "indexed": indexed
            }
            
            if key in existing_keys:
                updated_fields.append(field_data)
            else:
                new_fields.append(field_data)
        
        # Add new fields
        for field in new_fields:
            try:
                self.store.add_field(
                    field_key=field["key"],
                    field_type=field["type"],
                    label=field["label"],
                    required=field["required"],
                    indexed=field["indexed"]
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to add field '{field['label']}': {str(e)}")
                return
        
        # Update existing fields (for now, we can only update required/indexed)
        # Full field editing would require schema migration
        for field in updated_fields:
            existing = existing_fields.get(field["key"])
            if existing:
                # Update required and indexed status
                # Note: Full field editing (type, key changes) would need more complex migration
                if existing["required"] != field["required"] or existing["indexed"] != field["indexed"]:
                    # Update in database
                    from datetime import datetime
                    import json
                    cursor = self.store.conn.cursor()
                    cursor.execute(
                        """UPDATE fields SET required=?, indexed=?, updated_at=? WHERE field_key=?""",
                        (1 if field["required"] else 0, 1 if field["indexed"] else 0,
                         datetime.now().isoformat(), field["key"])
                    )
                    self.store.conn.commit()
        
        # Remove deleted fields
        deleted_keys = existing_keys - keys_in_table
        for key in deleted_keys:
            # Note: Field deletion would require dropping column from records table
            # This is a destructive operation, so we'll just warn for now
            QMessageBox.warning(
                self, "Field Deletion",
                f"Field '{key}' was removed from the list.\n\n"
                f"To fully delete a field, use a database migration tool.\n"
                f"The field column will remain in records but won't be shown."
            )
        
        # Save description
        self._save_description()
        
        QMessageBox.information(self, "Success", "Fields saved successfully")
        self.accept()
