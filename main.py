"""Quartz - Personal Database Desktop Application
Main entry point"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.core.config import Config
from src.core.version import VERSION
from src.ui.main_window import MainWindow


def setup_logging():
    """Configure logging to console and a rotating file

    Logs at INFO by default; pass --debug or set QUARTZ_DEBUG=1 for DEBUG.
    """
    # Create logs directory
    log_dir = Path.home() / ".quartz" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "quartz.log"

    debug = "--debug" in sys.argv or os.environ.get("QUARTZ_DEBUG") == "1"

    # Keep at most ~6 MB of logs: quartz.log plus 5 rotated 1 MB backups
    handlers: list[logging.Handler] = [
        RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5, encoding='utf-8')
    ]
    # The windowed (PyInstaller) build has no stdout
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
    )

    # Set specific loggers to appropriate levels
    logging.getLogger('PySide6').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)


def main():
    """Application entry point"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Quartz application")

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
