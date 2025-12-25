"""Custom table cell editors for different field types"""

from typing import Any, Optional

from PySide6.QtWidgets import (
    QStyledItemDelegate, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QDateEdit, QDateTimeEdit, QWidget, QStyleOptionButton, QApplication, QStyle,
    QCalendarWidget
)
from PySide6.QtCore import Qt, QModelIndex, QDate, QDateTime, QAbstractItemModel, QEvent, QTimer
from PySide6.QtGui import QColor, QPainter, QPen


class FieldTypeDelegate(QStyledItemDelegate):
    """Base delegate for field-type-specific editors"""
    
    def __init__(self, field: dict, parent=None):
        super().__init__(parent)
        self.field = field
        self.field_type = field.get("type", "text")
    
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
    
    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget:
        """Create appropriate editor based on field type"""
        # For checkboxes, don't create an editor - handle clicks directly via editorEvent
        if self.field_type == "checkbox":
            return None
        
        # Ensure editor is positioned correctly within the cell
        editor = None
        if self.field_type == "integer":
            # Use QLineEdit with number validation instead of QSpinBox (no arrows)
            editor = QLineEdit(parent)
            editor.setPlaceholderText("")  # Clear any placeholder
            # Set input method hints for numeric keyboard on mobile
            editor.setInputMethodHints(Qt.InputMethodHint.ImhDigitsOnly)
            # Add validator for integers
            from PySide6.QtGui import QIntValidator
            validator = QIntValidator()
            editor.setValidator(validator)
        elif self.field_type == "decimal":
            # Use QLineEdit with number validation instead of QDoubleSpinBox (no arrows)
            editor = QLineEdit(parent)
            editor.setPlaceholderText("")  # Clear any placeholder
            editor.setInputMethodHints(Qt.InputMethodHint.ImhFormattedNumbersOnly)
            # Add validator for decimals
            from PySide6.QtGui import QDoubleValidator
            validator = QDoubleValidator()
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            editor.setValidator(validator)
        
        elif self.field_type == "date":
            editor = QDateEdit(parent)
            editor.setCalendarPopup(True)
            editor.setDate(QDate.currentDate())
            # Configure calendar to show full 3-character day abbreviations
            calendar = editor.calendarWidget()
            if calendar:
                calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
                # Use ShortDayNames format (3-character abbreviations)
                calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
            # Apply date format from config
            date_format = self._get_date_format()
            if date_format:
                editor.setDisplayFormat(date_format)
            return editor
        
        elif self.field_type == "datetime":
            editor = QDateTimeEdit(parent)
            editor.setCalendarPopup(True)
            editor.setDateTime(QDateTime.currentDateTime())
            # Configure calendar to show full 3-character day abbreviations
            calendar = editor.calendarWidget()
            if calendar:
                calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
                # Use ShortDayNames format (3-character abbreviations)
                calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
            # Apply datetime format from config
            datetime_format = self._get_datetime_format()
            if datetime_format:
                editor.setDisplayFormat(datetime_format)
            return editor
        
        elif self.field_type in ("select", "single-select"):
            editor = QComboBox(parent)
            options = self.field.get("options", [])
            if isinstance(options, str):
                import json
                try:
                    options = json.loads(options)
                except:
                    options = []
            if isinstance(options, list) and len(options) > 0:
                editor.addItems([str(opt) for opt in options])
            else:
                # If no options, add a placeholder
                editor.addItem("(No options)")
            editor.setEditable(False)
            # Ensure the combo box is interactive and can be clicked
            editor.setEnabled(True)
            editor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            return editor
        
        # Default: text editor
        editor = QLineEdit(parent)
        
        # Ensure no placeholder text is set (we want actual values, not placeholders)
        if isinstance(editor, QLineEdit):
            editor.setPlaceholderText("")  # Clear any placeholder
        
        # Apply minimal styling to all editors - opaque background to hide cell content
        if editor and isinstance(editor, (QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QDateTimeEdit)):
            # Opaque white background to hide the cell's displayed value while editing
            # No border, minimal styling, but opaque to prevent "shadow" of old value
            editor.setStyleSheet("""
                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QDateTimeEdit {
                    background-color: #ffffff;
                    border: none;
                    padding: 0px;
                    color: #212121;
                    selection-background-color: rgba(156, 39, 176, 0.5);
                    selection-color: #212121;
                }
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, 
                QComboBox:focus, QDateEdit:focus, QDateTimeEdit:focus {
                    border: none;
                    background-color: #ffffff;
                    color: #212121;
                }
                QComboBox::drop-down {
                    border: 1px solid #e0e0e0;
                    border-radius: 2px;
                    width: 20px;
                }
                QComboBox::drop-down:hover {
                    border: 1px solid rgba(156, 39, 176, 0.5);
                }
                QComboBox::down-arrow {
                    width: 12px;
                    height: 12px;
                    border-left: 6px solid transparent;
                    border-right: 6px solid transparent;
                    border-top: 8px solid #424242;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #424242;
                    selection-background-color: rgba(156, 39, 176, 0.3);
                    selection-color: #424242;
                }
            """)
        
        return editor
    
    def updateEditorGeometry(self, editor: QWidget, option, index: QModelIndex):
        """Update editor geometry to match cell exactly - stay within cell bounds"""
        # Position editor to exactly match the cell bounds - no overflow
        rect = option.rect
        
        # Check if this cell is selected/current (has a border)
        view = None
        parent = self.parent()
        while parent:
            if hasattr(parent, 'selectionModel'):
                view = parent
                break
            parent = parent.parent() if hasattr(parent, 'parent') else None
        
        is_selected_or_current = False
        if view and view.selectionModel():
            is_selected = view.selectionModel().isSelected(index)
            is_current = (index == view.currentIndex())
            is_selected_or_current = is_selected or is_current
        
        # For text editors (including numeric fields now using QLineEdit)
        if isinstance(editor, (QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QDateTimeEdit)):
            if is_selected_or_current:
                # Border is 2px wide, drawn at 1px inset, so editor should be inside the border
                # Use minimal padding to stay within border (3px from edges to account for border)
                editor.setGeometry(rect.adjusted(3, 1, -3, -1))
            else:
                # No border, use minimal padding to stay within cell
                editor.setGeometry(rect.adjusted(1, 0, -1, 0))
        else:
            # For checkboxes and other widgets, use exact cell bounds
            editor.setGeometry(rect)
    
    def setEditorData(self, editor: QWidget, index: QModelIndex):
        """Set editor value from model"""
        value = index.model().data(index, Qt.EditRole)
        
        if isinstance(editor, QLineEdit):
            # For numeric fields, display the value as-is
            if self.field_type == "integer":
                # Display integer value
                try:
                    editor.setText(str(int(value)) if value else "")
                except (ValueError, TypeError):
                    editor.setText(str(value) if value else "")
            elif self.field_type == "decimal":
                # Display decimal value
                try:
                    editor.setText(str(float(value)) if value else "")
                except (ValueError, TypeError):
                    editor.setText(str(value) if value else "")
            else:
                # Regular text field
                editor.setText(str(value) if value else "")
            
            # Select all text when editing starts (highlight current value)
            # Select immediately after setting text
            editor.selectAll()
            
            # Use QTimer to ensure selection happens after editor is fully shown and focused
            def select_all_text():
                try:
                    if editor and editor.isVisible() and editor.hasFocus():
                        editor.selectAll()
                except RuntimeError:
                    pass
            QTimer.singleShot(0, select_all_text)
            QTimer.singleShot(50, select_all_text)  # Backup to ensure it happens
        elif isinstance(editor, QSpinBox):
            try:
                editor.setValue(int(value) if value else 0)
            except (ValueError, TypeError):
                editor.setValue(0)
        elif isinstance(editor, QDoubleSpinBox):
            try:
                editor.setValue(float(value) if value else 0.0)
            except (ValueError, TypeError):
                editor.setValue(0.0)
        elif isinstance(editor, QCheckBox):
            if isinstance(value, bool):
                editor.setChecked(value)
            elif isinstance(value, str):
                editor.setChecked(value.lower() in ("true", "1", "yes", "on"))
            else:
                editor.setChecked(bool(value))
        elif isinstance(editor, QDateEdit):
            if value:
                try:
                    from datetime import datetime
                    if isinstance(value, str):
                        dt = datetime.fromisoformat(value)
                    else:
                        dt = value
                    editor.setDate(QDate(dt.year, dt.month, dt.day))
                except:
                    editor.setDate(QDate.currentDate())
            else:
                editor.setDate(QDate.currentDate())
        elif isinstance(editor, QDateTimeEdit):
            if value:
                try:
                    from datetime import datetime
                    if isinstance(value, str):
                        dt = datetime.fromisoformat(value)
                    else:
                        dt = value
                    editor.setDateTime(QDateTime(dt))
                except:
                    editor.setDateTime(QDateTime.currentDateTime())
            else:
                editor.setDateTime(QDateTime.currentDateTime())
        elif isinstance(editor, QComboBox):
            if value:
                idx = editor.findText(str(value))
                if idx >= 0:
                    editor.setCurrentIndex(idx)
                else:
                    # Value not in options, set to first item or empty
                    if editor.count() > 0:
                        editor.setCurrentIndex(0)
            else:
                # No value, set to first item if available
                if editor.count() > 0:
                    editor.setCurrentIndex(0)
            # Ensure combo box is enabled and can receive focus
            editor.setEnabled(True)
            editor.setFocus()
    
    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        """Set model value from editor"""
        if isinstance(editor, QLineEdit):
            text = editor.text().strip()
            # Validate numeric fields
            if self.field_type == "integer":
                # Validate integer
                try:
                    value = int(text) if text else ""
                except ValueError:
                    # Invalid integer - return empty or keep as text for validation to catch
                    value = text
            elif self.field_type == "decimal":
                # Validate decimal
                try:
                    value = float(text) if text else ""
                except ValueError:
                    # Invalid decimal - return empty or keep as text for validation to catch
                    value = text
            else:
                # Regular text field
                value = text
        elif isinstance(editor, QSpinBox):
            value = editor.value()
        elif isinstance(editor, QDoubleSpinBox):
            value = editor.value()
        elif isinstance(editor, QCheckBox):
            value = editor.isChecked()
        elif isinstance(editor, QDateEdit):
            date = editor.date()
            value = date.toString(Qt.DateFormat.ISODate)
        elif isinstance(editor, QDateTimeEdit):
            dt = editor.dateTime()
            value = dt.toString(Qt.DateFormat.ISODate)
        elif isinstance(editor, QComboBox):
            value = editor.currentText()
        else:
            value = ""
        
        model.setData(index, value, Qt.EditRole)
    
    def editorEvent(self, event: QEvent, model: QAbstractItemModel, option, index: QModelIndex) -> bool:
        """Handle editor events - for checkboxes, toggle on click or spacebar"""
        if self.field_type == "checkbox":
            # Handle mouse clicks
            if event.type() == QEvent.Type.MouseButtonPress or event.type() == QEvent.Type.MouseButtonDblClick:
                # Toggle checkbox value
                value = model.data(index, Qt.EditRole)
                checked = False
                
                if isinstance(value, bool):
                    checked = value
                elif isinstance(value, str):
                    checked = value.lower() in ("true", "1", "yes", "on")
                else:
                    checked = bool(value)
                
                # Toggle the value
                new_value = not checked
                model.setData(index, new_value, Qt.EditRole)
                return True
        
        return super().editorEvent(event, model, option, index)
    
    def _is_dark_mode(self, view):
        """Detect if we're in dark mode by checking table background color"""
        if not view:
            return False
        bg_color = view.palette().color(view.backgroundRole())
        # Dark mode typically has background RGB values < 128
        return bg_color.red() < 128 and bg_color.green() < 128 and bg_color.blue() < 128
    
    def paint(self, painter: QPainter, option, index: QModelIndex):
        """Custom paint for checkbox fields and selected cell borders"""
        # Disable default focus indicator (dotted rectangle around text)
        from PySide6.QtWidgets import QStyle
        option.state &= ~QStyle.State_HasFocus
        
        # Check if this cell is selected/current - we'll draw border after parent paint
        view = None
        parent = self.parent()
        while parent:
            if hasattr(parent, 'selectionModel'):
                view = parent
                break
            parent = parent.parent() if hasattr(parent, 'parent') else None
        
        should_draw_border = False
        if view and view.selectionModel():
            is_selected = view.selectionModel().isSelected(index)
            is_current = (index == view.currentIndex())
            should_draw_border = (is_selected or is_current)
        
        if self.field_type == "checkbox":
            value = index.model().data(index, Qt.DisplayRole)
            checked = False
            
            if isinstance(value, bool):
                checked = value
            elif isinstance(value, str):
                checked = value.lower() in ("true", "1", "yes", "on")
            else:
                checked = bool(value)
            
            # Enable anti-aliasing for smoother rendering
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            
            # Draw checkbox - ensure it fits within cell bounds
            cell_rect = option.rect
            checkbox_size = min(20, min(cell_rect.width() - 4, cell_rect.height() - 4))  # Leave 2px padding on each side
            checkbox_size = max(16, checkbox_size)  # Minimum 16px for visibility
            
            checkbox_rect = cell_rect
            checkbox_rect.setWidth(checkbox_size)
            checkbox_rect.setHeight(checkbox_size)
            checkbox_rect.moveLeft(cell_rect.left() + (cell_rect.width() - checkbox_size) // 2)
            checkbox_rect.moveTop(cell_rect.top() + (cell_rect.height() - checkbox_size) // 2)
            
            checkbox_option = QStyleOptionButton()
            checkbox_option.rect = checkbox_rect
            checkbox_option.state = QStyle.StateFlag.State_Enabled
            if checked:
                checkbox_option.state |= QStyle.StateFlag.State_On
            else:
                checkbox_option.state |= QStyle.StateFlag.State_Off
            
            QApplication.style().drawControl(QStyle.ControlElement.CE_CheckBox, checkbox_option, painter)
        else:
            # Default painting for other types
            super().paint(painter, option, index)
        
        # Draw border AFTER parent paint so it appears on top (for both checkbox and other field types)
        if should_draw_border:
            painter.save()
            # Use lighter grey for dark mode, black for light mode
            if self._is_dark_mode(view):
                border_color = QColor("#f5f5f5")  # Very light grey, almost white for dark mode
            else:
                border_color = QColor(Qt.black)
            pen = QPen(border_color, 2)  # 2px border - thicker for better visibility
            painter.setPen(pen)
            # Draw border rectangle around the entire cell
            border_rect = option.rect.adjusted(1, 1, -1, -1)
            painter.drawRect(border_rect)
            painter.restore()


class ValidationErrorDelegate(QStyledItemDelegate):
    """Delegate that highlights validation errors"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.error_cells = {}  # {(row, col): error_message}
    
    def set_error(self, row: int, col: int, message: str):
        """Mark a cell as having an error"""
        self.error_cells[(row, col)] = message
    
    def clear_error(self, row: int, col: int):
        """Clear error for a cell"""
        self.error_cells.pop((row, col), None)
    
    def clear_all_errors(self):
        """Clear all errors"""
        self.error_cells.clear()
    
    def _is_dark_mode(self, view):
        """Detect if we're in dark mode by checking table background color"""
        if not view:
            return False
        bg_color = view.palette().color(view.backgroundRole())
        # Dark mode typically has background RGB values < 128
        return bg_color.red() < 128 and bg_color.green() < 128 and bg_color.blue() < 128
    
    def paint(self, painter: QPainter, option, index: QModelIndex):
        """Paint with error highlighting and selected cell border"""
        # Disable default focus indicator (dotted rectangle around text)
        from PySide6.QtWidgets import QStyle
        option.state &= ~QStyle.State_HasFocus
        
        # Check if this cell is selected/current and draw border
        view = None
        parent = self.parent()
        while parent:
            if hasattr(parent, 'selectionModel'):
                view = parent
                break
            parent = parent.parent() if hasattr(parent, 'parent') else None
        
        if view and view.selectionModel():
            is_selected = view.selectionModel().isSelected(index)
            is_current = (index == view.currentIndex())
            
            if is_selected or is_current:
                # Draw border around entire cell
                painter.save()
                # Use lighter grey for dark mode, black for light mode
                if self._is_dark_mode(view):
                    border_color = QColor("#f5f5f5")  # Very light grey, almost white for dark mode
                else:
                    border_color = QColor(Qt.black)
                pen = QPen(border_color, 3)  # 3px border - thicker for better visibility
                painter.setPen(pen)
                # Draw border rectangle around the entire cell
                border_rect = option.rect.adjusted(1, 1, -1, -1)
                painter.drawRect(border_rect)
                painter.restore()
        
        # Check if this cell has an error
        row = index.row()
        col = index.column()
        
        if (row, col) in self.error_cells:
            # Draw red border
            painter.save()
            painter.setPen(QColor(255, 0, 0, 200))
            painter.setBrush(QColor(255, 240, 240, 100))
            painter.drawRect(option.rect)
            painter.restore()
        
        # Call parent paint
        super().paint(painter, option, index)
