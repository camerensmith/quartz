"""Subcollection tab bar widget — sits between the top bar and the table."""

import re
import shutil
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QDrag, QFont, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.subcollection_store import SubcollectionInfo, SubcollectionStore


# ---------------------------------------------------------------------------
# Accessibility / colour helpers
# ---------------------------------------------------------------------------

def _relative_luminance(hex_color: str) -> float:
    """WCAG 2.1 relative luminance for a hex colour string."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

    def linearise(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rl, gl, bl = linearise(r), linearise(g), linearise(b)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def contrasting_text_color(hex_bg: str) -> str:
    """Return '#ffffff' or '#000000' for best WCAG AA contrast against hex_bg."""
    lum = _relative_luminance(hex_bg)
    # contrast ratio with white = (1.05) / (lum + 0.05)
    contrast_white = 1.05 / (lum + 0.05)
    contrast_black = (lum + 0.05) / 0.05
    return "#ffffff" if contrast_white >= contrast_black else "#000000"


def _lighten_hex(hex_color: str, amount: float = 0.15) -> str:
    """Mix hex_color toward white by *amount* (0‒1)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    r2 = int(r + (255 - r) * amount)
    g2 = int(g + (255 - g) * amount)
    b2 = int(b + (255 - b) * amount)
    return f"#{r2:02x}{g2:02x}{b2:02x}"


