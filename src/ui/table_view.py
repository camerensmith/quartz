"""Table view (spreadsheet-like)"""

from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QTableView,
    QAbstractItemView,
    QMessageBox,
    QToolTip,
    QMenu,
    QStyledItemDelegate,
    QAbstractItemDelegate,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, QDate, QDateTime
from PySide6.QtGui import QKeySequence, QShortcut, QIcon, QKeyEvent

from src.core.collection_store import CollectionStore
from src.ui.table_delegates import FieldTypeDelegate, ValidationErrorDelegate


class RecordsTableModel(QAbstractTableModel):
    """Table model for records"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store: Optional[CollectionStore] = None
        self.fields: List[Dict] = []
        self.records: List[Dict] = []
        self.filtered_records: List[Dict] = []
        self._readonly = False  # Track readonly state
    
    def _get_date_format(self) -> str:
        """Get date format from config"""
        # Try to find config through parent chain
        parent = self.parent()
        while parent:
            if hasattr(parent, 'config'):
                return parent.config.get("date_format", "yyyy-MM-dd")
            parent = parent.parent() if hasattr(parent, 'parent') else None
        # Default if config not found
        return "yyyy-MM-dd"
    
    def _get_datetime_format(self) -> str:
        """Get datetime format from config"""
        # Try to find config through parent chain
        parent = self.parent()
        while parent:
            if hasattr(parent, 'config'):
                return parent.config.get("datetime_format", "yyyy-MM-dd HH:mm:ss")
            parent = parent.parent() if hasattr(parent, 'parent') else None
        # Default if config not found
        return "yyyy-MM-dd HH:mm:ss"

    def set_collection(self, store: Optional[CollectionStore], fields: List[Dict]):
        """Set the collection to display"""
        self.store = store
        self.fields = fields
        if store is None:
            # Clear the model
            self.beginResetModel()
            self.records = []
            self.filtered_records = []
            self.endResetModel()
        else:
            self._refresh_data()

    def _refresh_data(self):
        """Refresh record data"""
        if not self.store:
            return

        self.beginResetModel()
        self.records = self.store.list_records()
        self.filtered_records = self.records.copy()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.filtered_records)

    def columnCount(self, parent=QModelIndex()) -> int:
        # Add 1 for primary key column
        return len(self.fields) + 1

    def headerData(
        self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole
    ):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                # First column is primary key
                if section == 0:
                    return "ID"
                elif section - 1 < len(self.fields):
                    return self.fields[section - 1]["label"]
            else:
                return str(section + 1)
        elif role == Qt.DecorationRole:
            # Show key icon for primary key column
            if orientation == Qt.Horizontal and section == 0:
                from src.core.resource_path import asset_path
                key_icon_path = asset_path("key.png")
                if key_icon_path.exists():
                    return QIcon(str(key_icon_path))
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # Primary key column (column 0)
        if col == 0:
            if row >= len(self.filtered_records):
                return None
            record = self.filtered_records[row]
            if role == Qt.DisplayRole or role == Qt.EditRole:
                return str(record.get("id", ""))
            elif role == Qt.DecorationRole:
                # Show key icon in cells
                from src.core.resource_path import asset_path
                key_icon_path = asset_path("key.png")
                if key_icon_path.exists():
                    return QIcon(str(key_icon_path))
            return None

        # Regular field columns
        if row >= len(self.filtered_records) or col - 1 >= len(self.fields):
            return None

        record = self.filtered_records[row]
        field = self.fields[col - 1]  # Adjust for primary key column
        field_key = field["key"]
        field_type = field.get("type", "text")

        if role == Qt.DisplayRole or role == Qt.EditRole:
            value = record.get(field_key)
            if value is None:
                return ""
            
            # Format date/datetime values according to user preferences
            if field_type == "date":
                try:
                    from datetime import datetime
                    if isinstance(value, str):
                        dt = datetime.fromisoformat(value)
                    else:
                        dt = value
                    date = QDate(dt.year, dt.month, dt.day)
                    # Get date format from config
                    date_format = self._get_date_format()
                    return date.toString(date_format) if date_format else str(value)
                except (ValueError, TypeError, AttributeError):
                    return str(value)
            elif field_type == "datetime":
                try:
                    from datetime import datetime
                    if isinstance(value, str):
                        dt = datetime.fromisoformat(value)
                    else:
                        dt = value
                    qdt = QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
                    # Get datetime format from config
                    datetime_format = self._get_datetime_format()
                    return qdt.toString(datetime_format) if datetime_format else str(value)
                except (ValueError, TypeError, AttributeError):
                    return str(value)
            
            return str(value)

        return None

    def setData(self, index: QModelIndex, value, role=Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        
        # Block editing if readonly
        if self._readonly:
            return False

        row = index.row()
        col = index.column()

        # Handle primary key column editing (column 0)
        # Note: SQLite doesn't allow updating primary keys directly,
        # so we'll allow editing the display but warn that it won't persist
        if col == 0:
            if row >= len(self.filtered_records):
                return False
            record = self.filtered_records[row]
            # Update display only (database ID cannot be changed)
            try:
                new_id = int(value)
                record["id"] = new_id
                self.dataChanged.emit(index, index, [role])
                # Show warning that ID change won't persist
                # Get the view to access the visual rect
                view = self.parent()  # self.parent() is the TableView
                if view:
                    # Get the visual rect from the view
                    visual_rect = view.visualRect(index)
                    if visual_rect.isValid():
                        global_pos = view.mapToGlobal(visual_rect.topLeft())
                        QToolTip.showText(
                            global_pos,
                            "Note: Primary key changes are display-only and won't be saved to database"
                        )
                return True
            except (ValueError, TypeError):
                return False

        if row >= len(self.filtered_records) or col - 1 >= len(self.fields):
            return False

        record = self.filtered_records[row]
        field = self.fields[col - 1]  # Adjust for primary key column
        field_key = field["key"]
        record_id = record["id"]

        # Validate value before committing
        from src.core.validation import FieldValidator

        validation_result = FieldValidator.validate(field, value)

        if not validation_result.valid:
            # Show error tooltip
            error_msg = validation_result.error_message or "Invalid value"
            view = self.parent()  # self.parent() is the TableView
            if view:
                # Get the visual rect from the view
                visual_rect = view.visualRect(index)
                if visual_rect.isValid():
                    global_pos = view.mapToGlobal(visual_rect.topLeft())
                    QToolTip.showText(global_pos, error_msg)
            # Mark cell as having error (for visual feedback)
            if parent and hasattr(parent, "error_delegate"):
                parent.error_delegate.set_error(row, col, error_msg)
                parent.validation_errors[(row, col)] = error_msg
                # Trigger repaint
                self.dataChanged.emit(index, index, [Qt.DisplayRole])
            return False  # Block commit
        else:
            # Clear error if validation passes
            parent = self.parent()
            if parent and hasattr(parent, "error_delegate"):
                parent.error_delegate.clear_error(row, col)
                parent.validation_errors.pop((row, col), None)

        # Get old value for undo history
        old_value = record.get(field_key)
        
        # Update record in database
        if self.store:
            self.store.update_record(record_id, {field_key: value})
            
            # Add to undo history if main window is available
            # Find main window through TableView (which is the model's parent)
            main_window = None
            view = self.parent()  # Model's parent is the TableView
            if isinstance(view, TableView):
                # Find main window through TableView's parent chain
                parent = view.parent()
                while parent and not hasattr(parent, "_add_to_history"):
                    parent = parent.parent()
                if parent and hasattr(parent, "_add_to_history"):
                    main_window = parent
            
            if main_window and hasattr(main_window, "current_store") and main_window.current_store:
                # Create undo command for this field update
                from src.core.undo_redo import RecordUpdateCommand
                old_data = {field_key: old_value}
                new_data = {field_key: value}
                command = RecordUpdateCommand(main_window.current_store, record_id, old_data, new_data)
                main_window._add_to_history(command)

        # Update local data - also update in main records list
        record[field_key] = value
        # Find and update in main records list
        for main_record in self.records:
            if main_record["id"] == record_id:
                main_record[field_key] = value
                break

        # Clear any validation errors for this cell
        parent = self.parent()
        if parent and hasattr(parent, "validation_errors"):
            parent.validation_errors.pop((row, col), None)
            if hasattr(parent, "error_delegate"):
                parent.error_delegate.clear_error(row, col)

        self.dataChanged.emit(index, index, [role])
        
        # Notify main window to update navigation counter
        if main_window:
            main_window._update_navigation()
        
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        if index.isValid():
            # Only make editable if not readonly
            if not self._readonly:
                flags |= Qt.ItemIsEditable
        return flags
    
    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder):
        """Sort the model by column"""
        if not self.filtered_records:
            return
        
        # Determine sort key function based on column
        if column == 0:
            # Sort by primary key (ID)
            key_func = lambda r: r.get("id", 0)
        else:
            # Sort by field value
            field_index = column - 1  # Adjust for primary key column
            if field_index >= len(self.fields):
                return
            
            field = self.fields[field_index]
            field_key = field["key"]
            field_type = field.get("type", "text")
            
            def key_func(record):
                value = record.get(field_key)
                
                # Handle different field types for proper sorting
                if field_type == "integer":
                    if value is None:
                        return 0 if order == Qt.AscendingOrder else float('inf')
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return 0
                elif field_type == "decimal":
                    if value is None:
                        return 0.0 if order == Qt.AscendingOrder else float('inf')
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return 0.0
                elif field_type == "checkbox":
                    # Normalize checkbox values to boolean for consistent sorting
                    if value is None:
                        return False  # None/null treated as False
                    if isinstance(value, bool):
                        return value
                    # Convert string values to boolean
                    value_str = str(value).lower().strip()
                    return value_str in ("true", "1", "yes", "on")
                elif field_type in ("date", "datetime"):
                    # Sort dates as strings (ISO format sorts correctly)
                    if value is None:
                        return "" if order == Qt.AscendingOrder else "zzz"
                    return str(value)
                else:
                    # Text, notes, dropdown, etc. - sort as string
                    if value is None:
                        return "" if order == Qt.AscendingOrder else "zzz"
                    return str(value).lower()
        
        # Sort the filtered records
        self.layoutAboutToBeChanged.emit()
        
        reverse = (order == Qt.DescendingOrder)
        self.filtered_records.sort(key=key_func, reverse=reverse)
        
        self.layoutChanged.emit()
    
    def set_readonly(self, readonly: bool):
        """Set model readonly state"""
        self._readonly = readonly


class TableView(QTableView):
    """Table view widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = RecordsTableModel(self)  # Pass self as parent so model can find the view
        self.setModel(self.model)
        self._readonly = False  # Track readonly state

        # Enable features
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Enable sorting
        self.setSortingEnabled(True)
        
        # Enable column reordering
        self.horizontalHeader().setSectionsMovable(True)
        
        # Configure vertical header (row numbers) to be visible
        self.verticalHeader().setVisible(True)  # Ensure it's visible
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setMinimumSectionSize(20)  # Minimum to show row numbers
        self.verticalHeader().setDefaultAlignment(Qt.AlignCenter)  # Center row numbers
        # Set fixed width for vertical header to show row numbers properly
        # Fixed width ensures it's always visible and not cut off
        # Use larger width to account for padding (8px on each side) and text width
        self.verticalHeader().setFixedWidth(70)  # Width for row numbers with padding (e.g., "1000")

        # Enable inline editing - Tab navigation and typing handled in keyPressEvent
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
        )

        # Enable paste
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_table_context_menu)
        paste_action = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_action.activated.connect(self._handle_paste)

        # Connect context menu for header (field removal)
        self.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(
            self._show_header_context_menu
        )

        # Validation error delegate (for error highlighting)
        self.error_delegate = ValidationErrorDelegate(self)
        self.field_delegates = {}
        self.validation_errors = {}  # Track errors by (row, col)

    def set_collection(self, store: CollectionStore, fields: List[Dict]):
        """Set the collection to display"""
        self.model.set_collection(store, fields)
        self._fields = fields  # Store fields for _get_field_for_column

        # Set field-type-specific delegates (skip primary key column at index 0)
        self.field_delegates.clear()
        for col, field in enumerate(fields):
            delegate = FieldTypeDelegate(field, self)
            self.setItemDelegateForColumn(col + 1, delegate)  # +1 for primary key column
            self.field_delegates[col + 1] = delegate

        # Set primary key column width (first column)
        self.setColumnWidth(0, 60)  # Fixed width for ID column
        
        # Get default column width from config if available
        default_col_width = 120  # Default fallback
        if hasattr(self, 'parent') and self.parent():
            # Try to find main window to get config
            parent = self.parent()
            while parent and not hasattr(parent, 'config'):
                parent = parent.parent()
            if parent and hasattr(parent, 'config'):
                default_col_width = parent.config.get("column_width_default", 120)
        
        # Auto-resize columns to content with min/max constraints
        self.resizeColumnsToContents()
        # Set minimum and maximum widths for columns (skip primary key column)
        for col in range(1, len(fields) + 1):  # Start from 1, skip primary key
            current_width = self.columnWidth(col)
            # Set minimum width based on header
            header_width = self.horizontalHeader().sectionSizeHint(col)
            min_width = max(header_width, 80)  # Minimum 80px
            max_width = 400  # Maximum 400px before manual adjustment needed
            if current_width < min_width:
                self.setColumnWidth(col, min_width)
            elif current_width > max_width:
                self.setColumnWidth(col, max_width)
            elif current_width < default_col_width:
                # If column is smaller than default, use default
                self.setColumnWidth(col, default_col_width)
            else:
                # Keep auto-sized width
                pass

    def set_readonly(self, readonly: bool):
        """Set table to readonly mode (disable editing)"""
        self._readonly = readonly
        
        # Update model's readonly state
        if self.model:
            self.model._readonly = readonly
        
        if readonly:
            # Disable editing
            self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        else:
            # Re-enable editing
            self.setEditTriggers(
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.EditKeyPressed
            )

    def _show_header_context_menu(self, position):
        """Show context menu for header (field removal and show/hide key)"""
        if not self.model or not self.model.store:
            return

        # Get column at position
        column = self.horizontalHeader().logicalIndexAt(position.x())
        
        # Validate column index
        if column < 0 or column >= self.model.columnCount():
            return
        
        menu = QMenu(self)
        
        # For primary key column (column 0), show Hide/Show Key option
        if column == 0:
            # Check if key column is currently visible
            is_visible = not self.isColumnHidden(0)
            if is_visible:
                hide_action = menu.addAction("Hide Key")
                hide_action.triggered.connect(lambda: self.setColumnHidden(0, True))
            else:
                show_action = menu.addAction("Show Key")
                show_action.triggered.connect(lambda: self.setColumnHidden(0, False))
        else:
            # For other columns, show field removal option
            # Adjust for primary key column (column 0)
            field_index = column - 1
            
            # Validate field index bounds
            if field_index < 0 or field_index >= len(self.model.fields):
                return
            
            field = self.model.fields[field_index]
            field_key = field["key"]
            field_label = field["label"]

            from src.core.resource_path import asset_path
            remove_action = menu.addAction(
                QIcon(str(asset_path("delete_column.svg"))), f"Remove Field '{field_label}'..."
            )
            remove_action.triggered.connect(
                lambda: self._remove_field(field_key, field_label)
            )
        
        menu.exec(self.horizontalHeader().mapToGlobal(position))

    def _show_table_context_menu(self, position):
        """Show context menu for table (for showing key when hidden and adding rows)"""
        if not self.model or not self.model.store:
            return
        
        # Check if click is on a row
        index = self.indexAt(position)
        is_row_click = index.isValid() and index.row() >= 0
        
        # Store current selection to restore it if Qt changes it
        if self.selectionModel():
            current_selection = self.selectionModel().selection()
            clicked_row_was_selected = False
            if is_row_click:
                clicked_row_was_selected = any(idx.row() == index.row() for idx in current_selection.indexes())
        else:
            current_selection = None
            clicked_row_was_selected = False
        
        menu = QMenu(self)
        
        if is_row_click:
            row = index.row()
            # Duplicate Row option (when clicking on a row)
            duplicate_row_action = menu.addAction("Duplicate Row")
            duplicate_row_action.triggered.connect(lambda: self._duplicate_row_via_context(row))
            
            # Delete Row option (when clicking on a row)
            delete_row_action = menu.addAction("Delete Row")
            delete_row_action.triggered.connect(lambda: self._delete_row_via_context(row))
            menu.addSeparator()
        
        # Add Row option (always available)
        add_row_action = menu.addAction("Add Row...")
        add_row_action.triggered.connect(self._add_row_via_context)
        
        # Show Key option (only if key column is hidden)
        if self.isColumnHidden(0):
            menu.addSeparator()
            show_key_action = menu.addAction("Show Key")
            show_key_action.triggered.connect(lambda: self.setColumnHidden(0, False))
        
        menu.exec(self.mapToGlobal(position))
        
        # Restore selection if Qt automatically selected a row that wasn't selected before
        if current_selection and self.selectionModel() and is_row_click and not clicked_row_was_selected:
            new_selection = self.selectionModel().selection()
            # Check if the clicked row is now selected
            clicked_row_now_selected = any(idx.row() == index.row() for idx in new_selection.indexes())
            if clicked_row_now_selected:
                # Restore the previous selection (without the clicked row)
                self.selectionModel().select(current_selection, self.selectionModel().ClearAndSelect)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard input for tab navigation and typing"""
        # Handle Tab key - move to next cell and start editing
        if event.key() == Qt.Key_Tab:
            current = self.currentIndex()
            if current.isValid() and not self._readonly:
                # Commit current edit if any
                if self.state() == QAbstractItemView.EditingState:
                    current_editor = self.indexWidget(current)
                    if current_editor:
                        # Commit the data
                        self.commitData(current_editor)
                    self.closeEditor(current_editor, QAbstractItemDelegate.NoHint)
                
                # Move to next cell
                if event.modifiers() & Qt.ShiftModifier:
                    # Shift+Tab: move to previous cell
                    if current.column() > 0:
                        next_index = self.model.index(current.row(), current.column() - 1)
                    else:
                        # Move to last column of previous row
                        if current.row() > 0:
                            next_index = self.model.index(current.row() - 1, self.model.columnCount() - 1)
                        else:
                            next_index = current
                else:
                    # Tab: move to next cell
                    if current.column() < self.model.columnCount() - 1:
                        next_index = self.model.index(current.row(), current.column() + 1)
                    else:
                        # Move to first column of next row
                        if current.row() < self.model.rowCount() - 1:
                            next_index = self.model.index(current.row() + 1, 0)
                        else:
                            next_index = current
                
                self.setCurrentIndex(next_index)
                # Ensure checkbox cells get focus even though they don't use editors
                field = self._get_field_for_column(next_index.column())
                if field and field.get("type") == "checkbox":
                    # For checkboxes, just ensure focus - spacebar will handle toggling
                    self.setFocus()
                else:
                    self.edit(next_index)
                event.accept()
                return
        
        # Handle Enter key - move down and start editing
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            current = self.currentIndex()
            if current.isValid() and not self._readonly:
                # Commit current edit if any
                if self.state() == QAbstractItemView.EditingState:
                    current_editor = self.indexWidget(current)
                    if current_editor:
                        # Commit the data
                        self.commitData(current_editor)
                    self.closeEditor(current_editor, QAbstractItemDelegate.NoHint)
                
                # Move down (or up with Shift)
                if event.modifiers() & Qt.ShiftModifier:
                    # Shift+Enter: move up
                    if current.row() > 0:
                        next_index = self.model.index(current.row() - 1, current.column())
                    else:
                        next_index = current
                else:
                    # Enter: move down
                    if current.row() < self.model.rowCount() - 1:
                        next_index = self.model.index(current.row() + 1, current.column())
                    else:
                        next_index = current
                
                self.setCurrentIndex(next_index)
                # Ensure checkbox cells get focus even though they don't use editors
                field = self._get_field_for_column(next_index.column())
                if field and field.get("type") == "checkbox":
                    # For checkboxes, just ensure focus - spacebar will handle toggling
                    self.setFocus()
                else:
                    self.edit(next_index)
                event.accept()
                return
        
        # Handle Spacebar for checkbox fields
        elif event.key() == Qt.Key_Space:
            current = self.currentIndex()
            if current.isValid() and not self._readonly:
                field = self._get_field_for_column(current.column())
                if field and field.get("type") == "checkbox":
                    # Toggle checkbox value
                    value = self.model.data(current, Qt.EditRole)
                    checked = False
                    
                    if isinstance(value, bool):
                        checked = value
                    elif isinstance(value, str):
                        checked = value.lower() in ("true", "1", "yes", "on")
                    else:
                        checked = bool(value)
                    
                    # Toggle the value
                    new_value = not checked
                    self.model.setData(current, new_value, Qt.EditRole)
                    event.accept()
                    return
        
        # For navigation keys (arrows, page up/down, etc.), let parent handle them
        elif event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right, 
                             Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End):
            super().keyPressEvent(event)
            return
        
        # For other keys, if it's a printable character and we have a selection, start editing
        elif event.text() and len(event.text()) > 0 and event.text().isprintable():
            current = self.currentIndex()
            if current.isValid() and not self._readonly:
                # Don't start editing for checkbox fields
                field = self._get_field_for_column(current.column())
                if field and field.get("type") == "checkbox":
                    # Let parent handle it (might be navigation)
                    super().keyPressEvent(event)
                    return
                
                # Start editing immediately when typing
                if self.state() != QAbstractItemView.EditingState:
                    self.edit(current)
                    # The key event will be forwarded to the editor automatically
                    return
        
        # Call parent implementation for other keys
        super().keyPressEvent(event)
    
    def _get_field_for_column(self, column: int):
        """Get the field definition for a given column index"""
        if not hasattr(self, '_fields') or not self._fields:
            return None
        # Column 0 is primary key, so adjust
        if column == 0:
            return None
        field_index = column - 1
        if 0 <= field_index < len(self._fields):
            return self._fields[field_index]
        return None
    
    def _add_row_via_context(self):
        """Add a new row via context menu"""
        # Find main window through parent chain
        parent = self.parent()
        while parent and not hasattr(parent, "_new_record"):
            parent = parent.parent()
        
        if parent and hasattr(parent, "_new_record"):
            parent._new_record()
    
    def _duplicate_row_via_context(self, row: int):
        """Duplicate a row via context menu"""
        # Find main window through parent chain
        parent = self.parent()
        while parent and not hasattr(parent, "_duplicate_record"):
            parent = parent.parent()
        
        if parent and hasattr(parent, "_duplicate_record"):
            # Only select the row if it's not already selected
            # This prevents unwanted selection changes when right-clicking
            selected_rows = [idx.row() for idx in self.selectedIndexes()]
            if row not in selected_rows:
                self.selectRow(row)
            parent._duplicate_record()
    
    def _delete_row_via_context(self, row: int):
        """Delete a row via context menu"""
        # Find main window through parent chain
        parent = self.parent()
        while parent and not hasattr(parent, "_delete_record"):
            parent = parent.parent()
        
        if parent and hasattr(parent, "_delete_record"):
            # Only select the row if it's not already selected
            # This prevents unwanted selection changes when right-clicking
            selected_rows = [idx.row() for idx in self.selectedIndexes()]
            if row not in selected_rows:
                self.selectRow(row)
            parent._delete_record()

    def _remove_field(self, field_key: str, field_label: str):
        """Remove a field from the collection"""
        reply = QMessageBox.warning(
            self,
            "Remove Field",
            f"Are you sure you want to remove the field '{field_label}'?\n\n"
            f"⚠️ WARNING:\n"
            f"• All data in this field will be permanently lost\n"
            f"• This action cannot be undone\n"
            f"• Any dependencies or relationships using this field may break\n"
            f"• The column will be removed from all records\n\n"
            f"This is a destructive operation. Consider exporting your data first.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            if not self.model or not self.model.store:
                return
            
            try:
                # Remove field from database
                self.model.store.remove_field(field_key)
                
                # Find main window to refresh the collection view
                main_window = None
                parent = self.parent()
                while parent and not hasattr(parent, "_open_collection"):
                    parent = parent.parent()
                if parent and hasattr(parent, "_open_collection"):
                    main_window = parent
                
                # Refresh the collection view
                if main_window and hasattr(main_window, "current_collection") and main_window.current_collection:
                    collection_name = main_window.current_collection
                    main_window._open_collection(collection_name)
                    main_window.statusBar().showMessage(f"Field '{field_label}' removed successfully", 3000)
                else:
                    # Fallback: just reload fields in current view
                    fields = self.model.store.list_fields()
                    self.set_collection(self.model.store, fields)
                    
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to remove field: {str(e)}"
                )

    def _handle_paste(self):
        """Handle paste from clipboard"""
        # Block paste if readonly
        if self._readonly:
            return
        
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return

        # Parse tabular data
        rows = []
        for line in text.strip().split("\n"):
            # Support both tab and comma delimiters
            if "\t" in line:
                cells = line.split("\t")
            else:
                cells = line.split(",")
            rows.append([cell.strip() for cell in cells])

        if not rows:
            return

        # Get current selection
        current_index = self.currentIndex()
        if not current_index.isValid():
            # Start from first row, first column
            start_row = 0
            start_col = 0
        else:
            start_row = current_index.row()
            start_col = current_index.column()

        # Determine how many columns we can paste (skip primary key column)
        max_cols = self.model.columnCount() - 1  # Exclude primary key column
        available_cols = max_cols - max(0, start_col - 1)  # Adjust for primary key
        if start_col == 0:
            start_col = 1  # Skip primary key column

        # Paste data
        created_count = 0
        updated_count = 0
        errors = []

        for row_idx, row_data in enumerate(rows):
            target_row = start_row + row_idx

            # If pasting beyond existing rows, create new records
            if target_row >= len(self.model.filtered_records):
                # Create new record
                if not self.model.store:
                    continue

                # Get default values
                new_record_data = {}
                for col_idx, value in enumerate(row_data[:available_cols]):
                    field_col = start_col + col_idx - 1  # Adjust for primary key column
                    if 0 <= field_col < len(self.model.fields):
                        field = self.model.fields[field_col]
                        new_record_data[field["key"]] = value

                try:
                    record_id = self.model.store.add_record(new_record_data)
                    created_count += 1
                except Exception as e:
                    errors.append(f"Row {row_idx+1}: {str(e)}")
            else:
                # Update existing record
                record = self.model.filtered_records[target_row]
                record_id = record["id"]

                for col_idx, value in enumerate(row_data[:available_cols]):
                    field_col = start_col + col_idx - 1  # Adjust for primary key column
                    if 0 <= field_col < len(self.model.fields):
                        field = self.model.fields[field_col]
                        field_key = field["key"]

                        # Validate and update (add 1 for primary key column)
                        index = self.model.index(target_row, start_col + col_idx)
                        if not self.model.setData(index, value):
                            errors.append(
                                f"Row {row_idx+1}, Col {col_idx+1}: Invalid value"
                            )
                        else:
                            updated_count += 1

        # Refresh model
        self.model._refresh_data()

        # Show summary
        if errors:
            QMessageBox.warning(
                self,
                "Paste Complete with Errors",
                f"Pasted {created_count + updated_count} cells.\n"
                f"Created {created_count} records, updated {updated_count} cells.\n\n"
                f"Errors: {len(errors)}\n" + "\n".join(errors[:5]),
            )
        else:
            QMessageBox.information(
                self,
                "Paste Complete",
                f"Successfully pasted {created_count + updated_count} cells.\n"
                f"Created {created_count} records, updated {updated_count} cells.",
            )
