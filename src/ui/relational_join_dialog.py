"""Dialog for creating relational joins between collections"""

from typing import Optional, List, Dict
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from src.core.collection_store import CollectionStore


class RelationalJoinDialog(QDialog):
    """Dialog for creating relationships between collections"""
    
    def __init__(self, parent=None, source_collection: str = None, workspace=None):
        super().__init__(parent)
        self.setWindowTitle("Create Relational Join")
        self.setMinimumWidth(500)
        
        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())
        
        self.source_collection = source_collection
        self.workspace = workspace
        self.relationship_data = {}
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(
            "Create a relationship between collections. This allows you to link records "
            "across collections using foreign keys."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        form_layout = QFormLayout()
        
        # Relationship name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Customer_Orders, Author_Books")
        form_layout.addRow("Relationship Name:", self.name_input)
        
        # Source collection (read-only if provided)
        if self.source_collection:
            source_label = QLabel(self.source_collection)
            source_label.setStyleSheet("font-weight: bold;")
            form_layout.addRow("Source Collection:", source_label)
        else:
            self.source_combo = QComboBox()
            if self.workspace:
                collections = self.workspace.list_collections()
                self.source_combo.addItems(collections)
            form_layout.addRow("Source Collection:", self.source_combo)
        
        # Source field
        self.source_field_combo = QComboBox()
        self.source_field_combo.setEditable(False)
        form_layout.addRow("Source Field:", self.source_field_combo)
        
        # Update source field options when source collection changes
        if not self.source_collection:
            self.source_combo.currentTextChanged.connect(self._update_source_fields)
        else:
            self._update_source_fields()
        
        # Target collection
        self.target_combo = QComboBox()
        if self.workspace:
            collections = self.workspace.list_collections()
            # Remove source collection from target list
            if self.source_collection:
                collections = [c for c in collections if c != self.source_collection]
            self.target_combo.addItems(collections)
        self.target_combo.currentTextChanged.connect(self._update_target_fields)
        form_layout.addRow("Target Collection:", self.target_combo)
        
        # Target field
        self.target_field_combo = QComboBox()
        self.target_field_combo.setEditable(False)
        form_layout.addRow("Target Field:", self.target_field_combo)
        
        # Relationship type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["one_to_one", "one_to_many", "many_to_many"])
        self.type_combo.setCurrentText("one_to_many")
        form_layout.addRow("Relationship Type:", self.type_combo)
        
        # Cascade delete
        self.cascade_check = QCheckBox("Cascade Delete")
        self.cascade_check.setToolTip(
            "If enabled, deleting a record in the source collection will also delete "
            "related records in the target collection"
        )
        form_layout.addRow("", self.cascade_check)
        
        layout.addLayout(form_layout)
        
        # Help text
        help_group = QGroupBox("Relationship Types")
        help_layout = QVBoxLayout()
        help_text = QLabel(
            "<b>one_to_one:</b> Each record in source matches exactly one record in target<br/>"
            "<b>one_to_many:</b> Each record in source can match multiple records in target<br/>"
            "<b>many_to_many:</b> Records in both collections can have multiple matches"
        )
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("Create Relationship")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._validate_and_accept)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
    
    def _update_source_fields(self):
        """Update source field combo when source collection changes"""
        self.source_field_combo.clear()
        
        source_name = self.source_collection or (self.source_combo.currentText() if hasattr(self, 'source_combo') else None)
        if not source_name or not self.workspace:
            return
        
        try:
            source_info = self.workspace.get_collection_info(source_name)
            if not source_info:
                return
            
            source_db = self.workspace.workspace_path / source_info.db_path
            source_store = CollectionStore(source_db)
            source_store.connect()
            
            fields = source_store.list_fields()
            for field in fields:
                self.source_field_combo.addItem(f"{field.get('alias', field.get('label', ''))} ({field['key']})", field['key'])
            
            source_store.close()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load fields: {str(e)}")
    
    def _update_target_fields(self):
        """Update target field combo when target collection changes"""
        self.target_field_combo.clear()
        
        target_name = self.target_combo.currentText()
        if not target_name or not self.workspace:
            return
        
        try:
            target_info = self.workspace.get_collection_info(target_name)
            if not target_info:
                return
            
            target_db = self.workspace.workspace_path / target_info.db_path
            target_store = CollectionStore(target_db)
            target_store.connect()
            
            fields = target_store.list_fields()
            for field in fields:
                field_label = field.get('alias', field.get('label', ''))
                self.target_field_combo.addItem(f"{field_label} ({field['key']})", field['key'])
            
            target_store.close()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load fields: {str(e)}")
    
    def _validate_and_accept(self):
        """Validate and accept"""
        # Get relationship name
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a relationship name")
            return
        
        # Get source collection
        source_collection = self.source_collection or (self.source_combo.currentText() if hasattr(self, 'source_combo') else None)
        if not source_collection:
            QMessageBox.warning(self, "Validation", "Please select a source collection")
            return
        
        # Get source field
        source_field_index = self.source_field_combo.currentIndex()
        if source_field_index < 0:
            QMessageBox.warning(self, "Validation", "Please select a source field")
            return
        source_field_key = self.source_field_combo.itemData(source_field_index)
        
        # Get target collection
        target_collection = self.target_combo.currentText()
        if not target_collection:
            QMessageBox.warning(self, "Validation", "Please select a target collection")
            return
        
        if target_collection == source_collection:
            QMessageBox.warning(self, "Validation", "Source and target collections must be different")
            return
        
        # Get target field
        target_field_index = self.target_field_combo.currentIndex()
        if target_field_index < 0:
            QMessageBox.warning(self, "Validation", "Please select a target field")
            return
        target_field_key = self.target_field_combo.itemData(target_field_index)
        
        # Get relationship type
        relationship_type = self.type_combo.currentText()
        
        # Get cascade delete
        cascade_delete = self.cascade_check.isChecked()
        
        self.relationship_data = {
            "name": name,
            "source_collection": source_collection,
            "source_field_key": source_field_key,
            "target_collection": target_collection,
            "target_field_key": target_field_key,
            "type": relationship_type,
            "cascade_delete": cascade_delete
        }
        
        self.accept()
    
    def get_relationship_data(self) -> Dict:
        """Get the relationship data"""
        return self.relationship_data

