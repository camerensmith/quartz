"""Dialog showing keyboard shortcuts"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class ShortcutsDialog(QDialog):
    """Dialog displaying all keyboard shortcuts"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Table for shortcuts
        self.table = QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        # Populate shortcuts
        shortcuts = self._get_shortcuts()
        self.table.setRowCount(len(shortcuts))

        for row, (action, shortcut) in enumerate(shortcuts):
            action_item = QTableWidgetItem(action)
            action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, action_item)

            shortcut_item = QTableWidgetItem(shortcut)
            shortcut_item.setFlags(shortcut_item.flags() & ~Qt.ItemIsEditable)
            # Right-align shortcut text
            shortcut_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, shortcut_item)

        # Adjust row height
        self.table.resizeRowsToContents()

        layout.addWidget(self.table)

        # Close button
        button_layout = QVBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _get_shortcuts(self):
        """Get list of all keyboard shortcuts"""
        return [
            # File Menu
            ("New Collection", "Ctrl+Shift+N"),
            ("Exit", "Ctrl+Q"),

            # Records
            ("New Record", "Ctrl+N"),
            ("Delete Record", "Delete"),

                # Edit
                ("Undo", "Ctrl+Z"),
                ("Redo", "Ctrl+Y"),
                ("Audit Trail", "Ctrl+Shift+Z"),

                # Fields
                ("Add Field", "Ctrl+G"),

                # Search (Placeholder)
                ("Search (Placeholder)", "Ctrl+F"),

            # Table View
            ("Paste", "Ctrl+V"),
            ("Tab", "Navigate to next cell"),
            ("Enter", "Navigate to next row"),
            ("Space", "Toggle checkbox (when focused)"),
            ("Type", "Start editing cell immediately"),

            # Tools
            ("Refresh", "F5"),
        ]

