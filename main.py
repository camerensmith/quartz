"""Quartz - Personal Database Desktop Application
Main entry point"""
import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from src.ui.main_window import MainWindow
from src.core.config import Config
from src.core.version import VERSION


def setup_logging():
    """Configure logging to console and file"""
    # Create logs directory
    log_dir = Path.home() / ".quartz" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "quartz.log"
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),  # Console
            logging.FileHandler(log_file, mode='a', encoding='utf-8')  # File
        ]
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
