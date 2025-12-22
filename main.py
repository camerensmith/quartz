"""Quartz - Personal Database Desktop Application
Main entry point"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from src.ui.main_window import MainWindow
from src.core.config import Config
from src.core.version import VERSION


def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName('Quartz')
    app.setOrganizationName('Quartz')
    app.setApplicationVersion(VERSION)
    from src.core.resource_path import get_quartz_icon_path
    icon_path = get_quartz_icon_path()
    if icon_path.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(icon_path)))
    config = Config()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
