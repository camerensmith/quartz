"""Table view (spreadsheet-like)"""


from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QDate,
    QDateTime,
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QMenu,
    QMessageBox,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QToolTip,
)

from src.core.collection_store import CollectionStore
from src.ui.table_delegates import FieldTypeDelegate, ValidationErrorDelegate


class CellBorderDelegate(QStyledItemDelegate):
    """Delegate that draws a border around selected cells"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = parent

    def _is_dark_mode(self):
        """Detect if we're in dark mode by checking table background color"""
        if not self.view:
            return False
        bg_color = self.view.palette().color(self.view.backgroundRole())
        # Dark mode typically has background RGB values < 128
        return bg_color.red() < 128 and bg_color.green() < 128 and bg_color.blue() < 128

    def paint(self, painter, option, index):
        """Paint cell with border if selected"""
        # Disable default focus indicator (dotted rectangle around text)
        option.state &= ~QStyle.State_HasFocus

        # Check if this cell is selected
        if self.view and self.view.selectionModel():
            is_selected = self.view.selectionModel().isSelected(index)
            is_current = (index == self.view.currentIndex())

            if is_selected or is_current:
                # Draw border around entire cell
                painter.save()
                # Use lighter grey for dark mode, black for light mode
                if self._is_dark_mode():
                    border_color = QColor("#f5f5f5")  # Very light grey, almost white for dark mode
                else:
                    border_color = QColor(Qt.black)
                pen = QPen(border_color, 3)  # 3px border - thicker for better visibility
                painter.setPen(pen)
                # Draw border rectangle around the entire cell
                border_rect = option.rect.adjusted(1, 1, -1, -1)
                painter.drawRect(border_rect)
                painter.restore()

        # Call parent paint to draw cell content (without focus indicator)
        super().paint(painter, option, index)


