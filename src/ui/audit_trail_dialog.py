"""Audit Trail Dialog - shows undo/redo history"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont


class AuditTrailDialog(QDialog):
    """Dialog displaying the undo/redo audit trail"""

    def __init__(self, undo_history: list, redo_history: list, parent=None):
        super().__init__(parent)
        self._undo_history = undo_history  # oldest first, most-recent last
        self._redo_history = redo_history  # most-recently-undone first

        self.setWindowTitle("Audit Trail")
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Audit Trail")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel(
            "The table below lists recent changes. "
            "Select a row and click <b>Undo to here</b> to roll back to that point, "
            "or use <b>Ctrl+Z</b> / <b>Ctrl+Y</b> to step one change at a time."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Action", "Time"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)

        self._populate_table()
        layout.addWidget(self.table)

        # Legend
        legend_layout = QHBoxLayout()
        undo_dot = QLabel("■")
        undo_dot.setStyleSheet("color: #4CAF50; font-size: 14px;")
        legend_layout.addWidget(undo_dot)
        legend_layout.addWidget(QLabel("Can undo"))
        legend_layout.addSpacing(16)
        redo_dot = QLabel("■")
        redo_dot.setStyleSheet("color: #9E9E9E; font-size: 14px;")
        legend_layout.addWidget(redo_dot)
        legend_layout.addWidget(QLabel("Already undone (can redo)"))
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.undo_to_here_btn = QPushButton("Undo to here")
        self.undo_to_here_btn.setEnabled(False)
        self.undo_to_here_btn.setToolTip(
            "Undo all changes back to (and including) the selected action"
        )
        self.undo_to_here_btn.clicked.connect(self._undo_to_here)
        btn_layout.addWidget(self.undo_to_here_btn)

        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_table(self):
        """Fill the table with undo and redo entries."""
        # Build ordered list: undoable entries newest-first, then redo entries
        # We show entries newest-at-top so the user sees what happened most recently.
        undo_entries = list(reversed(self._undo_history))  # most recent first
        redo_entries = list(self._redo_history)            # most recently undone first

        rows = []
        # Undoable entries (green)
        for i, cmd in enumerate(undo_entries):
            rows.append(("undo", i, cmd))
        # Redo entries (grey) — already undone
        for i, cmd in enumerate(redo_entries):
            rows.append(("redo", i, cmd))

        self.table.setRowCount(len(rows))
        self._row_data = rows  # store for button handler

        green = QColor("#e8f5e9")
        grey = QColor("#f5f5f5")

        for row_idx, (kind, history_idx, cmd) in enumerate(rows):
            if kind == "undo":
                seq_num = str(len(undo_entries) - history_idx)
            else:
                seq_num = f"–{history_idx + 1}"
            num_item = QTableWidgetItem(seq_num)
            num_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

            desc_item = QTableWidgetItem(getattr(cmd, "description", str(cmd)))

            ts = getattr(cmd, "timestamp", None)
            if ts is not None:
                # Convert to local time for display
                local_ts = ts.astimezone()
                time_str = local_ts.strftime("%H:%M:%S")
            else:
                time_str = ""
            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

            bg = green if kind == "undo" else grey
            for item in (num_item, desc_item, time_item):
                item.setBackground(bg)

            self.table.setItem(row_idx, 0, num_item)
            self.table.setItem(row_idx, 1, desc_item)
            self.table.setItem(row_idx, 2, time_item)

        self.table.resizeRowsToContents()

    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.undo_to_here_btn.setEnabled(False)
            return
        row_idx = rows[0].row()
        kind = self._row_data[row_idx][0] if self._row_data else None
        # Only allow "Undo to here" for undoable entries
        self.undo_to_here_btn.setEnabled(kind == "undo")

    def _undo_to_here(self):
        """Undo all steps back to (and including) the selected row."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row_idx = rows[0].row()
        if not self._row_data:
            return
        kind, history_idx, _ = self._row_data[row_idx]
        if kind != "undo":
            return

        # history_idx is the index in the reversed undo_history list,
        # meaning we need to undo (history_idx + 1) times.
        steps = history_idx + 1
        self.done(steps)  # return the number of steps to undo
