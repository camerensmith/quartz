"""Dialog for creating a new collection with initial fields"""

from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt

from src.ui.styles import AppStyles


class NewCollectionDialog(QDialog):
    """Dialog for creating a new collection"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Collection")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.collection_name = ""
        self.key_prefix: Optional[str] = None
        self.fields: List[Dict] = []
        
        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Collection name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Collection Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Restaurants, Games, Books")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Key prefix (optional)
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("ID Prefix (Optional):"))
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("e.g., REST (will create IDs like REST_1, REST_2)")
        prefix_layout.addWidget(self.prefix_input)
        layout.addLayout(prefix_layout)
        
        prefix_help = QLabel("Leave empty to use auto-incrementing numbers (1, 2, 3...).\nPrefix helps avoid ID conflicts when merging collections.")
        prefix_help.setStyleSheet("color: #666; font-size: 11px;")
        prefix_help.setWordWrap(True)
        layout.addWidget(prefix_help)
        
        # Fields table
        layout.addWidget(QLabel("Fields:"))
        self.fields_table = QTableWidget()
        self.fields_table.setColumnCount(4)
        self.fields_table.setHorizontalHeaderLabels(["Alias", "Key", "Type", "Required"])
        self.fields_table.horizontalHeader().setStretchLastSection(True)
        self.fields_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Connect itemChanged to auto-generate keys
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
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("Create")
        ok_btn.clicked.connect(self._validate_and_accept)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
        
        # No default fields - user must click "Add Field" to add fields
    
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
    
    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle item change - auto-generate key when label changes"""
        # Only auto-generate key if label (column 0) changed
        if item.column() == 0:
            row = item.row()
            self._update_key_from_label(row)
    
    def _update_key_from_label(self, row: int):
        """Auto-generate field key from label"""
        label_item = self.fields_table.item(row, 0)
        key_item = self.fields_table.item(row, 1)
        
        if label_item and key_item:
            label = label_item.text()
            # Convert to snake_case
            key = label.lower().replace(" ", "").replace("-", "")
            # Remove special characters
            key = "".join(c for c in key if c.isalnum() or c == "_")
            if key and not key[0].isdigit():
                # Get existing fields from table to check for conflicts
                existing_fields = []
                for r in range(self.fields_table.rowCount()):
                    if r != row:  # Don't include current row
                        existing_key_item = self.fields_table.item(r, 1)
                        if existing_key_item and existing_key_item.text():
                            existing_fields.append({"key": existing_key_item.text()})
                
                # Generate unique key
                from src.ui.add_field_dialog import _generate_unique_field_key
                key = _generate_unique_field_key(key, existing_fields)
                key_item.setText(key)
    
    def _remove_field(self):
        """Remove selected field(s)"""
        rows = set()
        for item in self.fields_table.selectedItems():
            rows.add(item.row())
        
        for row in sorted(rows, reverse=True):
            self.fields_table.removeRow(row)
    
    def _validate_and_accept(self):
        """Validate input and accept"""
        # Validate collection name
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a collection name")
            return
        
        # Validate fields
        fields = []
        for row in range(self.fields_table.rowCount()):
            label_item = self.fields_table.item(row, 0)
            key_item = self.fields_table.item(row, 1)
            type_widget = self.fields_table.cellWidget(row, 2)
            required_item = self.fields_table.item(row, 3)
            
            if not label_item or not label_item.text().strip():
                continue  # Skip empty rows
            
            label = label_item.text().strip()
            key = key_item.text().strip() if key_item else ""
            
            if not key:
                QMessageBox.warning(self, "Validation", f"Field '{label}' needs a key. It will be auto-generated.")
                # Auto-generate
                key = label.lower().replace(" ", "").replace("-", "")
                key = "".join(c for c in key if c.isalnum() or c == "_")
            
            field_type = type_widget.currentText() if type_widget else "text"
            required = required_item.checkState() == Qt.Checked if required_item else False
            
            fields.append({
                "key": key,
                "type": field_type,
                "label": label,
                "required": required
            })
        
        # Fields are optional - collection can be created without fields
        # User can add fields later via Collection Properties
        
        # Get key prefix (optional)
        prefix = self.prefix_input.text().strip()
        if prefix:
            # Validate prefix - alphanumeric and underscores only
            if not all(c.isalnum() or c == '_' for c in prefix):
                QMessageBox.warning(self, "Validation", "ID prefix can only contain letters, numbers, and underscores")
                return
            if prefix[0].isdigit():
                QMessageBox.warning(self, "Validation", "ID prefix must start with a letter or underscore")
                return
        
        self.collection_name = name
        self.key_prefix = prefix if prefix else None
        self.fields = fields
        self.accept()
    
    def get_collection_name(self) -> str:
        """Get the collection name"""
        return self.collection_name
    
    def get_key_prefix(self) -> Optional[str]:
        """Get the key prefix"""
        return self.key_prefix
    
    def get_fields(self) -> List[Dict]:
        """Get the field definitions"""
        return self.fields