class RecordsTableModel(QAbstractTableModel):
    """Table model for records with virtualization support"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store: CollectionStore | None = None
        self.fields: list[dict] = []
        self.records: list[dict] = []
        self.filtered_records: list[dict] = []
        self._readonly = False  # Track readonly state

        # Subcollection filter: when set, only records whose id is in this set are shown
        self._subcollection_ids: set | None = None

        # Virtualization support
        self._virtualized = True  # Enable virtualization for large datasets
        self._batch_size = 200  # Load 200 records at a time (reduced for better responsiveness)
        self._loaded_batches: set = set()  # Track which batches are loaded
        self._record_cache: dict[int, dict] = {}  # Cache records by row index
        self._total_count = 0  # Total record count (without loading all)
        self._search_query: str | None = None  # Current search query
        self._sort_column: int | None = None  # Current sort column
        self._sort_order = Qt.AscendingOrder  # Current sort order
        self._max_cache_size = 2000  # Maximum cached records (prevent memory bloat)
        self._formatted_cache: dict[tuple, Any] = {}  # Cache formatted values: (row, col, role) -> value
        self._filter_error: str | None = None  # Error message when filters are invalid
        self._is_filtered: bool = False  # True when a search/filter is active (even if results are empty)

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

    def set_collection(self, store: CollectionStore | None, fields: list[dict]):
        """Set the collection to display"""
        self.store = store
        self.fields = fields
        self._subcollection_ids = None  # Clear subcollection filter on collection change
        if store is None:
            # Clear the model
            self.beginResetModel()
            self.records = []
            self.filtered_records = []
            self._is_filtered = False
            self._record_cache.clear()
            self._loaded_batches.clear()
            self._total_count = 0
            self.endResetModel()
        else:
            self._filter_error = None  # Clear filter error when collection changes
            self._is_filtered = False
            self._refresh_data()

    def set_subcollection_filter(self, record_ids: set):
        """Restrict display to records whose id is in *record_ids*.

        The existing search / field filters will additionally narrow the result
        when applied by main_window."""
        self._subcollection_ids = record_ids
        self._is_filtered = True
        self._apply_subcollection_to_display()

    def clear_subcollection_filter(self):
        """Remove subcollection restriction and revert to normal display."""
        self._subcollection_ids = None
        # If no other filters remain, mark as unfiltered
        self._is_filtered = False
        self._formatted_cache.clear()
        # Repopulate filtered_records with all records
        if self._virtualized and self._total_count > 500:
            self.filtered_records = []
        else:
            self.filtered_records = self.records.copy() if self.records else []
        self.beginResetModel()
        self.endResetModel()

    def _apply_subcollection_to_display(self):
        """Filter filtered_records (or all records) to only subcollection members."""
        if self._subcollection_ids is None:
            return
        self._formatted_cache.clear()
        if self._virtualized and self._total_count > 500:
            # Load all records from DB so we can filter them
            all_records = self.store.list_records() if self.store else []
        else:
            all_records = self.records if self.records else []
        self.filtered_records = [r for r in all_records if r.get("id") in self._subcollection_ids]
        self.beginResetModel()
        self.endResetModel()

    def _refresh_data(self):
        """Refresh record data - uses virtualization for large datasets"""
        if not self.store:
            return

        self.beginResetModel()

        # Clear all caches when refreshing to free memory
        self._formatted_cache.clear()
        # Aggressive cache cleanup - keep only recent entries if cache is large
        if len(self._formatted_cache) > 1000:
            # Keep only the most recent 500 entries
            items = list(self._formatted_cache.items())[-500:]
            self._formatted_cache = dict(items)

        # Get total count first (fast, doesn't load records)
        self._total_count = self.store.count_records()

        # Decide whether to use virtualization based on record count
        # Use virtualization for collections with more than 500 records (lowered threshold)
        use_virtualization = self._virtualized and self._total_count > 500

        if use_virtualization:
            # Virtualized mode: don't load all records, just track count
            self.records = []  # Empty list, records loaded on demand
            self.filtered_records = []  # Empty for now, will be populated on demand
            self._record_cache.clear()
            self._loaded_batches.clear()

            # Load first 2 batches immediately for initial display (better initial experience)
            self._load_batch(0)
            if self._total_count > self._batch_size:
                self._load_batch(self._batch_size)
        else:
            # Small dataset: load all records (backward compatible)
            self.records = self.store.list_records()
            self.filtered_records = self.records.copy()
            self._record_cache.clear()
            self._loaded_batches.clear()

        self.endResetModel()

    def _load_batch(self, row_index: int):
        """Load a batch of records containing the given row index"""
        if not self.store or self._total_count == 0:
            return

        # Calculate which batch this row belongs to
        batch_num = row_index // self._batch_size
        offset = batch_num * self._batch_size

        # Skip if already loaded
        if batch_num in self._loaded_batches:
            return

        # Clean cache if it's getting too large (keep most recent batches)
        if len(self._record_cache) > self._max_cache_size:
            self._clean_cache()

        # Load the batch
        batch_records = self.store.list_records(limit=self._batch_size, offset=offset)

        # Cache the records
        for i, record in enumerate(batch_records):
            cache_index = offset + i
            self._record_cache[cache_index] = record

        # Mark batch as loaded
        self._loaded_batches.add(batch_num)

        # In virtualized mode, filtered_records is not used for storage
        # Records are accessed directly from cache via _get_record()
        # filtered_records is kept empty in virtualized mode to save memory

    def _clean_cache(self):
        """Clean old records from cache to free memory"""
        if len(self._record_cache) <= self._max_cache_size:
            return

        # Keep the most recently accessed batches (keep middle 80% of cache)
        sorted_indices = sorted(self._record_cache.keys())
        keep_start = len(sorted_indices) // 10  # Keep from 10% to 90%
        keep_end = len(sorted_indices) - (len(sorted_indices) // 10)

        # Remove records outside the keep range
        to_remove = []
        for idx in sorted_indices[:keep_start]:
            to_remove.append(idx)
        for idx in sorted_indices[keep_end:]:
            to_remove.append(idx)

        for idx in to_remove:
            self._record_cache.pop(idx, None)
            # Also mark batch as unloaded if all records from that batch are removed
            batch_num = idx // self._batch_size
            batch_start = batch_num * self._batch_size
            batch_end = batch_start + self._batch_size
            if not any(i in self._record_cache for i in range(batch_start, batch_end)):
                self._loaded_batches.discard(batch_num)

    def _get_record(self, row: int) -> dict | None:
        """Get record at row index, loading batch if needed"""
        if not self.store:
            return None

        # If we have filtered_records (from search/filter), ALWAYS use those first
        # This takes priority over cache to ensure filtered results are shown
        if self.filtered_records and 0 <= row < len(self.filtered_records):
            return self.filtered_records[row]

        # Don't use cache if we have filtered_records (they should be used instead)
        # Check if we have it cached (only if no filtered_records)
        if not self.filtered_records and row in self._record_cache:
            return self._record_cache[row]

        # Check if we're in virtualized mode
        if self._virtualized and self._total_count > 500:
            # Load the batch containing this row
            self._load_batch(row)
            return self._record_cache.get(row)
        else:
            # Non-virtualized mode: should be in records
            if self.records and 0 <= row < len(self.records):
                return self.records[row]

        return None

    def rowCount(self, parent=None) -> int:
        """Return total row count (virtualized or actual)"""
        # If there's a filter error, show one row for the error message
        if self._filter_error:
            return 1

        # If we have filtered_records, or a filter is active (even with 0 results), use that count
        if self.filtered_records or self._is_filtered:
            return len(self.filtered_records)

        # Otherwise, use virtualized count or regular records count
        if self._virtualized and self._total_count > 500:
            # In virtualized mode, return total count
            return self._total_count
        else:
            # Non-virtualized mode: return actual records count
            return len(self.records) if self.records else 0

    def columnCount(self, parent=None) -> int:
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
        elif role == Qt.FontRole:
            # Make header bold if this is the current column
            if orientation == Qt.Horizontal:
                if hasattr(self, '_current_column') and section == self._current_column:
                    font = QFont()
                    font.setBold(True)
                    return font
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # If there's a filter error, show error message in first column
        if self._filter_error:
            if role == Qt.DisplayRole:
                if col == 0:
                    return "⚠"
                elif col == 1:
                    return self._filter_error
                else:
                    return ""
            return None

        # If we have filtered_records, don't use cache (row indices have changed)
        # Check cache first (for formatted values) only if not using filtered_records
        cache_key = (row, col, role)
        if not self.filtered_records and cache_key in self._formatted_cache:
            return self._formatted_cache[cache_key]

        # Get record (will load batch if needed in virtualized mode)
        record = self._get_record(row)
        if not record:
            return None

        result = None

        # Primary key column (column 0)
        if col == 0:
            if role == Qt.DisplayRole or role == Qt.EditRole:
                result = str(record.get("id", ""))
            elif role == Qt.DecorationRole:
                # Show key icon in cells - cache the icon path lookup
                from src.core.resource_path import asset_path
                key_icon_path = asset_path("key.png")
                if key_icon_path.exists():
                    result = QIcon(str(key_icon_path))
        else:
            # Regular field columns
            if col - 1 < len(self.fields):
                field = self.fields[col - 1]  # Adjust for primary key column
                field_key = field["key"]
                field_type = field.get("type", "text")

                if role == Qt.DisplayRole or role == Qt.EditRole:
                    value = record.get(field_key)
                    if value is None:
                        result = ""
                    else:
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
                                result = date.toString(date_format) if date_format else str(value)
                            except (ValueError, TypeError, AttributeError):
                                result = str(value)
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
                                result = qdt.toString(datetime_format) if datetime_format else str(value)
                            except (ValueError, TypeError, AttributeError):
                                result = str(value)
                        else:
                            result = str(value)

        # Cache the result (only for DisplayRole to save memory)
        if result is not None and role == Qt.DisplayRole:
            # Limit cache size to prevent memory bloat
            if len(self._formatted_cache) > 5000:
                # Clear oldest 50% of cache
                keys_to_remove = list(self._formatted_cache.keys())[:2500]
                for key in keys_to_remove:
                    self._formatted_cache.pop(key, None)
            self._formatted_cache[cache_key] = result

        return result

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

        if col - 1 >= len(self.fields):
            return False

        record = self._get_record(row)
        if not record:
            return False
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
            parent = self.parent()  # Get parent before using it
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
        # Update cache if in virtualized mode
        if self._virtualized and self._total_count > 1000:
            # Update cached record
            if row in self._record_cache:
                self._record_cache[row][field_key] = value
        else:
            # Find and update in main records list (non-virtualized mode)
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

        # Clear formatted cache for this cell
        cache_key = (row, col, Qt.DisplayRole)
        self._formatted_cache.pop(cache_key, None)

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
        # Don't sort if store is not set (e.g., during initialization)
        if not self.store:
            return

        # Clear formatted cache when sorting
        self._formatted_cache.clear()

        # Store sort state
        self._sort_column = column
        self._sort_order = order

        # For virtualized mode with large datasets, try database-level sorting first
        if self._virtualized and self._total_count > 500:
            # Try database-level sorting for simple cases (ID column or indexed fields)
            if column == 0:
                # Sort by ID - can use database sorting
                order_dir = "ASC" if order == Qt.AscendingOrder else "DESC"
                # Reload with database sorting
                self.beginResetModel()
                self.records = self.store.list_records(order_by=f"id {order_dir}")
                # In virtualized mode, populate filtered_records for sorting
                self.filtered_records = self.records.copy()
                # Cache all records
                self._record_cache.clear()
                for i, record in enumerate(self.records):
                    self._record_cache[i] = record
                self.endResetModel()
                return

            # For other columns, need to load all records for in-memory sorting
            # Temporarily disable virtualization to load all records
            if not self.records or len(self.records) < self._total_count:
                # Load all records
                self.records = self.store.list_records()
                # Cache all records
                self._record_cache.clear()
                for i, record in enumerate(self.records):
                    self._record_cache[i] = record

            # Populate filtered_records from records (or use search results if filtered)
            if not self.filtered_records and not self._is_filtered:
                # If no filter applied, use all records
                self.filtered_records = self.records.copy()
            elif len(self.filtered_records) < len(self.records):
                # Filtered - keep filtered_records as is
                pass
            else:
                # No filter, use all records
                self.filtered_records = self.records.copy()

        # Ensure we have records to sort
        if not self.filtered_records and not self._is_filtered:
            # Try to get records if we don't have them
            if not self.records:
                self.records = self.store.list_records()
            self.filtered_records = self.records.copy() if self.records else []

        if not self.filtered_records:
            return

        # Determine sort key function based on column
        if column == 0:
            # Sort by primary key (ID)
            def key_func(r):
                return r.get("id", 0)
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
        self.setSelectionBehavior(QAbstractItemView.SelectItems)  # Select individual cells
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Allow multiple cell selection
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Performance optimizations for large datasets
        self.verticalScrollBar().setSingleStep(1)  # Smooth scrolling

        # Connect scroll events for pre-fetching in virtualized mode
        from PySide6.QtCore import QTimer
        self._prefetch_timer = QTimer()
        self._prefetch_timer.setSingleShot(True)
        self._prefetch_timer.timeout.connect(self._prefetch_visible_records)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # Track current column for header bolding
        self.model._current_column = -1

        # Connect to selection changes to update header boldness
        self.selectionModel().currentChanged.connect(self._on_selection_changed)

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

        # Enable inline editing - AnyKeyPressed forwards the typed character to the new editor
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
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

        # Set a default delegate for selected cell border (for ID column and any columns without field delegates)
        self._cell_border_delegate = CellBorderDelegate(self)
        self.setItemDelegate(self._cell_border_delegate)

    def _on_scroll(self):
        """Handle scroll event - trigger pre-fetch after scroll stops"""
        # Debounce pre-fetching to avoid loading too frequently
        self._prefetch_timer.stop()
        self._prefetch_timer.start(100)  # Reduced delay for more responsive loading

    def _prefetch_visible_records(self):
        """Pre-fetch records around the visible area"""
        if not self.model or not self.model.store:
            return

        # Only pre-fetch in virtualized mode
        if not (self.model._virtualized and self.model._total_count > 500):
            return

        # Get visible row range
        visible_rect = self.viewport().rect()
        top_index = self.indexAt(visible_rect.topLeft())
        bottom_index = self.indexAt(visible_rect.bottomLeft())

        if not top_index.isValid() or not bottom_index.isValid():
            return

        # Pre-fetch more aggressively: 2 batches before and after visible area
        prefetch_batches = 2
        start_row = max(0, top_index.row() - (prefetch_batches * self.model._batch_size))
        end_row = min(self.model._total_count - 1, bottom_index.row() + (prefetch_batches * self.model._batch_size))

        # Load batches for visible range (load in background to avoid blocking)
        from PySide6.QtCore import QTimer
        batches_to_load = []
        for row in range(start_row, end_row + 1, self.model._batch_size):
            batch_num = row // self.model._batch_size
            if batch_num not in self.model._loaded_batches:
                batches_to_load.append(row)

        # Load batches with slight delay to avoid blocking UI
        if batches_to_load:
            def load_next_batch():
                if batches_to_load:
                    self.model._load_batch(batches_to_load.pop(0))
                    if batches_to_load:
                        QTimer.singleShot(10, load_next_batch)  # Load next batch after 10ms
            QTimer.singleShot(0, load_next_batch)  # Start loading immediately

    def set_collection(self, store: CollectionStore, fields: list[dict]):
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
                | QAbstractItemView.AnyKeyPressed
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

        # Note: Show/Hide Key is only available through View menu, not context menu
        # Skip primary key column (column 0) - no context menu options for it
        if column == 0:
            return

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
            # Get count of fully-selected rows (including the clicked row if not already
            # fully selected).  This must match what _delete_record() will actually delete,
            # which uses selectedRows() (all columns selected).
            selection_model = self.selectionModel()
            selected_count = 0
            if selection_model:
                fully_selected_rows = {idx.row() for idx in selection_model.selectedRows()}
                selected_count = len(fully_selected_rows)
                # If clicked row is not fully selected it will be added, so count it
                if row not in fully_selected_rows:
                    selected_count += 1

            # Duplicate Row option (when clicking on a row)
            duplicate_row_action = menu.addAction("Duplicate Row")
            duplicate_row_action.triggered.connect(lambda: self._duplicate_row_via_context(row))

            # Delete Row option - show count if multiple will be deleted
            if selected_count > 1:
                delete_row_action = menu.addAction(f"Delete {selected_count} Rows")
            else:
                delete_row_action = menu.addAction("Delete Row")
            delete_row_action.triggered.connect(lambda: self._delete_row_via_context(row))
            menu.addSeparator()

            # Add to Subcollection
            add_to_sub_action = menu.addAction("Add to Subcollection")
            add_to_sub_action.triggered.connect(lambda: self._add_rows_to_subcollection(row))
            menu.addSeparator()

        # Add Row option (always available)
        add_row_action = menu.addAction("Add Row...")
        add_row_action.triggered.connect(self._add_row_via_context)

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
                        # Close editor, which will commit data automatically
                        self.closeEditor(current_editor, QAbstractItemDelegate.EditNextItem)
                    else:
                        # No editor, just move to next cell
                        pass

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
                        # Close editor, which will commit data automatically
                        self.closeEditor(current_editor, QAbstractItemDelegate.EditNextItem)
                    else:
                        # No editor, just move down
                        pass

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
        # Calling super() lets Qt use the AnyKeyPressed trigger, which both opens the editor
        # and forwards the typed character into it (so the first keystroke is not lost).
        elif event.text() and len(event.text()) > 0 and event.text().isprintable():
            current = self.currentIndex()
            if current.isValid() and not self._readonly:
                super().keyPressEvent(event)
                return

        # Call parent implementation for other keys
        super().keyPressEvent(event)

    def closeEditor(self, editor, hint):
        """Override to auto-start editing on the next cell after Enter/Tab commits."""
        super().closeEditor(editor, hint)
        if hint in (QAbstractItemDelegate.EditNextItem, QAbstractItemDelegate.EditPreviousItem):
            def _start_next_edit():
                current = self.currentIndex()
                if current.isValid() and not self._readonly:
                    field = self._get_field_for_column(current.column())
                    # Checkboxes don't use a line-editor; skip them
                    if not (field and field.get("type") == "checkbox"):
                        self.edit(current)
            QTimer.singleShot(0, _start_next_edit)

    def _on_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """Handle selection changes to update header boldness"""
        old_column = self.model._current_column if hasattr(self.model, '_current_column') else -1
        new_column = current.column() if current.isValid() else -1

        if old_column != new_column:
            self.model._current_column = new_column
            # Update header to refresh bold state
            if old_column >= 0:
                self.model.headerDataChanged.emit(Qt.Horizontal, old_column, old_column)
            if new_column >= 0:
                self.model.headerDataChanged.emit(Qt.Horizontal, new_column, new_column)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events - clear selection if clicking outside cells"""
        # Check if click is on a valid cell
        index = self.indexAt(event.pos())

        if not index.isValid():
            # Clicked outside any cell - deselect the current record only
            # Only clear if not clicking on headers or other table components
            if event.pos().y() > self.horizontalHeader().height():
                if self.selectionModel():
                    self.selectionModel().clearSelection()
                    # Update header boldness
                    if hasattr(self.model, '_current_column') and self.model._current_column >= 0:
                        old_column = self.model._current_column
                        self.model._current_column = -1
                        self.model.headerDataChanged.emit(Qt.Horizontal, old_column, old_column)
            event.accept()
            return

        # Clicked on a valid cell - let parent handle it normally (allows editing)
        super().mousePressEvent(event)

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
        """Delete a row via context menu - works with multiple selections and cell clicks"""
        # Find main window through parent chain
        parent = self.parent()
        while parent and not hasattr(parent, "_delete_record"):
            parent = parent.parent()

        if parent and hasattr(parent, "_delete_record"):
            # Get current selection
            selection_model = self.selectionModel()
            if selection_model:
                # Use selectedRows() (fully-selected rows only) so the check matches what
                # _delete_record() requires.  selectedIndexes() includes partial cell
                # selections, which would cause _delete_record to find no selected rows.
                fully_selected_rows = {idx.row() for idx in selection_model.selectedRows()}

                # If the clicked row is not fully selected, select all its cells now so
                # that _delete_record() can find it via selectedRows().
                if row not in fully_selected_rows:
                    first_col = self.model.index(row, 0)
                    last_col = self.model.index(row, self.model.columnCount() - 1)
                    row_selection = QItemSelection(first_col, last_col)
                    selection_model.select(row_selection, QItemSelectionModel.Select | QItemSelectionModel.Rows)

            # Call delete_record which will handle all selected rows
            # This will delete the row that was right-clicked, plus any other selected rows
            parent._delete_record()

    def _add_rows_to_subcollection(self, clicked_row: int):
        """Collect selected record IDs and delegate to main_window for subcollection assignment."""
        # Build the set of record IDs to add
        selection_model = self.selectionModel()
        fully_selected_rows = set()
        if selection_model:
            fully_selected_rows = {idx.row() for idx in selection_model.selectedRows()}
        if clicked_row not in fully_selected_rows:
            fully_selected_rows.add(clicked_row)

        record_ids = []
        for row_idx in sorted(fully_selected_rows):
            record = self.model._get_record(row_idx)
            if record and record.get("id") is not None:
                record_ids.append(record["id"])

        if not record_ids:
            return

        # Delegate to main window
        parent = self.parent()
        while parent and not hasattr(parent, "_add_records_to_subcollection"):
            parent = parent.parent()
        if parent and hasattr(parent, "_add_records_to_subcollection"):
            parent._add_records_to_subcollection(record_ids)

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
                    self.model.store.add_record(new_record_data)
                    created_count += 1
                except Exception as e:
                    errors.append(f"Row {row_idx+1}: {str(e)}")
            else:
                # Update existing record
                record = self.model.filtered_records[target_row]
                record["id"]

                for col_idx, value in enumerate(row_data[:available_cols]):
                    field_col = start_col + col_idx - 1  # Adjust for primary key column
                    if 0 <= field_col < len(self.model.fields):
                        field = self.model.fields[field_col]
                        field["key"]

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
