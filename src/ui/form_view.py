"""Form view (data entry mode)"""


from typing import Any

from PySide6.QtCore import QDate, QDateTime, QEvent, QPoint, Qt, QTime, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.asset_store import AssetStore
from src.core.collection_store import CollectionStore
from src.ui.image_field import ImageFieldWidget

# Use Qt's minimum supported year as the blank-form sentinel for date editors.
EMPTY_FORM_DATE = QDate(1, 1, 1)
EMPTY_FORM_DATETIME = QDateTime(EMPTY_FORM_DATE, QTime(0, 0))


class FormView(QWidget):
    """Form view widget"""

    # Signal emitted when record is saved (object to support both int and str IDs)
    record_saved = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store: CollectionStore | None = None
        self.fields: list[dict] = []
        self.current_record_id: int | None = None
        self.field_widgets: dict[str, QWidget] = {}  # Initialize field_widgets dictionary
        self._main_window = None  # Cache reference to main window
        self._asset_store: AssetStore | None = None

        # Ordered list of widgets that participate in the form's tab cycle.
        # Populated by ``_rebuild_form`` and consumed by ``focusNextPrevChild``
        # so Tab/Shift+Tab cycle within the form instead of leaking out into
        # the rest of the main window.
        self._tab_chain: list[QWidget] = []

        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        self.layout.addLayout(self.form_layout)

        # Button bar for form actions (aligned left, under form fields)
        self.button_layout = QHBoxLayout()

        self.save_and_new_btn = QPushButton("Save and New")
        self.save_and_new_btn.clicked.connect(self._save_and_new)
        self.save_and_new_btn.setFocusPolicy(Qt.TabFocus)  # Ensure button is in tab order
        # Install event filter on button too
        self.save_and_new_btn.installEventFilter(self)
        self.button_layout.addWidget(self.save_and_new_btn)
        self.button_layout.addStretch()  # Push button to left, stretch on right

        self.layout.addLayout(self.button_layout)
        self.layout.addStretch()

        self.field_widgets: dict[str, QWidget] = {}

        self.loading_record = False  # Flag to prevent auto-save during loading
        self._readonly = False  # Track readonly state

        # Enable context menu for adding fields
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_form_context_menu)

        # Install event filter to catch right-clicks on child widgets
        self.installEventFilter(self)

        # Also override mousePressEvent to catch right-clicks anywhere on the form
        self.setMouseTracking(True)

    def set_collection(self, store: CollectionStore | None, fields: list[dict]):
        """Set the collection and fields"""
        self.store = store
        self.fields = fields
        self.current_record_id = None
        # Cache main window reference if not already cached
        if not self._main_window:
            self._find_main_window()

        # Resolve workspace-level asset store (for image fields). If the host
        # main window doesn't have one yet, fall back to None — image widgets
        # gracefully no-op until bound.
        if self._main_window and hasattr(self._main_window, "workspace") and self._main_window.workspace:
            self._asset_store = AssetStore(self._main_window.workspace.workspace_path)
        else:
            self._asset_store = None
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

        # Create widgets for each field and set up tab order chain
        first_widget = None
        previous_widget = None
        for field in self.fields:
            label = QLabel(field["label"])
            if field.get("required"):
                label.setText(f"{field['label']}*")

            # Create input widget based on field type
            widget = self._create_field_widget(field)
            self.field_widgets[field["key"]] = widget
            # Install event filter on child widgets to catch right-clicks
            widget.installEventFilter(self)
            # Also install event filter on label
            label.installEventFilter(self)
            self.form_layout.addRow(label, widget)

            # Set up tab order chain for all form fields
            if first_widget is None:
                first_widget = widget
            else:
                # Set tab order: previous widget -> current widget
                self.setTabOrder(previous_widget, widget)

            previous_widget = widget

        # Complete the tab order loop: last field -> button -> first field
        if hasattr(self, 'save_and_new_btn') and previous_widget:
            # After last form field, go to Save and New button
            self.setTabOrder(previous_widget, self.save_and_new_btn)
            if first_widget:
                # After button, go to first form field (completes the loop)
                self.setTabOrder(self.save_and_new_btn, first_widget)

        # Rebuild the explicit tab cycle used by ``focusNextPrevChild``. Order
        # matches the visual order of fields, with the Save and New button
        # appended at the end so the cycle is field1 → field2 → … → fieldN →
        # Save and New → field1.
        self._tab_chain = [
            self.field_widgets[f["key"]]
            for f in self.fields
            if f["key"] in self.field_widgets
        ]
        if hasattr(self, "save_and_new_btn"):
            self._tab_chain.append(self.save_and_new_btn)

    def _create_field_widget(self, field: dict) -> QWidget:
        """Create a widget for a field type"""
        field_type = field["type"]

        if field_type == "text":
            widget = QLineEdit()
            widget.setMaximumWidth(400)
            widget.textChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "notes":
            widget = QTextEdit()
            widget.setMaximumHeight(150)
            widget.setMaximumWidth(600)
            # Without this, Tab inside a notes field inserts a literal tab
            # character. Inside a form, users almost always want Tab to move
            # to the next field — they can still use Ctrl+Tab if they really
            # need a tab character.
            widget.setTabChangesFocus(True)
            widget.textChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "integer":
            widget = QSpinBox()
            widget.setMaximumWidth(150)
            widget.valueChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "decimal":
            widget = QDoubleSpinBox()
            widget.setMaximumWidth(150)
            widget.valueChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "checkbox":
            widget = QCheckBox()
            widget.stateChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "date":
            widget = QDateEdit()
            widget.setMinimumDate(EMPTY_FORM_DATE)
            widget.setSpecialValueText("")
            widget.setDate(widget.minimumDate())
            widget.setMaximumWidth(200)
            # Apply date format from config
            date_format = self._get_date_format()
            if date_format:
                widget.setDisplayFormat(date_format)
            widget.dateChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "datetime":
            widget = QDateTimeEdit()
            widget.setMinimumDateTime(EMPTY_FORM_DATETIME)
            widget.setSpecialValueText("")
            widget.setDateTime(widget.minimumDateTime())
            widget.setMaximumWidth(250)
            # Apply datetime format from config
            datetime_format = self._get_datetime_format()
            if datetime_format:
                widget.setDisplayFormat(datetime_format)
            widget.dateTimeChanged.connect(self._on_field_changed)
            return widget

        elif field_type == "image":
            widget = ImageFieldWidget()
            widget.bind_stores(self._asset_store, self.store)
            return widget

        elif field_type in ("select", "single-select"):
            widget = QComboBox()
            options = field.get("options", [])
            if isinstance(options, str):
                import json
                try:
                    options = json.loads(options)
                except Exception:
                    options = []
            if isinstance(options, list):
                widget.addItems([str(opt) for opt in options])
            widget.setMaximumWidth(300)
            # -1 keeps the form blank until the user explicitly chooses an option.
            widget.setCurrentIndex(-1)
            widget.currentTextChanged.connect(self._on_field_changed)
            return widget

        else:
            # Default to text input
            widget = QLineEdit()
            widget.setMaximumWidth(400)
            return widget

    def _get_widget_value(self, widget: QWidget, field: dict):
        """Get value from a widget"""
        from PySide6.QtCore import Qt

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
            if date == widget.minimumDate():
                return ""
            return date.toString(Qt.DateFormat.ISODate)
        elif isinstance(widget, QDateTimeEdit):
            dt = widget.dateTime()
            if dt == widget.minimumDateTime():
                return ""
            return dt.toString(Qt.DateFormat.ISODate)
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        elif isinstance(widget, ImageFieldWidget):
            return widget.value()

        return None

    def _on_field_changed(self):
        """Handle field changes while guarding against readonly and form-reset states."""
        if self.loading_record or self._readonly:
            return

    def new_record(self):
        """Create a new empty record in the form"""
        self.loading_record = True
        self.current_record_id = None
        self._clear_validation_errors()

        try:
            # Clear all field widgets
            for field in self.fields:
                field_key = field["key"]
                widget = self.field_widgets.get(field_key)
                if widget:
                    default_value = field.get("default_value")
                    self._set_widget_value(
                        widget, field, default_value if default_value else None
                    )
        finally:
            self.loading_record = False

    def _collect_form_data(self) -> tuple[dict[str, Any], dict[str, str]]:
        """Collect form data and return (field_data, validation_errors)."""
        data: dict[str, Any] = {}
        validation_errors: dict[str, str] = {}

        from src.core.validation import FieldValidator

        for field in self.fields:
            field_key = field["key"]
            widget = self.field_widgets.get(field_key)
            if widget:
                value = self._get_widget_value(widget, field)
                data[field_key] = value

                result = FieldValidator.validate(field, value)
                if not result.valid:
                    validation_errors[field_key] = result.error_message

        return data, validation_errors

    def save_record(self) -> int | None:
        """Save current form contents as a new record and return its ID, or None otherwise."""
        if not self.store or self._readonly:
            return None

        data, validation_errors = self._collect_form_data()

        # Show validation errors
        if validation_errors:
            self._show_validation_errors(validation_errors)
            return None

        # Clear any previous error indicators
        self._clear_validation_errors()

        record_id = self.store.add_record(data)

        # Track image references so .qz export and future GC know what's used.
        for field in self.fields:
            if field.get("type") != "image":
                continue
            ref = data.get(field["key"])
            if ref:
                AssetStore.track_ref(self.store, record_id, field["key"], ref)

        # Keep the form in new-entry mode so form view never edits committed records.
        self.current_record_id = None
        self.record_saved.emit(record_id)
        return record_id

    def _save_and_new(self):
        """Save current record and create a new empty form"""
        if not self.store or self._readonly:
            return

        # Clear focus from currently focused widget to ensure any pending edits are committed
        # Widget values are read directly, so no need to process events
        focused_widget = QApplication.focusWidget()
        if focused_widget:
            focused_widget.clearFocus()

        saved_record_id = self.save_record()
        if saved_record_id is None:
            return

        # Now create a new empty form
        self.new_record()

        # Show "Record added" notification in the status bar
        main_window = self._find_main_window()
        if main_window:
            try:
                main_window.statusBar().showMessage("Record added", 3000)
            except AttributeError:
                pass

        # Move focus back to the top of the form so the user can immediately
        # start typing the next record. This is the whole point of the
        # "Save and New" button — fast successive entry.
        self._focus_first_field()

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002 (Qt API name)
        """Keep Tab / Shift+Tab navigation cycling within the form.

        Without this override, Qt's focus chain is global: pressing Tab on the
        last form widget walks out into the search bar, sidebar, toolbar, etc.
        ``setTabOrder`` is only a hint about *relative* ordering and does not
        close the cycle.

        ``focusNextPrevChild`` is consulted by Qt before falling back to the
        global focus chain, so by handling it here we get a self-contained
        Tab cycle of: field1 → field2 → … → fieldN → Save and New → field1.
        Sub-widget cases (e.g. the QLineEdit nested inside a QSpinBox) are
        handled via ``isAncestorOf`` so the chain still works when focus is
        deep inside a composite editor.
        """
        chain = self._tab_chain
        if not chain:
            return super().focusNextPrevChild(next)

        current = self.focusWidget()
        if current is None:
            return super().focusNextPrevChild(next)

        target_idx: int | None = None
        for i, widget in enumerate(chain):
            try:
                if widget is current or widget.isAncestorOf(current):
                    target_idx = i
                    break
            except RuntimeError:
                # Widget was deleted underneath us (collection switch, etc.)
                continue

        if target_idx is None:
            return super().focusNextPrevChild(next)

        delta = 1 if next else -1
        next_idx = (target_idx + delta) % len(chain)
        chain[next_idx].setFocus(Qt.TabFocusReason)
        return True

    def _focus_first_field(self):
        """Move focus to the first widget in the form's tab cycle.

        Used after ``Save and New`` so the user can keep typing without
        reaching for the mouse. Falls back gracefully if the form has no
        fields yet (e.g. a brand-new collection).
        """
        if not self._tab_chain:
            return
        first = self._tab_chain[0]
        first.setFocus(Qt.TabFocusReason)
        # For text-style editors a fresh blank field is what we want; for
        # spin/double-spin editors selectAll lets the user overtype the
        # default value (typically 0) without backspacing first.
        if isinstance(first, (QSpinBox, QDoubleSpinBox)):
            first.selectAll()

    def _show_validation_errors(self, errors: dict[str, str]):
        """Display validation errors under fields"""
        from PySide6.QtWidgets import QLabel

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
            for _row, label in self.error_labels:
                try:
                    # Check if label still exists before trying to remove it
                    if label and label.parent():
                        self.form_layout.removeRow(label)
                        # removeRow might delete the widget, so check before deleteLater
                        if label.parent():
                            label.deleteLater()
                except RuntimeError:
                    # Label was already deleted, ignore
                    pass
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

    def _set_widget_value(self, widget: QWidget, field: dict, value):
        """Set value in a widget"""
        from PySide6.QtCore import QDate, QDateTime

        if value is None:
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QTextEdit):
                widget.clear()
            elif isinstance(widget, QSpinBox):
                widget.setValue(widget.minimum())
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(widget.minimum())
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)
            elif isinstance(widget, QDateEdit):
                widget.setDate(widget.minimumDate())
            elif isinstance(widget, QDateTimeEdit):
                widget.setDateTime(widget.minimumDateTime())
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(-1)
            elif isinstance(widget, ImageFieldWidget):
                widget.set_value(None)
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
            except Exception:
                pass
        elif isinstance(widget, QDateTimeEdit):
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(str(value))
                widget.setDateTime(QDateTime(dt))
            except Exception:
                pass
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))
        elif isinstance(widget, ImageFieldWidget):
            widget.set_value(str(value) if value else None)

    def _show_form_context_menu(self, position: QPoint):
        """Show context menu for adding fields"""
        # Allow context menu even if no collection is selected (for future use)
        # But check if we have a store to enable the action
        menu = QMenu(self)
        add_field_action = menu.addAction("Add Field...")
        add_field_action.setEnabled(self.store is not None)  # Enable only if collection is selected
        add_field_action.triggered.connect(self._add_field_from_form)
        menu.exec(self.mapToGlobal(position))

    def _find_main_window(self):
        """Find and cache reference to main window through parent chain"""
        if self._main_window:
            return self._main_window

        parent = self.parent()
        while parent:
            if hasattr(parent, "_add_field") and hasattr(parent, "current_store"):
                # Found main window
                self._main_window = parent
                return parent
            if hasattr(parent, 'parent'):
                parent = parent.parent()
            else:
                break

        return None

    def mousePressEvent(self, event):
        """Override to catch right-clicks anywhere on the form (including empty areas)"""
        if event.button() == Qt.RightButton:
            self._show_form_context_menu(event.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        """Event filter to catch right-clicks on child widgets"""
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                # Convert position to FormView coordinates
                if obj != self:
                    # For child widgets, map to global then to FormView
                    global_pos = obj.mapToGlobal(event.pos())
                    local_pos = self.mapFromGlobal(global_pos)
                else:
                    local_pos = event.pos()
                # Show context menu at mouse position
                self._show_form_context_menu(local_pos)
                return True  # Event handled
        return super().eventFilter(obj, event)

    def _add_field_from_form(self):
        """Open Add Field dialog directly"""
        # Find main window if not cached
        if not self._main_window:
            self._find_main_window()

        if self._main_window and hasattr(self._main_window, "_add_field"):
            # Call the main window's _add_field method which opens the Add Field dialog
            self._main_window._add_field()
        else:
            # If we couldn't find it, show an error
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Could not find main window. Please select a collection first.")

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
            elif isinstance(widget, ImageFieldWidget):
                widget.set_readonly(readonly)
