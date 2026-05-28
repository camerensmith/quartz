"""Dialog for comparing and syncing two workspaces"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.workspace import Workspace
from src.core.workspace_sync import CollectionDiff, compare_workspaces, sync_collection

_DIR_LOCAL_TO_CLOUD = "Local → Cloud"
_DIR_CLOUD_TO_LOCAL = "Cloud → Local"


def _fmt_size(size: int | None) -> str:
    if size is None:
        return "—"
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 ** 2:.1f} MB"


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    return iso.replace("T", " ")[:16]


class WorkspaceSyncDialog(QDialog):
    """Shows discrepancies between two workspaces and lets the user cherry-pick syncs."""

    _COL_INCLUDE = 0
    _COL_NAME = 1
    _COL_LOCAL_UPDATED = 2
    _COL_CLOUD_UPDATED = 3
    _COL_LOCAL_RECORDS = 4
    _COL_CLOUD_RECORDS = 5
    _COL_LOCAL_FIELDS = 6
    _COL_CLOUD_FIELDS = 7
    _COL_LOCAL_SIZE = 8
    _COL_CLOUD_SIZE = 9
    _COL_DIRECTION = 10

    _HEADERS = [
        "Sync",
        "Collection",
        "Local\nUpdated",
        "Cloud\nUpdated",
        "Local\nRecords",
        "Cloud\nRecords",
        "Local\nFields",
        "Cloud\nFields",
        "Local\nSize",
        "Cloud\nSize",
        "Direction",
    ]

    def __init__(
        self,
        parent=None,
        local_path: Path | None = None,
        cloud_path: Path | None = None,
        config=None,
    ):
        super().__init__(parent)
        self.local_path = Path(local_path) if local_path else None
        self.cloud_path = Path(cloud_path) if cloud_path else None
        self._diffs: list[CollectionDiff] = []

        self.setWindowTitle("Sync Workspaces")
        self.setMinimumWidth(940)
        self.setMinimumHeight(560)

        if config:
            from src.ui.styles import AppStyles
            color_scheme = config.get("color_scheme", "default")
            mode = config.get("mode", "light")
            self.setStyleSheet(AppStyles.get_theme(color_scheme=color_scheme, mode=mode))

        self._init_ui()
        self._load_diff()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Workspace path display
        paths_group = QGroupBox("Workspaces Being Compared")
        paths_layout = QVBoxLayout()

        local_row = QHBoxLayout()
        local_row.addWidget(QLabel("<b>Local:</b>"))
        self._local_path_label = QLabel(str(self.local_path) if self.local_path else "—")
        self._local_path_label.setWordWrap(True)
        local_row.addWidget(self._local_path_label, 1)
        paths_layout.addLayout(local_row)

        cloud_row = QHBoxLayout()
        cloud_row.addWidget(QLabel("<b>Cloud:</b>"))
        self._cloud_path_label = QLabel(str(self.cloud_path) if self.cloud_path else "—")
        self._cloud_path_label.setWordWrap(True)
        cloud_row.addWidget(self._cloud_path_label, 1)
        paths_layout.addLayout(cloud_row)

        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)

        # Default direction
        direction_row = QHBoxLayout()
        direction_row.addWidget(QLabel("Default direction for all collections:"))
        self._default_dir_combo = QComboBox()
        self._default_dir_combo.addItems([_DIR_LOCAL_TO_CLOUD, _DIR_CLOUD_TO_LOCAL])
        self._default_dir_combo.currentTextChanged.connect(self._apply_default_direction)
        direction_row.addWidget(self._default_dir_combo)
        direction_row.addStretch()
        layout.addLayout(direction_row)

        # Comparison table
        self._table = QTableWidget(0, len(self._HEADERS))
        self._table.setHorizontalHeaderLabels(self._HEADERS)
        self._table.horizontalHeader().setSectionResizeMode(self._COL_NAME, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_DIRECTION, QHeaderView.ResizeToContents
        )
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # Warning
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        warn_label = QLabel(
            "⚠️  <b>Warning:</b> Syncing will <b>overwrite</b> existing collection data in "
            "the target workspace. This cannot be undone. Ensure you have backups before "
            "proceeding. Changes to the local workspace will be visible after restarting."
        )
        warn_label.setWordWrap(True)
        warn_label.setStyleSheet("color: #b85c00;")
        layout.addWidget(warn_label)

        self._confirm_check = QCheckBox(
            "I understand that synced collections will be overwritten in the target workspace."
        )
        self._confirm_check.stateChanged.connect(self._update_sync_btn)
        layout.addWidget(self._confirm_check)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._sync_btn = QPushButton("Sync")
        self._sync_btn.setEnabled(False)
        self._sync_btn.clicked.connect(self._do_sync)
        btn_row.addWidget(self._sync_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_diff(self):
        if not self.local_path or not self.cloud_path:
            return
        if not self.local_path.exists() or not self.cloud_path.exists():
            QMessageBox.warning(
                self,
                "Path Not Found",
                "One or both workspace paths do not exist. Please check your settings.",
            )
            return

        try:
            local_ws = Workspace(self.local_path)
            cloud_ws = Workspace(self.cloud_path)
            self._diffs = compare_workspaces(local_ws, cloud_ws)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not compare workspaces:\n{exc}")
            return

        if not self._diffs:
            QMessageBox.information(
                self,
                "No Collections",
                "No collections were found in either workspace.",
            )
            return

        self._table.setRowCount(len(self._diffs))
        for row, diff in enumerate(self._diffs):
            self._populate_row(row, diff)

        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setSectionResizeMode(self._COL_NAME, QHeaderView.Stretch)

    def _populate_row(self, row: int, diff: CollectionDiff):
        # Include checkbox (centred in a wrapper widget)
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk = QCheckBox()
        chk.setChecked(True)
        chk_layout.addWidget(chk)
        chk_layout.setAlignment(Qt.AlignCenter)
        chk_layout.setContentsMargins(0, 0, 0, 0)
        self._table.setCellWidget(row, self._COL_INCLUDE, chk_widget)

        # Helper: coloured item for mismatches
        def _item(text: str, highlight: bool = False) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            if highlight:
                item.setForeground(Qt.red)
            return item

        self._table.setItem(row, self._COL_NAME, QTableWidgetItem(diff.name))
        self._table.setItem(row, self._COL_LOCAL_UPDATED, _item(_fmt_date(diff.local_updated_at)))
        self._table.setItem(row, self._COL_CLOUD_UPDATED, _item(_fmt_date(diff.cloud_updated_at)))

        # Records (highlight differences)
        local_recs = str(diff.local_record_count) if diff.local_record_count is not None else "—"
        cloud_recs = str(diff.cloud_record_count) if diff.cloud_record_count is not None else "—"
        recs_differ = (
            diff.in_local
            and diff.in_cloud
            and diff.local_record_count != diff.cloud_record_count
        )
        self._table.setItem(row, self._COL_LOCAL_RECORDS, _item(local_recs, recs_differ))
        self._table.setItem(row, self._COL_CLOUD_RECORDS, _item(cloud_recs, recs_differ))

        # Fields (highlight differences)
        local_flds = str(diff.local_field_count) if diff.local_field_count is not None else "—"
        cloud_flds = str(diff.cloud_field_count) if diff.cloud_field_count is not None else "—"
        flds_differ = (
            diff.in_local
            and diff.in_cloud
            and diff.local_field_count != diff.cloud_field_count
        )
        self._table.setItem(row, self._COL_LOCAL_FIELDS, _item(local_flds, flds_differ))
        self._table.setItem(row, self._COL_CLOUD_FIELDS, _item(cloud_flds, flds_differ))

        self._table.setItem(row, self._COL_LOCAL_SIZE, _item(_fmt_size(diff.local_size_bytes)))
        self._table.setItem(row, self._COL_CLOUD_SIZE, _item(_fmt_size(diff.cloud_size_bytes)))

        # Direction combo — constrain if collection exists only on one side
        dir_combo = QComboBox()
        if diff.in_local and not diff.in_cloud:
            dir_combo.addItem(_DIR_LOCAL_TO_CLOUD)
            dir_combo.setEnabled(False)
        elif diff.in_cloud and not diff.in_local:
            dir_combo.addItem(_DIR_CLOUD_TO_LOCAL)
            dir_combo.setEnabled(False)
        else:
            dir_combo.addItems([_DIR_LOCAL_TO_CLOUD, _DIR_CLOUD_TO_LOCAL])
            dir_combo.setCurrentText(self._default_dir_combo.currentText())
        self._table.setCellWidget(row, self._COL_DIRECTION, dir_combo)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_default_direction(self, direction: str):
        """Push the chosen default direction to all non-constrained rows."""
        for row in range(self._table.rowCount()):
            combo = self._table.cellWidget(row, self._COL_DIRECTION)
            if isinstance(combo, QComboBox) and combo.isEnabled() and combo.count() == 2:
                combo.setCurrentText(direction)

    def _update_sync_btn(self):
        self._sync_btn.setEnabled(self._confirm_check.isChecked())

    def _get_row_checkbox(self, row: int) -> QCheckBox | None:
        cell = self._table.cellWidget(row, self._COL_INCLUDE)
        if cell:
            return cell.findChild(QCheckBox)
        return None

    # ------------------------------------------------------------------
    # Sync execution
    # ------------------------------------------------------------------

    def _do_sync(self):
        if not self._confirm_check.isChecked():
            return

        # Build plan
        plan: list[tuple[str, str]] = []
        for row, diff in enumerate(self._diffs):
            chk = self._get_row_checkbox(row)
            if not (chk and chk.isChecked()):
                continue
            combo = self._table.cellWidget(row, self._COL_DIRECTION)
            if isinstance(combo, QComboBox):
                plan.append((diff.name, combo.currentText()))

        if not plan:
            QMessageBox.information(
                self, "Nothing to Sync", "No collections were selected for sync."
            )
            return

        # Final confirmation with full summary
        summary = "\n".join(f"  • {name}  ({direction})" for name, direction in plan)
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirm Sync")
        confirm.setIcon(QMessageBox.Warning)
        confirm.setText(
            f"You are about to sync {len(plan)} collection(s):\n\n{summary}\n\n"
            "Data in the <b>target</b> workspace will be <b>permanently overwritten</b>.\n"
            "This cannot be undone. Proceed?"
        )
        confirm.setTextFormat(Qt.RichText)
        confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        confirm.setDefaultButton(QMessageBox.Cancel)
        if confirm.exec() != QMessageBox.Yes:
            return

        # Execute
        local_ws = Workspace(self.local_path)
        cloud_ws = Workspace(self.cloud_path)
        errors: list[str] = []
        for name, direction in plan:
            try:
                if direction == _DIR_LOCAL_TO_CLOUD:
                    sync_collection(name, local_ws, cloud_ws)
                else:
                    sync_collection(name, cloud_ws, local_ws)
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        if errors:
            QMessageBox.warning(
                self,
                "Sync Completed with Errors",
                "Some collections could not be synced:\n\n" + "\n".join(errors),
            )
        else:
            QMessageBox.information(
                self,
                "Sync Complete",
                f"Successfully synced {len(plan)} collection(s).\n\n"
                "Restart the application to see changes in the local workspace.",
            )
        self.accept()
