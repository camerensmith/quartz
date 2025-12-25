"""Application styles and themes"""

from typing import Dict


class AppStyles:
    """Centralized styling for the application"""
    
    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    # Color schemes
    COLOR_SCHEMES = {
        "default": {  # Based on #8000FF
            "primary": "#8000FF",
            "primary_light": "#9D33FF",
            "primary_dark": "#6600CC",
            "primary_lighter": "#B366FF",
            "primary_darker": "#4D00AA",
            "accent": "#9933FF",
            "accent_light": "#B366FF",
            "accent_dark": "#6600CC",
        },
        "magenta": {  # Current theme
            "primary": "#9c27b0",
            "primary_light": "#ab47bc",
            "primary_dark": "#7b1fa2",
            "primary_lighter": "#ba68c8",
            "primary_darker": "#6a1b9a",
            "accent": "#8e24aa",
            "accent_light": "#ba68c8",
            "accent_dark": "#4a148c",
        },
        "modern": {  # Black/grey modern
            "primary": "#2d2d2d",
            "primary_light": "#3d3d3d",
            "primary_dark": "#1d1d1d",
            "primary_lighter": "#4d4d4d",
            "primary_darker": "#0d0d0d",
            "accent": "#4a4a4a",
            "accent_light": "#6a6a6a",
            "accent_dark": "#2a2a2a",
        }
    }
    
    @staticmethod
    def _get_base_light_theme(colors: Dict[str, str]) -> str:
        """Get base light theme with color scheme"""
        # Extract RGB values from primary color for subtle selection
        primary_rgb = AppStyles._hex_to_rgb(colors['primary'])
        return f"""
/* Main Window */
QMainWindow {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f5f5f5, stop:1 #e8e8e8);
}}

/* Sidebar */
QListWidget {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffffff, stop:1 #f5f5f5);
    border: none;
    border-right: 1px solid #e0e0e0;
    padding: 8px;
    font-size: 13px;
}}

QListWidget::item {{
    padding: 10px 12px;
    border-radius: 6px;
    margin: 2px 0px;
}}

QListWidget::item:hover {{
    background-color: #f0f0f0;
}}

QListWidget::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {colors['primary']}, stop:1 {colors['primary_light']});
    color: #ffffff;
    font-weight: 500;
}}

/* Toolbar */
QToolBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f5f5f5);
    border: none;
    border-bottom: 1px solid #e0e0e0;
    padding: 4px;
    spacing: 4px;
}}

QToolBar QToolButton {{
    padding: 6px 12px;
    border-radius: 4px;
    background-color: transparent;
    border: 1px solid transparent;
}}

QToolBar QToolButton:hover {{
    background-color: #f5f5f5;
    border: 1px solid #e0e0e0;
}}

QToolBar QToolButton:pressed {{
    background-color: #e8e8e8;
}}

/* Buttons */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 500;
    min-height: 24px;
}}

QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_light']}, stop:1 {colors['primary']});
}}

QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_dark']}, stop:1 {colors['primary_darker']});
}}

QPushButton:disabled {{
    background-color: #bdbdbd;
    color: #757575;
}}

/* Secondary buttons */
QPushButton[class="secondary"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_lighter']}, stop:1 {colors['accent_light']});
    color: #ffffff;
    border: 1px solid {colors['primary']};
}}

QPushButton[class="secondary"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['accent_light']}, stop:1 {colors['primary']});
    border: 1px solid {colors['primary_light']};
}}

/* Table View */
QTableView {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    gridline-color: #d0d0d0;
    selection-background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, 0.03);
    selection-color: #424242;
    font-size: 13px;
}}

QTableView::item {{
    padding: 4px;
    border: none;
}}

QTableView::item:selected {{
    background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, 0.04);
    color: #424242;
    border: none;
}}

QTableView::item:hover {{
    background-color: #f5f5f5;
}}

QTableView::item:selected:hover {{
    background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, 0.05);
}}

/* Inline editor styling - subtle and non-intrusive */
QTableView QLineEdit,
QTableView QSpinBox,
QTableView QDoubleSpinBox,
QTableView QComboBox,
QTableView QDateEdit,
QTableView QDateTimeEdit {{
    background-color: rgba(255, 255, 255, 0.95);
    border: 1px solid rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, 0.25);
    border-radius: 2px;
    padding: 2px 4px;
    color: #424242;
    selection-background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, 0.15);
    selection-color: #424242;
}}

QTableView QLineEdit:focus,
QTableView QSpinBox:focus,
QTableView QDoubleSpinBox:focus,
QTableView QComboBox:focus,
QTableView QDateEdit:focus,
QTableView QDateTimeEdit:focus {{
    border: 1px solid rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, 0.5);
    background-color: rgba(255, 255, 255, 1.0);
    color: #424242;
}}

QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fafafa, stop:1 #f5f5f5);
    color: #424242;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #e0e0e0;
    border-right: 1px solid #e0e0e0;
    font-weight: 600;
    font-size: 12px;
}}

/* Vertical header (row numbers) - reduce padding to prevent cutoff */
QHeaderView::section:vertical {{
    padding: 4px 8px;
    min-width: 70px;
}}

QHeaderView::section:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f0f0f0, stop:1 {colors['primary_lighter']});
}}

/* Form View */
QFormLayout {{
    spacing: 12px;
}}

QLabel {{
    color: #424242;
    font-size: 13px;
}}

QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QDateTimeEdit {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 20px;
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus, QDateTimeEdit:focus {{
    border: 2px solid {colors['primary']};
    padding: 5px 9px;
}}

QLineEdit:hover, QTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QDateEdit:hover, QDateTimeEdit:hover {{
    border: 1px solid #bdbdbd;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #757575;
    width: 0;
    height: 0;
}}

QComboBox QAbstractItemView {{
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background-color: #ffffff;
    selection-background-color: {colors['primary']};
    selection-color: #ffffff;
}}

/* Checkbox */
QCheckBox {{
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid #757575;
    border-radius: 4px;
    background-color: #ffffff;
}}

QCheckBox::indicator:hover {{
    border-color: {colors['primary']};
}}

QCheckBox::indicator:checked {{
    background-color: {colors['primary']};
    border-color: {colors['primary']};
    image: none;
}}

QCheckBox::indicator:unchecked {{
    background-color: #ffffff;
    border-color: #757575;
    image: none;
}}

/* Search Box */
QLineEdit[class="search"] {{
    border: 1px solid #e0e0e0;
    border-radius: 20px;
    padding: 6px 16px;
    background-color: #ffffff;
    font-size: 13px;
}}

QLineEdit[class="search"]:focus {{
    border: 2px solid {colors['primary']};
    padding: 5px 15px;
}}

/* View Toggle */
QPushButton[class="toggle"] {{
    background-color: #f5f5f5;
    color: #424242;
    border: 1px solid #e0e0e0;
    padding: 6px 20px;
    border-radius: 4px;
}}

QPushButton[class="toggle"]:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    color: white;
    border: 1px solid {colors['primary']};
}}

/* Menus */
QMenu {{
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px 6px 28px;
    border-radius: 3px;
}}

QMenu::item:selected {{
    background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, 0.1);
}}

QMenu::indicator {{
    width: 16px;
    height: 16px;
    left: 6px;
}}

/* Dialogs */
QDialog {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f5f5f5);
}}

QGroupBox {{
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
    font-size: 13px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0px 8px;
    color: #424242;
}}

/* Status Bar */
QStatusBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {colors['primary']}, stop:1 {colors['primary_light']});
    border-top: 1px solid {colors['primary_dark']};
    color: #ffffff;
    font-size: 12px;
    font-weight: 500;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background-color: #f5f5f5;
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: #bdbdbd;
    border-radius: 6px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #9e9e9e;
}}

QScrollBar:horizontal {{
    background-color: #f5f5f5;
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: #bdbdbd;
    border-radius: 6px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #9e9e9e;
}}

/* Error states */
QLineEdit[class="error"], QTextEdit[class="error"] {{
    border: 2px solid #d32f2f;
    background-color: #ffebee;
}}

QLabel[class="error"] {{
    color: #d32f2f;
    font-size: 11px;
}}

/* Navigation buttons */
QPushButton[class="nav"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    border: 1px solid {colors['primary_dark']};
    border-radius: 3px;
    padding: 2px 6px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    font-size: 12px;
    font-weight: bold;
    color: #ffffff;
}}

QPushButton[class="nav"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_light']}, stop:1 {colors['primary']});
    border: 1px solid {colors['primary_light']};
}}

QPushButton[class="nav"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_dark']}, stop:1 {colors['primary_darker']});
}}

/* Icon buttons */
QPushButton[class="icon-button"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    border: 1px solid {colors['primary_dark']};
    border-radius: 4px;
    padding: 4px;
    font-size: 14px;
    font-weight: bold;
    min-width: 24px;
    min-height: 24px;
    color: #ffffff;
}}

QPushButton[class="icon-button"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_light']}, stop:1 {colors['primary']});
    border: 1px solid {colors['primary_light']};
}}

QPushButton[class="icon-button"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_dark']}, stop:1 {colors['primary_darker']});
}}
"""
    
    @staticmethod
    def _get_base_dark_theme(colors: Dict[str, str]) -> str:
        """Get base dark theme with color scheme - adapts to color scheme"""
        # Extract RGB values from primary color for subtle selection
        primary_rgb = AppStyles._hex_to_rgb(colors['primary'])
        
        # Determine if this is the modern (dark) scheme - needs lighter backgrounds for contrast
        is_modern = colors['primary'] == "#2d2d2d"
        
        # Adaptive background colors based on color scheme
        if is_modern:
            # Modern scheme: use lighter backgrounds for better contrast
            bg_main_start = "#2a2a2a"
            bg_main_end = "#1f1f1f"
            bg_sidebar_start = "#303030"
            bg_sidebar_end = "#2a2a2a"
            bg_toolbar_start = "#353535"
            bg_toolbar_end = "#2a2a2a"
            bg_table = "#2a2a2a"
            bg_item_hover = "#353535"
            bg_cell_focus = "#2d2d2d"  # One tint lighter than table (#2a2a2a -> #2d2d2d)
            border_color = "#4a4a4a"
            text_color = "#e0e0e0"
            gridline_color = "#6a6a6a"
            header_border = "#6a6a6a"
            header_hover_bg = "#5a5a5a"
            selection_opacity = "0.35"
            selection_opacity_selected = "0.40"
            selection_opacity_hover = "0.45"
            editor_bg = "rgba(55, 55, 55, 0.98)"
            editor_bg_focus = "rgba(60, 60, 60, 1.0)"
            editor_border_opacity = "0.7"
            form_focus_bg = "#2d2d2d"
            form_hover_bg = "#2d2d2d"
            form_hover_border = "#6a6a6a"
        else:
            # Default/Magenta: use standard dark backgrounds with improved accessibility
            bg_main_start = "#1e1e1e"
            bg_main_end = "#0d0d0d"
            bg_sidebar_start = "#252526"
            bg_sidebar_end = "#1e1e1e"
            bg_toolbar_start = "#2d2d30"
            bg_toolbar_end = "#1e1e1e"
            bg_table = "#1e1e1e"
            bg_item_hover = "#2a2d2e"
            bg_cell_focus = ""  # Not used for non-modern schemes
            border_color = "#505050"
            text_color = "#e0e0e0"  # Light grey - good contrast but not pure white
            gridline_color = "#5a5a5a"
            header_border = "#5a5a5a"
            header_hover_bg = "#4a4a4a"
            selection_opacity = "0.25"
            selection_opacity_selected = "0.30"
            selection_opacity_hover = "0.35"
            editor_bg = "rgba(42, 42, 43, 0.98)"
            editor_bg_focus = "rgba(45, 45, 46, 1.0)"
            editor_border_opacity = "0.5"
            form_focus_bg = "#1f1f1f"
            form_hover_bg = "#1f1f1f"
            form_hover_border = "#6a6a6a"
        
        # Determine cell focus background color
        if is_modern and bg_cell_focus:
            cell_focus_bg = bg_cell_focus
        else:
            cell_focus_bg = f"rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, {selection_opacity_selected})"
        
        return f"""
/* Main Window */
QMainWindow {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_main_start}, stop:1 {bg_main_end});
}}

/* Sidebar */
QListWidget {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {bg_sidebar_start}, stop:1 {bg_sidebar_end});
    border: none;
    border-right: 1px solid {border_color};
    padding: 8px;
    font-size: 13px;
    color: {text_color};
}}

QListWidget::item {{
    padding: 10px 12px;
    border-radius: 6px;
    margin: 2px 0px;
    color: {text_color};
}}

QListWidget::item:hover {{
    background-color: {bg_item_hover};
}}

QListWidget::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {colors['primary']}, stop:1 {colors['primary_light']});
    color: #ffffff;
    font-weight: 500;
}}

/* Toolbar */
QToolBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_toolbar_start}, stop:1 {bg_toolbar_end});
    border: none;
    border-bottom: 1px solid {border_color};
    padding: 4px;
    spacing: 4px;
}}

QToolBar QToolButton {{
    padding: 6px 12px;
    border-radius: 4px;
    background-color: transparent;
    border: 1px solid transparent;
    color: {text_color};
}}

QToolBar QToolButton:hover {{
    background-color: {border_color};
    border: 1px solid {colors['primary_light'] if not is_modern else '#5a5a5a'};
}}

QToolBar QToolButton:pressed {{
    background-color: {colors['primary_dark'] if not is_modern else '#4a4a4a'};
}}

/* Buttons */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 500;
    min-height: 24px;
}}

QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_light']}, stop:1 {colors['primary']});
}}

QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_dark']}, stop:1 {colors['primary_darker']});
}}

QPushButton:disabled {{
    background-color: {border_color};
    color: {colors['primary_dark'] if is_modern else '#6e6e6e'};
}}

/* Secondary buttons */
QPushButton[class="secondary"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_dark']}, stop:1 {colors['primary_darker']});
    color: #ffffff;
    border: 1px solid {colors['primary']};
}}

QPushButton[class="secondary"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    border: 1px solid {colors['primary_light']};
}}

/* Table View */
QTableView {{
    background-color: {bg_table};
    border: 1px solid {border_color};
    border-radius: 4px;
    gridline-color: {gridline_color};
    selection-background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, {selection_opacity});
    selection-color: #ffffff;
    font-size: 13px;
    color: {text_color};
    alternate-background-color: #2a2a2a;
}}

QTableView::item {{
    padding: 4px;
    border: none;
}}

QTableView::item:selected {{
    background-color: {cell_focus_bg};
    color: #ffffff;
    border: 2px solid {colors['primary']};
}}

QTableView::item:hover {{
    background-color: {bg_item_hover};
    border: 1px solid {gridline_color};
    color: {text_color};
}}

QTableView::item:selected:hover {{
    background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, {selection_opacity_hover});
    color: #ffffff;
}}

/* Inline editor styling for dark theme - accessible and visible */
QTableView QLineEdit,
QTableView QSpinBox,
QTableView QDoubleSpinBox,
QTableView QComboBox,
QTableView QDateEdit,
QTableView QDateTimeEdit {{
    background-color: {editor_bg};
    border: 2px solid rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, {editor_border_opacity});
    border-radius: 2px;
    padding: 2px 4px;
    color: {text_color};
    selection-background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, 0.5);
    selection-color: #ffffff;
}}

QTableView QLineEdit:focus,
QTableView QSpinBox:focus,
QTableView QDoubleSpinBox:focus,
QTableView QComboBox:focus,
QTableView QDateEdit:focus,
QTableView QDateTimeEdit:focus {{
    border: 2px solid {colors['primary']};
    background-color: {editor_bg_focus};
    color: {text_color};
}}

QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_toolbar_start}, stop:1 {bg_table});
    color: {text_color};
    padding: 8px;
    border: none;
    border-bottom: 2px solid {header_border};
    border-right: 1px solid {header_border};
    font-weight: 600;
    font-size: 12px;
}}

QHeaderView::section:vertical {{
    padding: 4px 8px;
    min-width: 70px;
}}

QHeaderView::section:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {header_hover_bg}, stop:1 {colors['primary_dark']});
    border-bottom: 2px solid {colors['primary']};
}}

/* Form View */
QFormLayout {{
    spacing: 12px;
}}

QLabel {{
    color: {text_color};
    font-size: 13px;
}}

QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QDateTimeEdit {{
    background-color: {bg_sidebar_start};
    border: 2px solid {border_color};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 20px;
    color: {text_color};
}}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus, QDateTimeEdit:focus {{
    border: 2px solid {colors['primary']};
    padding: 5px 9px;
    background-color: {form_focus_bg};
}}

QLineEdit:hover, QTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QDateEdit:hover, QDateTimeEdit:hover {{
    border: 2px solid {form_hover_border if is_modern else colors['primary_light']};
    background-color: {form_hover_bg};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {text_color};
    width: 0;
    height: 0;
}}

QComboBox QAbstractItemView {{
    border: 2px solid {border_color};
    border-radius: 4px;
    background-color: {bg_sidebar_start};
    selection-background-color: {colors['primary']};
    selection-color: #ffffff;
    color: {text_color};
}}

/* Checkbox */
QCheckBox {{
    spacing: 8px;
    font-size: 13px;
    color: {text_color};
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {colors['primary_dark'] if is_modern else '#6e6e6e'};
    border-radius: 4px;
    background-color: {bg_sidebar_start};
}}

QCheckBox::indicator:hover {{
    border-color: {colors['primary']};
}}

QCheckBox::indicator:checked {{
    background-color: {colors['primary']};
    border-color: {colors['primary']};
    image: none;
}}

QCheckBox::indicator:unchecked {{
    background-color: {bg_sidebar_start};
    border-color: {colors['primary_dark'] if is_modern else '#6e6e6e'};
    image: none;
}}

/* Search Box */
QLineEdit[class="search"] {{
    border: 2px solid {border_color};
    border-radius: 20px;
    padding: 6px 16px;
    background-color: {bg_sidebar_start};
    font-size: 13px;
    color: {text_color};
}}

QLineEdit[class="search"]:focus {{
    border: 2px solid {colors['primary']};
    padding: 5px 15px;
    background-color: {form_focus_bg};
}}

/* View Toggle */
QPushButton[class="toggle"] {{
    background-color: {bg_toolbar_start};
    color: {text_color};
    border: 1px solid {border_color};
    padding: 6px 20px;
    border-radius: 4px;
}}

/* Filter Chips */
QFrame[class="filter-chip"] {{
    background-color: {bg_item_hover if is_modern else '#f0f0f0'};
    border: 1px solid {border_color};
    border-radius: 12px;
    padding: 2px;
    max-width: 250px;
}}

QFrame[class="filter-chip"]:hover {{
    background-color: {colors['primary_light'] if not is_modern else '#3a3a3a'};
    border-color: {colors['primary']};
}}

QLabel[class="filter-chip-label"] {{
    color: {text_color};
    font-size: 12px;
    padding: 2px 4px;
}}

QLabel[class="filter-chip-remove"] {{
    background-color: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}}

QLabel[class="filter-chip-remove"]:hover {{
    opacity: 0.7;
}}

QPushButton[class="toggle"]:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    color: white;
    border: 1px solid {colors['primary']};
}}

/* Menus */
QMenu {{
    background-color: {bg_sidebar_start};
    border: 2px solid {border_color};
    border-radius: 4px;
    padding: 4px;
    color: {text_color};
}}

QMenu::item {{
    padding: 6px 24px 6px 28px;
    border-radius: 3px;
    color: {text_color};
}}

QMenu::item:selected {{
    background-color: rgba({primary_rgb[0]}, {primary_rgb[1]}, {primary_rgb[2]}, {selection_opacity_selected});
    color: #ffffff;
}}

QMenu::indicator {{
    width: 16px;
    height: 16px;
    left: 6px;
}}

/* Dialogs */
QDialog {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_sidebar_start}, stop:1 {bg_table});
    color: {text_color};
}}

/* Tab Widget - for Preferences dialog */
QTabWidget::pane {{
    border: 2px solid {border_color};
    border-radius: 4px;
    background-color: {bg_sidebar_start};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {bg_table};
    color: {text_color};
    border: 1px solid {border_color};
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background-color: {bg_sidebar_start};
    color: {text_color};
    border-bottom: 2px solid {colors['primary']};
    font-weight: 600;
}}

QTabBar::tab:hover {{
    background-color: {bg_item_hover};
}}

QGroupBox {{
    border: 2px solid {border_color};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
    font-size: 13px;
    color: {text_color};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0px 8px;
    color: {text_color};
}}

/* Status Bar */
QStatusBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {colors['primary']}, stop:1 {colors['primary_light']});
    border-top: 1px solid {colors['primary_dark']};
    color: #ffffff;
    font-size: 12px;
    font-weight: 500;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background-color: {bg_table};
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {border_color};
    border-radius: 6px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {colors['primary_light'] if not is_modern else '#5a5a5a'};
}}

QScrollBar:horizontal {{
    background-color: {bg_table};
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {border_color};
    border-radius: 6px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {colors['primary_light'] if not is_modern else '#5a5a5a'};
}}

/* Error states */
QLineEdit[class="error"], QTextEdit[class="error"] {{
    border: 2px solid #f44336;
    background-color: #3d1f1f;
}}

QLabel[class="error"] {{
    color: #f44336;
    font-size: 11px;
}}

/* Navigation buttons */
QPushButton[class="nav"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    border: 1px solid {colors['primary_dark']};
    border-radius: 3px;
    padding: 2px 6px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    font-size: 12px;
    font-weight: bold;
    color: #ffffff;
}}

QPushButton[class="nav"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_light']}, stop:1 {colors['primary']});
    border: 1px solid {colors['primary_light']};
}}

QPushButton[class="nav"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_dark']}, stop:1 {colors['primary_darker']});
}}

/* Icon buttons */
QPushButton[class="icon-button"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    border: 1px solid {colors['primary_dark']};
    border-radius: 4px;
    padding: 4px;
    font-size: 14px;
    font-weight: bold;
    min-width: 24px;
    min-height: 24px;
    color: #ffffff;
}}

QPushButton[class="icon-button"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_light']}, stop:1 {colors['primary']});
    border: 1px solid {colors['primary_light']};
}}

QPushButton[class="icon-button"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_dark']}, stop:1 {colors['primary_darker']});
}}

/* Message Boxes and Dialogs - ensure text is visible */
QMessageBox {{
    background-color: {bg_sidebar_start};
    color: {text_color};
}}

QMessageBox QLabel {{
    color: {text_color};
}}

QMessageBox QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary']}, stop:1 {colors['primary_dark']});
    color: #ffffff;
    border: 1px solid {colors['primary']};
    padding: 6px 20px;
    border-radius: 4px;
    min-width: 80px;
}}

QMessageBox QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors['primary_light']}, stop:1 {colors['primary']});
}}

QInputDialog {{
    background-color: {bg_sidebar_start};
    color: {text_color};
}}

QInputDialog QLabel {{
    color: {text_color};
}}

QInputDialog QLineEdit {{
    background-color: {bg_sidebar_start};
    border: 2px solid {border_color};
    color: {text_color};
}}

QFileDialog {{
    background-color: {bg_sidebar_start};
    color: {text_color};
}}

QFileDialog QLabel {{
    color: {text_color};
}}
"""
    
    @staticmethod
    def get_theme(theme_name: str = "default", color_scheme: str = "default", mode: str = "light") -> str:
        """Get theme by name, color scheme, and mode
        
        Args:
            theme_name: Deprecated, use color_scheme instead
            color_scheme: "default" (#8000FF), "magenta", or "modern"
            mode: "light" or "dark"
        """
        # Support old theme_name format for backward compatibility
        if theme_name in ["light", "dark", "system"]:
            mode = theme_name if theme_name != "system" else "light"
            color_scheme = "default"
        
        colors = AppStyles.COLOR_SCHEMES.get(color_scheme, AppStyles.COLOR_SCHEMES["default"])
        
        if mode == "dark":
            return AppStyles._get_base_dark_theme(colors)
        else:
            return AppStyles._get_base_light_theme(colors)
    
    # Legacy methods for backward compatibility
    @staticmethod
    def get_light_theme() -> str:
        """Get light theme (default color scheme)"""
        return AppStyles.get_theme(color_scheme="default", mode="light")
    
    @staticmethod
    def get_dark_theme() -> str:
        """Get dark theme (default color scheme)"""
        return AppStyles.get_theme(color_scheme="default", mode="dark")
