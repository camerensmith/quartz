"""Dialog for adding a new field with all options"""


from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


def _generate_unique_field_key(base_key: str, existing_fields: list) -> str:
    """
    Generate a unique field key by appending characters if needed.

    Args:
        base_key: The base key to start with (e.g., "r")
        existing_fields: List of existing field dicts with "key" attribute

    Returns:
        A unique key (e.g., "r", "re", "ra", "r1", etc.)
    """
    existing_keys = {f["key"] for f in existing_fields} if existing_fields else set()

    # If base key is unique, return it
    if base_key not in existing_keys:
        return base_key

    # Try appending characters from the original label
    # First, try single characters (a-z, 0-9)
    for char in "abcdefghijklmnopqrstuvwxyz0123456789":
        candidate = base_key + char
        if candidate not in existing_keys:
            return candidate

    # If still not unique, try two characters
    for char1 in "abcdefghijklmnopqrstuvwxyz0123456789":
        for char2 in "abcdefghijklmnopqrstuvwxyz0123456789":
            candidate = base_key + char1 + char2
            if candidate not in existing_keys:
                return candidate

    # Last resort: append number
    counter = 1
    while True:
        candidate = f"{base_key}{counter}"
        if candidate not in existing_keys:
            return candidate
        counter += 1
        if counter > 1000:  # Safety limit
            break

    # Should never reach here, but fallback
    return f"{base_key}_auto"


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

        # Key (read-only, auto-generated)
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("Key:"))
        self.key_input = QLineEdit()
        self.key_input.setReadOnly(True)
        self.key_input.setPlaceholderText("Auto-generated from alias")
        self.key_input.setStyleSheet("background-color: #f5f5f5; color: #666;")
        key_layout.addWidget(self.key_input)
        layout.addLayout(key_layout)

        # Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "text",
            "notes",
            "integer",
            "decimal",
            "checkbox",
            "date",
            "datetime",
            "select",
            "image",
        ])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        self.image_type_hint = QLabel(
            "Cells store an asset:sha256:<hex> reference. Image bytes are kept "
            "in the workspace and only travel with .qz exports — CSV / Excel / "
            "raw .sqlite exports include the reference, not the picture."
        )
        self.image_type_hint.setWordWrap(True)
        self.image_type_hint.setStyleSheet("color: #666; font-size: 11px;")
        self.image_type_hint.hide()
        layout.addWidget(self.image_type_hint)

        # Options (for select type)
        self.options_group = QGroupBox("Select Options")
        options_layout = QVBoxLayout()
        options_layout.addWidget(QLabel("Add options for the dropdown:"))

        # Scroll area for options list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(200)
        scroll_area.setMinimumHeight(100)

        self.options_widget = QWidget()
        self.options_list_layout = QVBoxLayout(self.options_widget)
        self.options_list_layout.setContentsMargins(0, 0, 0, 0)
        self.options_list_layout.setSpacing(5)

        scroll_area.setWidget(self.options_widget)
        options_layout.addWidget(scroll_area)

        self.options_group.setLayout(options_layout)
        self.options_group.setVisible(False)  # Hidden by default
        layout.addWidget(self.options_group)

        # Store option input widgets and their layouts
        self.option_inputs: list = []
        self.option_layouts: list = []  # Store layouts for easy removal

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
                # Make key unique if existing fields are provided
                if self.existing_fields:
                    key = _generate_unique_field_key(key, self.existing_fields)
                self.key_input.setText(key)

    def _on_type_changed(self, field_type: str):
        """Show/hide options input based on field type"""
        if field_type == "select":
            self.options_group.setVisible(True)
            # Initialize with 2 empty options if none exist
            if len(self.option_inputs) == 0:
                self._add_option()
                self._add_option()
        else:
            self.options_group.setVisible(False)

        # Image field has its own hint about export behavior
        if hasattr(self, "image_type_hint"):
            self.image_type_hint.setVisible(field_type == "image")

    def _add_option(self, initial_value: str = ""):
        """Add a new option input row"""
        option_layout = QHBoxLayout()

        option_input = QLineEdit()
        option_input.setPlaceholderText(f"Option {len(self.option_inputs) + 1}")
        if initial_value:
            option_input.setText(initial_value)
        option_layout.addWidget(option_input)

        add_btn = QPushButton("+")
        add_btn.setMaximumWidth(35)
        add_btn.setMaximumHeight(30)
        add_btn.setMinimumWidth(35)
        add_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        add_btn.clicked.connect(lambda: self._add_option())
        option_layout.addWidget(add_btn)

        remove_btn = QPushButton("−")
        remove_btn.setMaximumWidth(35)
        remove_btn.setMaximumHeight(30)
        remove_btn.setMinimumWidth(35)
        remove_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        remove_btn.clicked.connect(lambda: self._remove_option(option_layout))
        # Hide remove button if only one option
        remove_btn.setVisible(len(self.option_inputs) > 0)
        option_layout.addWidget(remove_btn)

        self.options_list_layout.addLayout(option_layout)
        self.option_inputs.append(option_input)
        self.option_layouts.append(option_layout)

        # Update remove buttons visibility
        self._update_remove_buttons()

    def _remove_option(self, option_layout: QHBoxLayout):
        """Remove an option input row"""
        if len(self.option_inputs) <= 1:
            return  # Keep at least one option

        # Find the index
        try:
            index = self.option_layouts.index(option_layout)

            # Remove widgets from layout
            while option_layout.count():
                child = option_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Remove from lists
            self.options_list_layout.removeItem(option_layout)
            self.option_inputs.pop(index)
            self.option_layouts.pop(index)

            # Update remove buttons visibility
            self._update_remove_buttons()
        except ValueError:
            pass  # Layout not found

    def _update_remove_buttons(self):
        """Update visibility of remove buttons based on option count"""
        show_remove = len(self.option_inputs) > 1
        for layout in self.option_layouts:
            # Remove button is the 3rd widget (index 2)
            if layout.count() >= 3:
                remove_btn = layout.itemAt(2).widget()
                if remove_btn and isinstance(remove_btn, QPushButton):
                    remove_btn.setVisible(show_remove)

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

        # Make key unique if existing fields are provided
        if self.existing_fields:
            key = _generate_unique_field_key(key, self.existing_fields)
            # Update the key input to show the unique key
            self.key_input.setText(key)

        # Validate key format
        if not key[0].isalpha() and key[0] != "_":
            QMessageBox.warning(self, "Validation", "Field key must start with a letter or underscore")
            return

        field_type = self.type_combo.currentText()

        # Parse options for select type
        options = []
        if field_type == "select":
            # Get options from input widgets
            for option_input in self.option_inputs:
                option_text = option_input.text().strip()
                if option_text:
                    options.append(option_text)

            if not options:
                QMessageBox.warning(self, "Validation", "Please add at least one option for the Select field")
                return

        self.field_data = {
            "key": key,
            "label": label,
            "type": field_type,
            "required": self.required_check.isChecked(),
            "image_path": self.image_path_input.text().strip() or None,
            "options": options if options else None  # Only include if there are options
        }

        self.accept()

    def get_field_data(self) -> dict:
        """Get the field data"""
        return self.field_data

