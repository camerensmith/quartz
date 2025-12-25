"""Collection properties dialog for viewing/editing fields"""

from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QGroupBox, QCheckBox, QWidget
)
from PySide6.QtCore import Qt

from src.core.collection_store import CollectionStore


class ReorderableFieldsTable(QTableWidget):
    """Custom QTableWidget with up/down buttons for reordering rows"""
    
    def __init__(self, parent=None):
        super().__init__(parent)


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
        self.fields_table = ReorderableFieldsTable()
        self.fields_table.setColumnCount(6)  # Added column for up/down buttons
        self.fields_table.setHorizontalHeaderLabels(["", "Alias", "Key", "Type", "Required", "Indexed"])
        self.fields_table.horizontalHeader().setStretchLastSection(True)
        self.fields_table.setSelectionBehavior(QTableWidget.SelectRows)
        # Set first column width for buttons
        self.fields_table.setColumnWidth(0, 45)
        
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
        # Add help text about reordering
        help_label = QLabel("💡 Tip: Use ↑ ↓ buttons to reorder fields")
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        field_buttons.addWidget(help_label)
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
            # Create up/down buttons using helper method
            self._create_move_buttons(row)
            
            # Label (column 1)
            label_item = QTableWidgetItem(field["label"])
            self.fields_table.setItem(row, 1, label_item)
            
            # Key (read-only) (column 2)
            key_item = QTableWidgetItem(field["key"])
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable & ~Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 2, key_item)
            
            # Type (column 3)
            type_combo = QComboBox()
            type_combo.addItems(["text", "notes", "integer", "decimal", "checkbox", "date", "datetime", "select"])
            type_combo.setCurrentText(field["type"])
            self.fields_table.setCellWidget(row, 3, type_combo)
            
            # Required (column 4)
            required_item = QTableWidgetItem()
            required_item.setCheckState(Qt.Checked if field.get("required") else Qt.Unchecked)
            # Only allow checking, not editing text
            required_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 4, required_item)
            
            # Indexed (column 5)
            indexed_item = QTableWidgetItem()
            indexed_item.setCheckState(Qt.Checked if field.get("indexed") else Qt.Unchecked)
            # Only allow checking, not editing text
            indexed_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 5, indexed_item)
    
    def _add_field(self):
        """Add a new field row - opens dialog to prompt for field details"""
        from src.ui.add_field_dialog import AddFieldDialog
        
        dialog = AddFieldDialog(self)
        if dialog.exec():
            field_data = dialog.get_field_data()
            
            # Add row to table
            row = self.fields_table.rowCount()
            self.fields_table.insertRow(row)
            
            # Create up/down buttons using helper method
            self._create_move_buttons(row)
            
            # Label (column 1)
            label_item = QTableWidgetItem(field_data["label"])
            self.fields_table.setItem(row, 1, label_item)
            
            # Key (editable) (column 2)
            key_item = QTableWidgetItem(field_data["key"])
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 2, key_item)
            
            # Type (column 3)
            type_combo = QComboBox()
            type_combo.addItems(["text", "notes", "integer", "decimal", "checkbox", "date", "datetime", "select"])
            type_combo.setCurrentText(field_data["type"])
            self.fields_table.setCellWidget(row, 3, type_combo)
            
            # Required (column 4)
            required_item = QTableWidgetItem()
            required_item.setCheckState(Qt.Checked if field_data["required"] else Qt.Unchecked)
            # Only allow checking, not editing text
            required_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 4, required_item)
            
            # Indexed (column 5)
            indexed_item = QTableWidgetItem()
            indexed_item.setCheckState(Qt.Checked)  # Default to indexed
            # Only allow checking, not editing text
            indexed_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            self.fields_table.setItem(row, 5, indexed_item)
    
    def _move_field_up(self, row: int):
        """Move a field up one position"""
        if row <= 0:
            return
        self._swap_rows(row, row - 1)
        self._update_move_buttons()
    
    def _move_field_down(self, row: int):
        """Move a field down one position"""
        if row >= self.fields_table.rowCount() - 1:
            return
        self._swap_rows(row, row + 1)
        self._update_move_buttons()
    
    def _swap_rows(self, row1: int, row2: int):
        """Swap two rows in the table"""
        # Store all data from both rows
        row1_data = {}
        row2_data = {}
        
        for col in range(self.fields_table.columnCount()):
            # Store items
            item1 = self.fields_table.item(row1, col)
            item2 = self.fields_table.item(row2, col)
            if item1:
                row1_data[col] = QTableWidgetItem(item1.text())
                row1_data[col].setFlags(item1.flags())
                if item1.checkState() is not None:
                    row1_data[col].setCheckState(item1.checkState())
            if item2:
                row2_data[col] = QTableWidgetItem(item2.text())
                row2_data[col].setFlags(item2.flags())
                if item2.checkState() is not None:
                    row2_data[col].setCheckState(item2.checkState())
            
            # Store widgets
            widget1 = self.fields_table.cellWidget(row1, col)
            widget2 = self.fields_table.cellWidget(row2, col)
            if widget1:
                if isinstance(widget1, QComboBox):
                    row1_data[f'widget_{col}'] = {
                        'type': 'combo',
                        'items': [widget1.itemText(i) for i in range(widget1.count())],
                        'current': widget1.currentText()
                    }
                elif isinstance(widget1, QWidget) and col == 0:
                    # For button widgets in column 0, we'll recreate them
                    # Don't store the widget, we'll recreate it with correct row references
                    pass
            if widget2:
                if isinstance(widget2, QComboBox):
                    row2_data[f'widget_{col}'] = {
                        'type': 'combo',
                        'items': [widget2.itemText(i) for i in range(widget2.count())],
                        'current': widget2.currentText()
                    }
                elif isinstance(widget2, QWidget) and col == 0:
                    # For button widgets in column 0, we'll recreate them
                    pass
        
        # Clear both rows
        for col in range(self.fields_table.columnCount()):
            self.fields_table.setItem(row1, col, None)
            self.fields_table.setItem(row2, col, None)
            self.fields_table.setCellWidget(row1, col, None)
            self.fields_table.setCellWidget(row2, col, None)
        
        # Restore swapped data
        for col, item in row1_data.items():
            if isinstance(col, int):
                self.fields_table.setItem(row2, col, item)
        for col, item in row2_data.items():
            if isinstance(col, int):
                self.fields_table.setItem(row1, col, item)
        
        # Restore widgets
        for key, widget_data in row1_data.items():
            if isinstance(key, str) and key.startswith('widget_'):
                col = int(key.split('_')[1])
                if widget_data['type'] == 'combo':
                    combo = QComboBox()
                    combo.addItems(widget_data['items'])
                    combo.setCurrentText(widget_data['current'])
                    self.fields_table.setCellWidget(row2, col, combo)
        
        for key, widget_data in row2_data.items():
            if isinstance(key, str) and key.startswith('widget_'):
                col = int(key.split('_')[1])
                if widget_data['type'] == 'combo':
                    combo = QComboBox()
                    combo.addItems(widget_data['items'])
                    combo.setCurrentText(widget_data['current'])
                    self.fields_table.setCellWidget(row1, col, combo)
        
        # Recreate button widgets with correct row references
        self._create_move_buttons(row2)  # row1 moved to row2
        self._create_move_buttons(row1)  # row2 moved to row1
        
        # Update button connections
        self._update_move_buttons()
    
    def _create_move_buttons(self, row: int):
        """Create up/down buttons for a specific row"""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        
        up_btn = QPushButton("⬆")
        up_btn.setFlat(True)
        up_btn.setStyleSheet("QPushButton { border: none; background: transparent; padding: 2px; } QPushButton:hover { background: rgba(255, 255, 255, 0.1); }")
        up_btn.setEnabled(row > 0)
        up_btn.clicked.connect(lambda checked, r=row: self._move_field_up(r))
        
        down_btn = QPushButton("⬇")
        down_btn.setFlat(True)
        down_btn.setStyleSheet("QPushButton { border: none; background: transparent; padding: 2px; } QPushButton:hover { background: rgba(255, 255, 255, 0.1); }")
        down_btn.setEnabled(row < self.fields_table.rowCount() - 1)
        down_btn.clicked.connect(lambda checked, r=row: self._move_field_down(r))
        
        button_layout.addWidget(up_btn)
        button_layout.addWidget(down_btn)
        self.fields_table.setCellWidget(row, 0, button_widget)
    
    def _update_move_buttons(self):
        """Update the enabled state of up/down buttons"""
        for row in range(self.fields_table.rowCount()):
            button_widget = self.fields_table.cellWidget(row, 0)
            if button_widget:
                layout = button_widget.layout()
                if layout and layout.count() >= 2:
                    up_btn = layout.itemAt(0).widget()
                    down_btn = layout.itemAt(1).widget()
                    if up_btn:
                        up_btn.setEnabled(row > 0)
                    if down_btn:
                        down_btn.setEnabled(row < self.fields_table.rowCount() - 1)
    
    def _on_item_changed(self, item: QTableWidgetItem):
        """Auto-generate key when label changes"""
        if item.column() == 1:  # Column 1 = Label
            row = item.row()
            key_item = self.fields_table.item(row, 2)  # Column 2 = Key
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
        
        # Collect fields from table (in order)
        new_fields = []
        updated_fields = []
        keys_in_table = set()
        field_keys_in_order = []  # Track order for reordering
        
        for row in range(self.fields_table.rowCount()):
            label_item = self.fields_table.item(row, 1)  # Column 1 = Label
            key_item = self.fields_table.item(row, 2)    # Column 2 = Key
            type_widget = self.fields_table.cellWidget(row, 3)  # Column 3 = Type
            required_item = self.fields_table.item(row, 4)  # Column 4 = Required
            indexed_item = self.fields_table.item(row, 5)  # Column 5 = Indexed
            
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
            field_keys_in_order.append(key)  # Track order
            
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
        
        # Add new fields first (they need to exist before we can reorder)
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
        
        # Save field order based on table row order (after all fields are saved)
        if field_keys_in_order:
            try:
                self.store.reorder_fields(field_keys_in_order)
            except Exception as e:
                # If reordering fails, continue anyway (might be old schema without field_order column)
                pass
        
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
            try:
                # Get field label for better error messages
                field_info = existing_fields.get(key, {})
                field_label = field_info.get("alias", field_info.get("label", key))
                
                # Actually delete the field from the collection
                self.store.remove_field(key)
            except Exception as e:
                QMessageBox.warning(
                    self, "Error",
                    f"Failed to delete field '{key}': {str(e)}"
                )
                return
        
        # Save description
        self._save_description()
        
        QMessageBox.information(self, "Success", "Fields saved successfully")
        self.accept()
