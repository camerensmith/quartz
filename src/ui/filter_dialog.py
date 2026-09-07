"""Filter creation dialog"""


from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.core.collection_store import ROW_TAG_NAME_KEY, CollectionStore


class FilterDialog(QDialog):
    """Dialog for creating filters"""

    def __init__(self, parent=None, store: CollectionStore | None = None):
        super().__init__(parent)
        self.store = store
        self.filter_result = None

        self.setWindowTitle("Add Filter")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)

        self._init_ui()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Filter type (field or text)
        type_group = QGroupBox("Filter Type")
        type_layout = QVBoxLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Field", "Text"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # Field selector (only shown for field type)
        self.field_group = QGroupBox("Field")
        field_layout = QVBoxLayout()
        self.field_combo = QComboBox()
        self.field_data = {}  # Store field data by key
        if self.store:
            self.field_combo.addItem("Row Tag", ROW_TAG_NAME_KEY)
            fields = self.store.list_fields()
            for f in fields:
                if f["key"] != "id":
                    field_label = f.get("alias", f.get("label", f["key"]))
                    self.field_combo.addItem(field_label, f["key"])  # Display label, store key
                    self.field_data[f["key"]] = f  # Store full field data
        self.field_combo.currentIndexChanged.connect(self._on_field_changed)
        field_layout.addWidget(self.field_combo)
        self.field_group.setLayout(field_layout)
        self.field_group.setVisible(True)  # Default to field
        layout.addWidget(self.field_group)

        # Operator
        operator_group = QGroupBox("Operator")
        operator_layout = QVBoxLayout()
        self.operator_combo = QComboBox()
        self.operator_combo.addItems([
            "=", "!=", "LIKE", "NOT LIKE", ">", "<", ">=", "<=", "IS", "IS NOT"
        ])
        operator_layout.addWidget(self.operator_combo)
        operator_group.setLayout(operator_layout)
        layout.addWidget(operator_group)

        # Value
        value_group = QGroupBox("Value")
        value_layout = QVBoxLayout()
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Enter filter value...")
        self.row_tag_value_combo = QComboBox()
        self.row_tag_value_combo.setVisible(False)
        value_layout.addWidget(self.value_input)
        value_layout.addWidget(self.row_tag_value_combo)
        value_group.setLayout(value_layout)
        layout.addWidget(value_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        add_btn = QPushButton("Add Filter")
        add_btn.setDefault(True)
        add_btn.clicked.connect(self._add_filter)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(add_btn)
        layout.addLayout(button_layout)
        self._on_field_changed()

    def _on_type_changed(self, text: str):
        """Handle filter type change"""
        self.field_group.setVisible(text == "Field")
        self._on_field_changed()

    def _on_field_changed(self):
        """Toggle the value editor based on the selected filter target."""
        is_row_tag_field = (
            self.type_combo.currentText() == "Field"
            and self.field_combo.currentData() == ROW_TAG_NAME_KEY
        )
        self.value_input.setVisible(not is_row_tag_field)
        self.row_tag_value_combo.setVisible(is_row_tag_field)
        if not is_row_tag_field or not self.store:
            return

        current_text = self.row_tag_value_combo.currentText()
        self.row_tag_value_combo.clear()
        for tag in self.store.list_row_tags():
            self.row_tag_value_combo.addItem(tag["name"], tag["id"])
        if current_text:
            index = self.row_tag_value_combo.findText(current_text)
            if index >= 0:
                self.row_tag_value_combo.setCurrentIndex(index)

    def _add_filter(self):
        """Add the filter"""
        filter_type = self.type_combo.currentText()
        operator = self.operator_combo.currentText()
        if filter_type == "Field" and self.field_combo.currentData() == ROW_TAG_NAME_KEY:
            value = self.row_tag_value_combo.currentText().strip()
        else:
            value = self.value_input.text().strip()

        if not value:
            return

        if filter_type == "Field":
            field_key = self.field_combo.currentData()  # Get the stored key
            field_label = self.field_combo.currentText()  # Get the displayed label
            if not field_key:
                return
            self.filter_result = {
                "field_or_text": field_key,  # Store key for filtering logic
                "field_label": field_label,  # Store label for display
                "operator": operator,
                "value": value
            }
        else:
            self.filter_result = {
                "field_or_text": "text",
                "operator": operator,
                "value": value
            }

        self.accept()

    def get_filter(self) -> dict | None:
        """Get the created filter"""
        return self.filter_result