def _darken_hex(hex_color: str, amount: float = 0.15) -> str:
    """Mix hex_color toward black by *amount*."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    r2 = int(r * (1 - amount))
    g2 = int(g * (1 - amount))
    b2 = int(b * (1 - amount))
    return f"#{r2:02x}{g2:02x}{b2:02x}"


def _accessible_hover(hex_bg: str) -> str:
    """Return a hover background that remains accessible against text colour."""
    lum = _relative_luminance(hex_bg)
    return _lighten_hex(hex_bg, 0.15) if lum < 0.5 else _darken_hex(hex_bg, 0.12)


# ---------------------------------------------------------------------------
# Colour picker dialog
# ---------------------------------------------------------------------------

_PALETTE = [
    "#8000FF", "#9c27b0", "#e91e63", "#f44336", "#ff5722",
    "#ff9800", "#ffc107", "#ffeb3b", "#cddc39", "#4caf50",
    "#009688", "#00bcd4", "#2196f3", "#3f51b5", "#673ab7",
    "#795548", "#9e9e9e", "#607d8b", "#000000", "#ffffff",
]


class ColorPickerDialog(QDialog):
    """A small colour picker with preset swatches and a hex input."""

    _HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

    def __init__(self, current_color: str = "#8000FF", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose tab colour")
        self.setFixedWidth(280)
        # Validate the initial color to prevent malformed CSS
        if not self._HEX_RE.match(current_color or ""):
            current_color = "#8000FF"
        self.chosen_color = current_color

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Swatch grid
        grid_widget = QWidget()
        grid = QHBoxLayout(grid_widget)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)
        # Build 4 rows of 5 swatches
        from PySide6.QtWidgets import QGridLayout
        swatch_widget = QWidget()
        swatch_grid = QGridLayout(swatch_widget)
        swatch_grid.setSpacing(4)
        swatch_grid.setContentsMargins(0, 0, 0, 0)
        for idx, color in enumerate(_PALETTE):
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                f"QPushButton {{background:{color}; border:2px solid transparent; border-radius:4px;}}"
                f"QPushButton:hover {{border:2px solid #333;}}"
            )
            btn.clicked.connect(lambda checked, c=color: self._pick(c))
            swatch_grid.addWidget(btn, idx // 5, idx % 5)
        layout.addWidget(swatch_widget)

        # Hex input
        hex_row = QHBoxLayout()
        hex_row.addWidget(QLabel("Hex:"))
        self._hex_input = QLineEdit(current_color)
        self._hex_input.setMaxLength(7)
        self._hex_input.setFixedWidth(80)
        hex_row.addWidget(self._hex_input)
        self._preview = QLabel()
        self._preview.setFixedSize(28, 28)
        self._preview.setStyleSheet(f"background:{current_color}; border-radius:4px;")
        hex_row.addWidget(self._preview)
        hex_row.addStretch()
        layout.addLayout(hex_row)
        self._hex_input.textChanged.connect(self._on_hex_changed)

        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _pick(self, color: str):
        self.chosen_color = color
        self._hex_input.setText(color)
        self._preview.setStyleSheet(f"background:{color}; border-radius:4px;")

    def _on_hex_changed(self, text: str):
        text = text.strip()
        if not text.startswith("#"):
            text = "#" + text
        try:
            QColor(text)  # validate
            self._preview.setStyleSheet(f"background:{text}; border-radius:4px;")
            self.chosen_color = text
        except Exception:
            pass

    def _accept(self):
        # Ensure chosen_color is valid
        c = QColor(self.chosen_color)
        if not c.isValid():
            self.chosen_color = "#8000FF"
        else:
            self.chosen_color = c.name()
        self.accept()


# ---------------------------------------------------------------------------
# Individual subcollection tab
# ---------------------------------------------------------------------------

class SubcollectionTab(QFrame):
    """A single draggable tab representing one subcollection."""

    clicked = Signal(str)       # emits sub_id
    rename_requested = Signal(str, str)   # sub_id, new_name
    delete_requested = Signal(str)        # sub_id
    color_changed = Signal(str, str)      # sub_id, new_hex
    icon_changed = Signal(str, str)       # sub_id, new_icon_path (rel)
    create_new_requested = Signal()

    def __init__(self, sub: SubcollectionInfo, workspace_path: Path, active: bool = False, parent=None):
        super().__init__(parent)
        self.sub_id = sub.id
        self.sub_name = sub.name
        self.color = sub.color
        self.icon_path_rel = sub.icon_path
        self.workspace_path = workspace_path
        self._active = active
        self._dragging = False
        self._drag_start: QPoint | None = None

        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 8, 2)
        layout.setSpacing(4)

        # Drag grip dots
        grip = QLabel("⠿")
        grip.setFixedWidth(10)
        grip.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 10px;")
        layout.addWidget(grip)

        # Icon
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        self._icon_label.setScaledContents(True)
        self._refresh_icon()
        layout.addWidget(self._icon_label)

        # Name label
        self._name_label = QLabel(sub.name)
        self._name_label.setMaximumWidth(120)
        font = QFont()
        font.setPointSize(9)
        if active:
            font.setBold(True)
        self._name_label.setFont(font)
        layout.addWidget(self._name_label)

        # Inline rename editor (hidden by default)
        self._rename_edit = QLineEdit(sub.name)
        self._rename_edit.setFixedWidth(100)
        self._rename_edit.hide()
        self._rename_edit.returnPressed.connect(self._finish_rename)
        self._rename_edit.editingFinished.connect(self._finish_rename)
        layout.addWidget(self._rename_edit)

        self._apply_style(hover=False)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    def _apply_style(self, hover: bool = False):
        bg = _accessible_hover(self.color) if hover else self.color
        text_color = contrasting_text_color(bg)
        border = "2px solid rgba(0,0,0,0.3)" if self._active else "1px solid rgba(0,0,0,0.2)"
        radius = "6px"
        self.setStyleSheet(f"""
            SubcollectionTab {{
                background: {bg};
                border: {border};
                border-radius: {radius};
            }}
        """)
        label_style = f"color: {text_color}; background: transparent;"
        self._name_label.setStyleSheet(label_style)
        try:
            self._icon_label.setStyleSheet("background: transparent;")
        except RuntimeError:
            # Ignore errors caused by the widget being deleted during cleanup
            pass

    def _refresh_icon(self):
        from src.core.resource_path import asset_path
        if self.icon_path_rel:
            full = self.workspace_path / self.icon_path_rel
            if full.exists():
                pix = QPixmap(str(full))
                if not pix.isNull():
                    self._icon_label.setPixmap(pix.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    return
        # default icon
        default_path = asset_path("subcollection.png")
        if default_path.exists():
            pix = QPixmap(str(default_path))
            if not pix.isNull():
                self._icon_label.setPixmap(pix.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ------------------------------------------------------------------
    # Active state
    # ------------------------------------------------------------------

    def set_active(self, active: bool):
        self._active = active
        font = QFont()
        font.setPointSize(9)
        font.setBold(active)
        self._name_label.setFont(font)
        self._apply_style(hover=False)

    # ------------------------------------------------------------------
    # Hover / mouse events
    # ------------------------------------------------------------------

    def enterEvent(self, event):
        self._apply_style(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(hover=False)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if (event.buttons() & Qt.LeftButton) and self._drag_start is not None:
            if (event.pos() - self._drag_start).manhattanLength() > QApplication.startDragDistance():
                self._start_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and not self._dragging:
            self.clicked.emit(self.sub_id)
        self._dragging = False
        self._drag_start = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def _start_drag(self):
        self._dragging = True
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.sub_id)
        drag.setMimeData(mime)
        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(pix.width() // 2, pix.height() // 2))
        drag.exec(Qt.MoveAction)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Change name", self._start_rename)
        menu.addAction("Change icon", self._change_icon)
        menu.addAction("Change tab color", self._change_color)
        menu.addSeparator()
        menu.addAction("Create new sub", lambda: self.create_new_requested.emit())
        menu.addSeparator()
        menu.addAction("Delete sub", self._confirm_delete)
        menu.exec(self.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Inline rename
    # ------------------------------------------------------------------

    def _start_rename(self):
        self._name_label.hide()
        self._rename_edit.setText(self.sub_name)
        self._rename_edit.show()
        self._rename_edit.setFocus()
        self._rename_edit.selectAll()

    def _finish_rename(self):
        new_name = self._rename_edit.text().strip() or self.sub_name
        self._rename_edit.hide()
        self._name_label.show()
        if new_name != self.sub_name:
            self.sub_name = new_name
            self._name_label.setText(new_name)
            self.rename_requested.emit(self.sub_id, new_name)

    # ------------------------------------------------------------------
    # Change icon
    # ------------------------------------------------------------------

    def _change_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Choose Icon", "", "Images (*.png *.jpg *.jpeg *.svg *.bmp)"
        )
        if not file_path:
            return
        icons_dir = self.workspace_path / "subcollection_icons"
        icons_dir.mkdir(exist_ok=True)
        dest = icons_dir / f"{self.sub_id}.png"
        src = Path(file_path)
        # Copy and resize using Qt
        pix = QPixmap(file_path)
        if not pix.isNull():
            scaled = pix.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.save(str(dest))
        else:
            shutil.copy2(file_path, dest)
        rel = str(dest.relative_to(self.workspace_path))
        self.icon_path_rel = rel
        self._refresh_icon()
        self.icon_changed.emit(self.sub_id, rel)

    # ------------------------------------------------------------------
    # Change colour
    # ------------------------------------------------------------------

    def _change_color(self):
        dlg = ColorPickerDialog(self.color, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_color = dlg.chosen_color
            self.color = new_color
            self._apply_style(hover=False)
            self.color_changed.emit(self.sub_id, new_color)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _confirm_delete(self):
        reply = QMessageBox.question(
            self,
            "Delete Subcollection",
            f"Delete subcollection '{self.sub_name}'?\n\nThis only removes the subcollection tab — no records are deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.delete_requested.emit(self.sub_id)


# ---------------------------------------------------------------------------
# SubcollectionBar
# ---------------------------------------------------------------------------

class SubcollectionBar(QWidget):
    """Horizontal bar of subcollection tabs with drag-to-reorder support.

    Signals
    -------
    subcollection_selected(str | None)
        Emitted when the user clicks a tab (str = sub_id) or deselects (None).
    tabs_reordered(list[str])
        Emitted with the new ordered list of sub_ids after a drag-drop.
    create_requested()
        Emitted when the user clicks "+ New" or chooses "Create new sub".
    """

    subcollection_selected = Signal(object)   # str | None
    tabs_reordered = Signal(list)
    create_requested = Signal()
    rename_requested = Signal(str, str)       # sub_id, new_name
    delete_requested = Signal(str)            # sub_id
    color_changed = Signal(str, str)          # sub_id, new_hex
    icon_changed = Signal(str, str)           # sub_id, new_rel_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._subcollections: list[SubcollectionInfo] = []
        self._workspace_path: Path | None = None
        self._active_id: str | None = None
        self._tabs: list[SubcollectionTab] = []

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(6, 4, 6, 4)
        outer_layout.setSpacing(6)

        # Scroll area for tabs
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(46)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setAcceptDrops(True)
        self._scroll.dragEnterEvent = self._drag_enter
        self._scroll.dragMoveEvent = self._drag_move
        self._scroll.dropEvent = self._drop

        self._tabs_container = QWidget()
        self._tabs_container.setAcceptDrops(True)
        self._tabs_layout = QHBoxLayout(self._tabs_container)
        self._tabs_layout.setContentsMargins(0, 0, 0, 0)
        self._tabs_layout.setSpacing(6)
        self._tabs_layout.addStretch()

        self._scroll.setWidget(self._tabs_container)
        outer_layout.addWidget(self._scroll, 1)

        # "+ New" button
        self._new_btn = QPushButton("+ New")
        self._new_btn.setFixedHeight(32)
        self._new_btn.setFixedWidth(60)
        self._new_btn.setToolTip("Create a new subcollection")
        self._new_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px dashed #aaa;
                border-radius: 6px;
                font-size: 11px;
                color: #666;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: #f0f0f0;
                border-color: #888;
                color: #333;
            }
        """)
        self._new_btn.clicked.connect(self.create_requested.emit)
        outer_layout.addWidget(self._new_btn)

        self.setFixedHeight(54)
        self.hide()  # Hidden until populated

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load(self, subcollections: list[SubcollectionInfo], workspace_path: Path, active_id: str | None = None):
        """Populate the bar from a list of SubcollectionInfo objects."""
        self._subcollections = subcollections
        self._workspace_path = workspace_path
        self._active_id = active_id
        self._rebuild_tabs()

    def clear(self):
        """Remove all tabs and hide the bar."""
        self._subcollections = []
        self._active_id = None
        self._clear_tabs()
        self.hide()

    def set_active(self, sub_id: str | None):
        """Highlight the tab with *sub_id* (or deactivate all if None)."""
        self._active_id = sub_id
        for tab in self._tabs:
            tab.set_active(tab.sub_id == sub_id)

    # ------------------------------------------------------------------
    # Internal rebuild
    # ------------------------------------------------------------------

    def _clear_tabs(self):
        for tab in self._tabs:
            self._tabs_layout.removeWidget(tab)
            tab.setParent(None)
            tab.deleteLater()
        self._tabs = []

    def _rebuild_tabs(self):
        self._clear_tabs()
        for sub in self._subcollections:
            self._add_tab(sub)

        if self._subcollections:
            self.show()
        else:
            self.hide()

    def _add_tab(self, sub: SubcollectionInfo):
        tab = SubcollectionTab(
            sub,
            self._workspace_path,
            active=(sub.id == self._active_id),
            parent=self._tabs_container,
        )
        # Wire signals
        tab.clicked.connect(self._on_tab_clicked)
        tab.rename_requested.connect(self.rename_requested.emit)
        tab.delete_requested.connect(self._on_delete_requested)
        tab.color_changed.connect(self.color_changed.emit)
        tab.icon_changed.connect(self.icon_changed.emit)
        tab.create_new_requested.connect(self.create_requested.emit)

        # Insert before the stretch
        stretch_index = self._tabs_layout.count() - 1  # last item is stretch
        self._tabs_layout.insertWidget(stretch_index, tab)
        self._tabs.append(tab)

    # ------------------------------------------------------------------
    # Tab click handler
    # ------------------------------------------------------------------

    def _on_tab_clicked(self, sub_id: str):
        if self._active_id == sub_id:
            # Clicking active tab deselects (show all)
            self._active_id = None
            self.set_active(None)
            self.subcollection_selected.emit(None)
        else:
            self._active_id = sub_id
            self.set_active(sub_id)
            self.subcollection_selected.emit(sub_id)

    def _on_delete_requested(self, sub_id: str):
        was_active = (self._active_id == sub_id)
        if was_active:
            self._active_id = None
            self.subcollection_selected.emit(None)
        self.delete_requested.emit(sub_id)

    # ------------------------------------------------------------------
    # Drag & drop reorder
    # ------------------------------------------------------------------

    def _drag_enter(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def _drag_move(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def _drop(self, event):
        if not event.mimeData().hasText():
            return
        dragged_id = event.mimeData().text()
        # Find drop position among tabs
        drop_x = self._scroll.widget().mapFrom(self._scroll, event.position().toPoint()).x()
        new_order = []
        inserted = False
        for tab in self._tabs:
            tab_center = tab.x() + tab.width() // 2
            if not inserted and drop_x < tab_center:
                new_order.append(dragged_id)
                inserted = True
            if tab.sub_id != dragged_id:
                new_order.append(tab.sub_id)
        if not inserted:
            new_order.append(dragged_id)

        event.acceptProposedAction()
        # Reorder _subcollections list
        id_to_sub = {s.id: s for s in self._subcollections}
        self._subcollections = [id_to_sub[sid] for sid in new_order if sid in id_to_sub]
        self._rebuild_tabs()
        self.tabs_reordered.emit(new_order)
