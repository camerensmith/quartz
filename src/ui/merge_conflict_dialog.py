"""Dialog for resolving merge conflicts"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class MergeConflictDialog(QDialog):
    """Dialog for resolving merge conflicts"""

    def __init__(self, parent=None, conflicts: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Merge Conflicts")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())

        self.conflicts = conflicts or {}
        self.resolutions = {}  # Store user's conflict resolutions
        self._init_ui()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            "The following conflicts were detected during merge. "
            "Please resolve each conflict by choosing an action:"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Field conflicts (same key)
        if self.conflicts.get("field_conflicts"):
            field_group = QGroupBox("Field Conflicts (Same Key)")
            field_layout = QVBoxLayout()

            info_text = "Fields with the same key exist in both collections. Choose how to resolve:"
            info_label = QLabel(info_text)
            info_label.setWordWrap(True)
            field_layout.addWidget(info_label)

            self.field_table = QTableWidget()
            self.field_table.setColumnCount(5)
            self.field_table.setHorizontalHeaderLabels(["Field Key", "Source", "Target", "Differences", "Action"])
            self.field_table.horizontalHeader().setStretchLastSection(True)

            field_conflicts = self.conflicts["field_conflicts"]
            self.field_table.setRowCount(len(field_conflicts))

            for row, conflict in enumerate(field_conflicts):
                # Field key
                key_item = QTableWidgetItem(conflict["key"])
                key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
                self.field_table.setItem(row, 0, key_item)

                # Source field info
                source_alias = conflict['source'].get('alias', conflict['source'].get('label', ''))
                source_text = f"{source_alias} ({conflict['source']['type']})"
                source_item = QTableWidgetItem(source_text)
                source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                self.field_table.setItem(row, 1, source_item)

                # Target field info
                target_alias = conflict['target'].get('alias', conflict['target'].get('label', ''))
                target_text = f"{target_alias} ({conflict['target']['type']})"
                target_item = QTableWidgetItem(target_text)
                target_item.setFlags(target_item.flags() & ~Qt.ItemIsEditable)
                self.field_table.setItem(row, 2, target_item)

                # Differences
                diff_parts = []
                if conflict.get("alias_differs"):
                    diff_parts.append("Alias differs")
                if conflict.get("type_differs"):
                    diff_parts.append("Type differs")
                diff_text = ", ".join(diff_parts) if diff_parts else "Same properties"
                diff_item = QTableWidgetItem(diff_text)
                diff_item.setFlags(diff_item.flags() & ~Qt.ItemIsEditable)
                self.field_table.setItem(row, 3, diff_item)

                # Action combo
                action_combo = QComboBox()
                action_combo.addItems([
                    "Skip (Keep Target)",
                    "Rename Source Field",
                    "Replace Target Field"
                ])
                self.field_table.setCellWidget(row, 4, action_combo)

                # Store resolution
                self.resolutions[f"field_{conflict['key']}"] = {
                    "type": "field",
                    "key": conflict["key"],
                    "action": action_combo
                }

            self.field_table.resizeColumnsToContents()
            field_layout.addWidget(self.field_table)
            field_group.setLayout(field_layout)
            layout.addWidget(field_group)

        # Field alias conflicts (same alias, different key)
        if self.conflicts.get("field_alias_conflicts"):
            alias_group = QGroupBox("Field Alias Conflicts (Same Alias, Different Key)")
            alias_layout = QVBoxLayout()

            info_text = "Fields with the same alias but different keys exist. These can be merged or kept separate:"
            info_label = QLabel(info_text)
            info_label.setWordWrap(True)
            alias_layout.addWidget(info_label)

            self.alias_table = QTableWidget()
            self.alias_table.setColumnCount(4)
            self.alias_table.setHorizontalHeaderLabels(["Alias", "Source Key", "Target Key", "Action"])
            self.alias_table.horizontalHeader().setStretchLastSection(True)

            alias_conflicts = self.conflicts["field_alias_conflicts"]
            self.alias_table.setRowCount(len(alias_conflicts))

            for row, conflict in enumerate(alias_conflicts):
                # Alias
                alias_item = QTableWidgetItem(conflict["alias"])
                alias_item.setFlags(alias_item.flags() & ~Qt.ItemIsEditable)
                self.alias_table.setItem(row, 0, alias_item)

                # Source key
                source_key_item = QTableWidgetItem(conflict["source_key"])
                source_key_item.setFlags(source_key_item.flags() & ~Qt.ItemIsEditable)
                self.alias_table.setItem(row, 1, source_key_item)

                # Target key
                target_key_item = QTableWidgetItem(conflict["target_key"])
                target_key_item.setFlags(target_key_item.flags() & ~Qt.ItemIsEditable)
                self.alias_table.setItem(row, 2, target_key_item)

                # Action combo
                action_combo = QComboBox()
                action_combo.addItems([
                    "Keep Separate (Rename Source)",
                    "Merge Into Target Field"
                ])
                self.alias_table.setCellWidget(row, 3, action_combo)

                # Store resolution
                self.resolutions[f"alias_{conflict['source_key']}"] = {
                    "type": "alias",
                    "source_key": conflict["source_key"],
                    "target_key": conflict["target_key"],
                    "action": action_combo
                }

            self.alias_table.resizeColumnsToContents()
            alias_layout.addWidget(self.alias_table)
            alias_group.setLayout(alias_layout)
            layout.addWidget(alias_group)

        # Record ID conflicts
        if self.conflicts.get("record_id_conflicts"):
            record_group = QGroupBox("Record ID Conflicts")
            record_layout = QVBoxLayout()

            record_label = QLabel(
                f"Found {len(self.conflicts['record_id_conflicts'])} record(s) with conflicting IDs. "
                "These will be assigned new IDs in the target collection."
            )
            record_label.setWordWrap(True)
            record_layout.addWidget(record_label)

            record_group.setLayout(record_layout)
            layout.addWidget(record_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("Resolve & Merge")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._resolve_and_accept)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)

    def _resolve_and_accept(self):
        """Collect resolutions and accept"""
        # Collect field resolutions
        for _key, resolution in self.resolutions.items():
            if resolution["type"] == "field":
                action = resolution["action"].currentText()
                if action == "Rename Source Field":
                    # Prompt for new name
                    from PySide6.QtWidgets import QInputDialog
                    new_key, ok = QInputDialog.getText(
                        self,
                        "Rename Field",
                        f"Enter new key for field '{resolution['key']}':",
                        text=f"{resolution['key']}_merged"
                    )
                    if ok and new_key and new_key.strip():
                        resolution["new_key"] = new_key.strip()
                    else:
                        QMessageBox.warning(self, "Error", "Field rename is required")
                        return
            elif resolution["type"] == "alias":
                action = resolution["action"].currentText()
                if action == "Keep Separate (Rename Source)":
                    # Prompt for new key
                    from PySide6.QtWidgets import QInputDialog
                    new_key, ok = QInputDialog.getText(
                        self,
                        "Rename Field",
                        f"Enter new key for source field '{resolution['source_key']}':",
                        text=f"{resolution['source_key']}_merged"
                    )
                    if ok and new_key and new_key.strip():
                        resolution["new_key"] = new_key.strip()
                    else:
                        QMessageBox.warning(self, "Error", "Field rename is required")
                        return

        self.accept()

    def get_resolutions(self) -> dict:
        """Get conflict resolutions"""
        resolutions = {}

        for key, resolution in self.resolutions.items():
            if resolution["type"] == "field":
                action = resolution["action"].currentText()
                resolutions[key] = {
                    "action": action,
                    "new_key": resolution.get("new_key")
                }
            elif resolution["type"] == "alias":
                action = resolution["action"].currentText()
                resolutions[key] = {
                    "action": action,
                    "new_key": resolution.get("new_key")
                }

        return resolutions
