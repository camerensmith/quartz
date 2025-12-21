"""Dialog for adding a new field with all options"""

from typing import Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QFileDialog, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon


class AddFieldDialog(QDialog):
    """Dialog for adding a new field with all options"""
    
    def __init__(self, parent=None, existing_fields=None):
        super().__init__(parent)
        self.setWindowTitle("Add Field")
        self.setMinimumWidth(400)
        
        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())
        
        self.existing_fields = existing_fields or []
        self.field_data = {}
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Show existing fields if provided
        if self.existing_fields:
            existing_group = QGroupBox("Existing Fields")
            existing_layout = QVBoxLayout()
            existing_text = ", ".join([f.get("alias", f.get("label", f["key"])) for f in self.existing_fields])
            existing_label = QLabel(existing_text)
            existing_label.setWordWrap(True)
            existing_layout.addWidget(existing_label)
            existing_group.setLayout(existing_layout)
            layout.addWidget(existing_group)
        
        # Alias (formerly Label)
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel("Alias:"))
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("Field alias (e.g., Name, Email)")
        self.label_input.textChanged.connect(self._on_label_changed)
        label_layout.addWidget(self.label_input)
        layout.addLayout(label_layout)
        
        # Key (editable)
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("Key:"))
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Field key (auto-generated from label)")
        key_layout.addWidget(self.key_input)
        layout.addLayout(key_layout)
        
        # Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["text", "notes", "integer", "decimal", "checkbox", "date", "datetime", "select"])
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)
        
        # Required
        self.required_check = QCheckBox("Required")
        layout.addWidget(self.required_check)
        
        # Image association
        image_group = QGroupBox("Image Association (Optional)")
        image_layout = QVBoxLayout()
        
        image_path_layout = QHBoxLayout()
        image_path_layout.addWidget(QLabel("Image:"))
        self.image_path_input = QLineEdit()
        self.image_path_input.setReadOnly(True)
        self.image_path_input.setPlaceholderText("No image selected")
        image_path_layout.addWidget(self.image_path_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_image)
        image_path_layout.addWidget(browse_btn)
        image_layout.addLayout(image_path_layout)
        
        image_group.setLayout(image_layout)
        layout.addWidget(image_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("Add Field")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._validate_and_accept)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
    
    def _on_label_changed(self, text: str):
        """Auto-generate key from label"""
        if not self.key_input.text():  # Only auto-generate if key is empty
            key = text.lower().replace(" ", "_").replace("-", "_")
            key = "".join(c for c in key if c.isalnum() or c == "_")
            if key and not key[0].isdigit():
                self.key_input.setText(key)
    
    def _browse_image(self):
        """Browse for image file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Image files (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*)"
        )
        if file_path:
            self.image_path_input.setText(file_path)
    
    def _validate_and_accept(self):
        """Validate and accept"""
        label = self.label_input.text().strip()
        if not label:
            QMessageBox.warning(self, "Validation", "Please enter a field alias")
            return
        
        key = self.key_input.text().strip()
        if not key:
            # Auto-generate from label
            key = label.lower().replace(" ", "_").replace("-", "_")
            key = "".join(c for c in key if c.isalnum() or c == "_")
            if not key or key[0].isdigit():
                key = f"field_{key}" if key else "field_1"
        
        # Validate key format
        if not key[0].isalpha() and key[0] != "_":
            QMessageBox.warning(self, "Validation", "Field key must start with a letter or underscore")
            return
        
        self.field_data = {
            "key": key,
            "label": label,
            "type": self.type_combo.currentText(),
            "required": self.required_check.isChecked(),
            "image_path": self.image_path_input.text().strip() or None
        }
        
        self.accept()
    
    def get_field_data(self) -> dict:
        """Get the field data"""
        return self.field_data

