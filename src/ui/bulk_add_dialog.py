"""Dialog for bulk adding blank rows"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QMessageBox,
)


class BulkAddDialog(QDialog):
    """Dialog for adding multiple blank records"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Add Records")
        self.setMinimumWidth(300)
        self.count = 1

        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())

        self._init_ui()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("How many blank records would you like to add?"))

        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Number of records:"))
        self.count_spin = QSpinBox()
        self.count_spin.setMinimum(1)
        self.count_spin.setMaximum(1000)
        self.count_spin.setValue(1)
        count_layout.addWidget(self.count_spin)
        count_layout.addStretch()
        layout.addLayout(count_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)

        add_btn = QPushButton("Add Records")
        add_btn.setDefault(True)
        add_btn.clicked.connect(self._accept_count)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(add_btn)
        layout.addLayout(button_layout)

    def _accept_count(self):
        """Accept and return count"""
        self.count = self.count_spin.value()
        self.accept()

    def get_count(self) -> int:
        """Get the number of records to add"""
        return self.count
