"""Progress dialog for update download and installation"""

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from src.core.update_downloader import UpdateDownloader


class UpdateDownloadThread(QThread):
    """Thread for downloading update in background"""
    progress = Signal(int, int)  # downloaded, total
    finished = Signal(Path)  # path to downloaded file
    error = Signal(str)  # error message

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self):
        """Download the update"""
        try:
            def progress_callback(downloaded, total):
                self.progress.emit(downloaded, total)

            downloaded_file = UpdateDownloader.download_update(
                self.download_url,
                progress_callback
            )
            self.finished.emit(downloaded_file)
        except Exception as e:
            self.error.emit(str(e))


class UpdateProgressDialog(QDialog):
    """Dialog showing download and installation progress"""

    def __init__(self, download_url: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.downloaded_file: Path | None = None
        self._init_ui()
        self._start_download()

    def _init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Downloading Update")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Status label
        self.status_label = QLabel("Preparing download...")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_download)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _start_download(self):
        """Start downloading the update"""
        self.status_label.setText("Downloading update...")
        self.thread = UpdateDownloadThread(self.download_url)
        self.thread.progress.connect(self._on_progress)
        self.thread.finished.connect(self._on_download_finished)
        self.thread.error.connect(self._on_error)
        self.thread.start()

    def _on_progress(self, downloaded: int, total: int):
        """Update progress bar"""
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_bar.setValue(percent)

            # Format size
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.status_label.setText(
                f"Downloading update... {downloaded_mb:.1f} MB / {total_mb:.1f} MB"
            )

    def _on_download_finished(self, downloaded_file: Path):
        """Handle download completion"""
        self.downloaded_file = downloaded_file
        self.status_label.setText("Download complete! Launching installer...")
        self.progress_bar.setValue(100)
        self.cancel_btn.setEnabled(False)

        try:
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication

            UpdateDownloader.install_update(downloaded_file)

            self.status_label.setText(
                "Installer launched. Quartz will now close.\n"
                "Please follow the installer instructions to complete the update."
            )

            def _close_and_quit():
                self.accept()
                QApplication.instance().quit()

            QTimer.singleShot(1500, _close_and_quit)

        except Exception as e:
            self._on_error(f"Installation failed: {e}")

    def _on_error(self, error_msg: str):
        """Handle download/installation error"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self,
            "Update Failed",
            f"Failed to download or install update:\n{error_msg}\n\n"
            "You can download the update manually from the GitHub releases page."
        )
        self.reject()

    def _cancel_download(self):
        """Cancel the download"""
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait(1000)
        self.reject()

