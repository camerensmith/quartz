"""Update dialog shown when an update is available"""

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTextEdit, QVBoxLayout

from src.core.version import VERSION


class UpdateDialog(QDialog):
    """Dialog shown when an update is available"""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.ignored = False
        self._init_ui()

    def _init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Update Available")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel(f"Quartz v{self.update_info['version']} is available!")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                padding: 8px 0px;
            }
        """)
        layout.addWidget(title)

        # Current version
        current_label = QLabel(f"Current version: v{VERSION}")
        current_label.setStyleSheet("color: #666;")
        layout.addWidget(current_label)

        layout.addWidget(QLabel())  # Spacer

        # Changelog section
        changelog_label = QLabel("What's new:")
        changelog_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(changelog_label)

        changelog = QTextEdit()
        changelog.setPlainText(self.update_info.get('changelog', 'No changelog available.'))
        changelog.setReadOnly(True)
        changelog.setMaximumHeight(200)
        layout.addWidget(changelog)

        layout.addStretch()

        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)

        download_btn = QPushButton("Download Update")
        download_btn.setDefault(True)
        download_btn.clicked.connect(self.accept)
        button_layout.addWidget(download_btn)

        later_btn = QPushButton("Remind Me Later")
        later_btn.clicked.connect(self.reject)
        button_layout.addWidget(later_btn)

        ignore_btn = QPushButton(f"Ignore v{self.update_info['version']}")
        ignore_btn.setProperty("class", "secondary")
        ignore_btn.clicked.connect(self._ignore_version)
        button_layout.addWidget(ignore_btn)

        layout.addLayout(button_layout)

    def _ignore_version(self):
        """Mark this version as ignored"""
        self.ignored = True
        self.reject()

