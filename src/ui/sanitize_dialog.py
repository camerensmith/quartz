"""Sanitize dialog for finding and merging duplicate records"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.collection_store import CollectionStore


class SanitizeDialog(QDialog):
    """Dialog for finding and merging duplicate records in a collection"""

    def __init__(self, parent=None, store: CollectionStore | None = None, fields: list[dict] | None = None):
        super().__init__(parent)
        self.store = store
        self.fields = fields or []

        self.setWindowTitle("Sanitize")
        self.setMinimumWidth(680)
        self.setMinimumHeight(520)

        # Inherit stylesheet from parent
        if parent:
            self.setStyleSheet(parent.styleSheet())

        self._init_ui()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # --- Field selection row ---
        field_row = QHBoxLayout()
        field_row.setSpacing(8)

        find_dup_label = QLabel("Find Duplicates in")
        find_dup_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        field_row.addWidget(find_dup_label)

        self.field_combo = QComboBox()
        self.field_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for field in self.fields:
            if field.get("key") != "id":
                label = field.get("alias") or field.get("label") or field["key"]
                self.field_combo.addItem(label, field["key"])
        field_row.addWidget(self.field_combo)
        layout.addLayout(field_row)

        # --- Options group ---
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        options_layout.setContentsMargins(0, 8, 0, 8)
        options_layout.setSpacing(14)

        self.auto_merge_check = QCheckBox(
            "Automatically merge 1:1 matches \u2014 records that match in the selected field "
            "and all other fields are fully merged automatically; "
            "otherwise they are displayed for manual review"
        )
        self.auto_merge_check.setWordWrap(True)
        options_layout.addWidget(self.auto_merge_check)

        self.strict_check = QCheckBox("Strict matching  \u2014  case and space sensitive")
        options_layout.addWidget(self.strict_check)

        self.passive_flag_check = QCheckBox(
            "Automatically flag new records that 1:1 match existing records (passive)"
        )
        self.passive_flag_check.setToolTip(
            "When enabled, new records whose field values exactly match an existing record "
            "will be highlighted for review. This is a passive, non-destructive check."
        )
        options_layout.addWidget(self.passive_flag_check)

        layout.addWidget(options_widget)

        # Spacer / results area
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setAlignment(Qt.AlignTop)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_scroll.setWidget(self.results_container)
        layout.addWidget(self.results_scroll, stretch=1)

        # --- Button row ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.run_btn = QPushButton("Run")
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self._run_sanitize)
        button_layout.addWidget(self.run_btn)

        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "secondary")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _run_sanitize(self):
        """Run the sanitize / duplicate-finding operation"""
        if not self.store:
            QMessageBox.warning(self, "Error", "No collection is currently open.")
            return

        field_key = self.field_combo.currentData()
        if not field_key:
            QMessageBox.warning(self, "Error", "Please select a field to check for duplicates.")
            return

        strict = self.strict_check.isChecked()
        auto_merge = self.auto_merge_check.isChecked()

        # Retrieve all records
        try:
            records = self.store.list_records()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to read records:\n{exc}")
            return

        # Group records by the selected field value
        groups: dict[str, list[dict]] = {}
        for record in records:
            raw_value = record.get(field_key, "")
            key = str(raw_value) if raw_value is not None else ""
            if not strict:
                key = key.strip().lower()
            groups.setdefault(key, []).append(record)

        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        # Clear previous results
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not duplicates:
            no_result = QLabel("No duplicates found for the selected field.")
            no_result.setStyleSheet("color: #555; padding: 8px;")
            self.results_layout.addWidget(no_result)
            return

        merged_count = 0
        failed_ids: list[int] = []

        for field_value, dup_records in duplicates.items():
            if auto_merge and self._all_fields_match(dup_records):
                # Keep the first record, delete the rest
                for record in dup_records[1:]:
                    try:
                        self.store.delete_record(record["id"])
                        merged_count += 1
                    except Exception as exc:
                        failed_ids.append(record.get("id", "?"))
                        # Show the group so the user can handle it manually
                        self._add_group_to_results(field_value, dup_records, field_key,
                                                    note=f"Auto-merge failed: {exc}")
            else:
                # Display duplicate group
                self._add_group_to_results(field_value, dup_records, field_key)

        # Notify about auto-merges and failures
        if merged_count or failed_ids:
            msg_parts = []
            if merged_count:
                msg_parts.append(f"Auto-merged {merged_count} duplicate record(s).")
            if failed_ids:
                ids_str = ", ".join(str(i) for i in failed_ids)
                msg_parts.append(
                    f"Failed to merge {len(failed_ids)} record(s) (IDs: {ids_str}). "
                    "They are shown below for manual review."
                )
            QMessageBox.information(
                self,
                "Sanitize Complete",
                "\n".join(msg_parts)
            )

    def _add_group_to_results(self, field_value: str, dup_records: list[dict],
                               field_key: str, note: str | None = None):
        """Render a duplicate group into the results area"""
        header_text = (
            f"<b>Duplicate value:</b> \"{field_value}\"  "
            f"<span style='color:#888'>({len(dup_records)} records)</span>"
        )
        if note:
            header_text += f"  <span style='color:#c0392b'>[{note}]</span>"
        group_label = QLabel(header_text)
        group_label.setTextFormat(Qt.RichText)
        group_label.setStyleSheet("padding: 4px 0 2px 0;")
        self.results_layout.addWidget(group_label)

        for record in dup_records:
            record_id = record.get("id", "?")
            preview_parts = []
            for field in self.fields:
                fk = field.get("key")
                if fk and fk != "id" and fk != field_key:
                    val = record.get(fk, "")
                    if val:
                        lbl = field.get("alias") or field.get("label") or fk
                        preview_parts.append(f"{lbl}: {val}")
            preview = "  |  ".join(preview_parts[:4]) if preview_parts else "(no other fields)"
            row_label = QLabel(f"  \u2022 ID {record_id}  \u2014  {preview}")
            row_label.setStyleSheet("color: #444; padding: 1px 0 1px 12px;")
            self.results_layout.addWidget(row_label)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #e0e0e0;")
        self.results_layout.addWidget(separator)

    def _all_fields_match(self, records: list[dict]) -> bool:
        """Return True if all records are identical across every field (excluding id)"""
        if len(records) < 2:
            return True
        reference = {k: v for k, v in records[0].items() if k != "id"}
        for record in records[1:]:
            candidate = {k: v for k, v in record.items() if k != "id"}
            if candidate != reference:
                return False
        return True
