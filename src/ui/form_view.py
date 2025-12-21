"""Form view (data entry mode)"""

from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QMenu,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QPoint

from src.core.collection_store import CollectionStore


class FormView(QWidget):
    """Form view widget"""

    # Signal emitted when record is saved
    record_saved = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store: Optional[CollectionStore] = None
        self.fields: List[Dict] = []
        self.current_record_id: Optional[int] = None

        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        self.layout.addLayout(self.form_layout)
        self.layout.addStretch()

        self.field_widgets: Dict[str, QWidget] = {}

        # Auto-save on field change (with debouncing)
        self.save_timer = None
        self.loading_record = False  # Flag to prevent auto-save during loading
        self._readonly = False  # Track readonly state

        # Enable context menu for adding fields
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_form_context_menu)

    def set_collection(self, store: Optional[CollectionStore], fields: List[Dict]):
        """Set the collection and fields"""
        self.store = store
        self.fields = fields
        self.current_record_id = None
        if store is None:
            # Clear the form
            while self.form_layout.count():
                child = self.form_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self.field_widgets.clear()
        else:
            self._rebuild_form()

    def _rebuild_form(self):
        """Rebuild form widgets"""
        # Clear existing widgets
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.field_widgets.clear()

        # Create widgets for each field
        for field in self.fields:
            label = QLabel(field["label"])
            if field.get("required"):
                label.setText(f"{field['label']}*")

            # Create input widget based on field type
            widget = self._create_field_widget(field)
            self.field_widgets[field["key"]] = widget
            self.form_layout.addRow(label, widget)

    def _create_field_widget(self, field: Dict) -> QWidget:
        """Create a widget for a field type"""
        field_type = field["type"]

        if field_type == "text":
            widget = QLineEdit()
            widget.textChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "notes":
            widget = QTextEdit()
            widget.setMaximumHeight(150)
            widget.textChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "integer":
            widget = QSpinBox()
            widget.valueChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "decimal":
            widget = QDoubleSpinBox()
            widget.valueChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "checkbox":
            widget = QCheckBox()
            widget.stateChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "date":
            from PySide6.QtCore import QDate

            widget = QDateEdit()
            widget.setDate(QDate.currentDate())
            widget.dateChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "datetime":
            from PySide6.QtCore import QDateTime

            widget = QDateTimeEdit()
            widget.setDateTime(QDateTime.currentDateTime())
            widget.dateTimeChanged.connect(self._on_field_changed)
            return widget

        elif field_type in ("select", "single-select"):
            widget = QComboBox()
            options = field.get("options", [])
            if isinstance(options, list):
                widget.addItems([str(opt) for opt in options])
            widget.currentTextChanged.connect(self._on_field_changed)
            return widget

        else:
            # Default to text input
            return QLineEdit()

    def _get_widget_value(self, widget: QWidget, field: Dict):
        """Get value from a widget"""
        from PySide6.QtCore import QDate, QDateTime, Qt

        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText()
        elif isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QDoubleSpinBox):
            return widget.value()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QDateEdit):
            date = widget.date()
            return date.toString(Qt.DateFormat.ISODate)
        elif isinstance(widget, QDateTimeEdit):
            dt = widget.dateTime()
            return dt.toString(Qt.DateFormat.ISODate)
        elif isinstance(widget, QComboBox):
            return widget.currentText()

        return None

    def _on_field_changed(self):
        """Handle field value change (auto-save)"""
        if not self.store or self.loading_record or self._readonly:
            return

        # Debounce saves (wait 500ms after last change)
        from PySide6.QtCore import QTimer

        if self.save_timer:
            self.save_timer.stop()

        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_record)
        self.save_timer.start(500)  # 500ms delay

    def new_record(self):
        """Create a new empty record in the form"""
        self.current_record_id = None

        # Clear all field widgets
        for field in self.fields:
            field_key = field["key"]
            widget = self.field_widgets.get(field_key)
            if widget:
                # Set to default value or empty
                default_value = field.get("default_value")
                self._set_widget_value(
                    widget, field, default_value if default_value else None
                )

    def save_record(self):
        """Save current record (create new if no ID, update if ID exists)"""
        if not self.store or self._readonly:
            return

        data = {}
        validation_errors = {}

        # Collect data and validate
        from src.core.validation import FieldValidator

        for field in self.fields:
            field_key = field["key"]
            widget = self.field_widgets.get(field_key)
            if widget:
                value = self._get_widget_value(widget, field)
                data[field_key] = value

                # Validate
                result = FieldValidator.validate(field, value)
                if not result.valid:
                    validation_errors[field_key] = result.error_message

        # Show validation errors
        if validation_errors:
            self._show_validation_errors(validation_errors)
            return  # Don't save if invalid

        # Clear any previous error indicators
        self._clear_validation_errors()

        # Create new record or update existing
        if self.current_record_id:
            # Update existing record
            self.store.update_record(self.current_record_id, data)
            self.record_saved.emit(self.current_record_id)
        else:
            # Create new record
            record_id = self.store.add_record(data)
            self.current_record_id = record_id
            self.record_saved.emit(record_id)

    def _show_validation_errors(self, errors: Dict[str, str]):
        """Display validation errors under fields"""
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt

        # Remove existing error labels
        self._clear_validation_errors()

        # Add error labels and mark widgets as error
        for field_key, error_msg in errors.items():
            widget = self.field_widgets.get(field_key)
            if widget:
                # Mark widget as having error
                widget.setProperty("class", "error")
                widget.style().unpolish(widget)
                widget.style().polish(widget)

                # Find the row in form layout
                for i in range(self.form_layout.rowCount()):
                    item = self.form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                    if item and item.widget() == widget:
                        # Add error label
                        error_label = QLabel(error_msg)
                        error_label.setProperty("class", "error")
                        error_label.setWordWrap(True)
                        self.form_layout.addRow("", error_label)

                        # Store reference for later removal
                        if not hasattr(self, "error_labels"):
                            self.error_labels = []
                        self.error_labels.append((i + 1, error_label))
                        break

    def _clear_validation_errors(self):
        """Remove validation error labels"""
        if hasattr(self, "error_labels"):
            for row, label in self.error_labels:
                self.form_layout.removeRow(label)
                label.deleteLater()
            self.error_labels = []

        # Clear error styling from widgets
        for widget in self.field_widgets.values():
            widget.setProperty("class", "")
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def load_record(self, record_id: int):
        """Load a record into the form"""
        if not self.store:
            return

        record = self.store.get_record(record_id)
        if not record:
            return

        self.loading_record = True
        self.current_record_id = record_id

        try:
            # Populate field widgets
            for field in self.fields:
                field_key = field["key"]
                widget = self.field_widgets.get(field_key)
                if not widget:
                    continue

                value = record.get(field_key)
                self._set_widget_value(widget, field, value)
        finally:
            self.loading_record = False

    def _set_widget_value(self, widget: QWidget, field: Dict, value):
        """Set value in a widget"""
        from PySide6.QtCore import QDate, QDateTime, Qt

        if value is None:
            return

        # Set value (signals will fire but loading_record flag prevents auto-save)
        if isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(str(value))
        elif isinstance(widget, QSpinBox):
            try:
                widget.setValue(int(value))
            except (ValueError, TypeError):
                pass
        elif isinstance(widget, QDoubleSpinBox):
            try:
                widget.setValue(float(value))
            except (ValueError, TypeError):
                pass
        elif isinstance(widget, QCheckBox):
            widget.setChecked(
                bool(value) and str(value).lower() not in ("0", "false", "")
            )
        elif isinstance(widget, QDateEdit):
            try:
                from datetime import datetime

                date = datetime.fromisoformat(str(value))
                widget.setDate(QDate(date.year, date.month, date.day))
            except:
                pass
        elif isinstance(widget, QDateTimeEdit):
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(str(value))
                widget.setDateTime(QDateTime(dt))
            except:
                pass
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))

    def _show_form_context_menu(self, position: QPoint):
        """Show context menu for adding fields"""
        if not self.store:
            return

        menu = QMenu(self)
        add_field_action = menu.addAction("Add Field...")
        add_field_action.triggered.connect(self._add_field_from_form)
        menu.exec(self.mapToGlobal(position))

    def _add_field_from_form(self):
        """Open collection properties to add a field"""
        # Find main window through parent chain
        parent = self.parent()
        while parent and not hasattr(parent, "_show_collection_properties"):
            parent = parent.parent()

        if parent and hasattr(parent, "current_collection"):
            collection_name = parent.current_collection
            if collection_name:
                parent._show_collection_properties(collection_name)
                # Refresh fields after adding
                if parent.current_store:
                    self.fields = parent.current_store.list_fields()
                    self._rebuild_form()
                    parent.table_view.set_collection(parent.current_store, self.fields)
    
    def set_readonly(self, readonly: bool):
        """Set all form fields to readonly or editable"""
        self._readonly = readonly
        
        for widget in self.field_widgets.values():
            if isinstance(widget, (QLineEdit, QTextEdit)):
                widget.setReadOnly(readonly)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit)):
                widget.setReadOnly(readonly)
            elif isinstance(widget, QComboBox):
                widget.setEnabled(not readonly)
            elif isinstance(widget, QCheckBox):
                widget.setEnabled(not readonly)
