"""UI affordances for ``image`` cells.

The cell value is always the canonical reference ``asset:sha256:<hex>``.
Bytes live in the workspace asset store. These widgets resolve and render
from that store; they never store binary data in the database.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QImage,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from src.core.asset_store import AssetStore, parse_asset_ref
from src.core.collection_store import CollectionStore

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg")
THUMB_SIZE = QSize(64, 64)
TABLE_THUMB_HEIGHT = 48


def is_image_file(path: Path | str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def _guess_mime(path: Path) -> str | None:
    mime, _ = mimetypes.guess_type(path.name)
    return mime


def store_image_from_path(
    asset_store: AssetStore,
    collection_store: CollectionStore,
    file_path: Path,
) -> str | None:
    """Read *file_path*, store its bytes, return the canonical reference."""
    try:
        data = Path(file_path).read_bytes()
    except OSError:
        return None
    pix = QPixmap(str(file_path))
    width = pix.width() if not pix.isNull() else None
    height = pix.height() if not pix.isNull() else None
    return asset_store.store_bytes(
        data,
        store=collection_store,
        original_name=Path(file_path).name,
        mime=_guess_mime(Path(file_path)),
        width=width,
        height=height,
    )


def thumbnail_for_ref(
    asset_store: AssetStore,
    ref: str | None,
    size: QSize = THUMB_SIZE,
) -> QPixmap | None:
    """Return a scaled QPixmap for *ref*, or None if missing / not an image."""
    if not ref or not parse_asset_ref(ref):
        return None
    data = asset_store.resolve_bytes(ref)
    if not data:
        return None
    image = QImage.fromData(data)
    if image.isNull():
        return None
    return QPixmap.fromImage(image).scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ---------------------------------------------------------------------------
# Form widget
# ---------------------------------------------------------------------------

class ImageFieldWidget(QWidget):
    """Drop / browse / clear widget that resolves to an asset reference."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._asset_store: AssetStore | None = None
        self._collection_store: CollectionStore | None = None
        self._ref: str | None = None
        self._readonly = False
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._thumb = QLabel("(no image)")
        self._thumb.setFixedSize(72, 72)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            "QLabel {"
            " border: 1px dashed #aaa;"
            " border-radius: 6px;"
            " color: #888;"
            " font-size: 10px;"
            " background: #fafafa;"
            "}"
        )
        layout.addWidget(self._thumb)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)

        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color: #666; font-size: 11px;")
        self._info_label.setWordWrap(True)
        right.addWidget(self._info_label)

        button_row = QHBoxLayout()
        self._choose_btn = QPushButton("Choose…")
        self._choose_btn.clicked.connect(self._on_choose)
        button_row.addWidget(self._choose_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setProperty("class", "secondary")
        self._clear_btn.clicked.connect(self._on_clear)
        button_row.addWidget(self._clear_btn)

        button_row.addStretch()
        right.addLayout(button_row)

        layout.addLayout(right, stretch=1)
        self._refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bind_stores(
        self,
        asset_store: AssetStore | None,
        collection_store: CollectionStore | None,
    ) -> None:
        self._asset_store = asset_store
        self._collection_store = collection_store
        self._refresh()

    def set_value(self, value: str | None) -> None:
        if value and parse_asset_ref(value):
            self._ref = value
        else:
            self._ref = None
        self._refresh()

    def value(self) -> str:
        return self._ref or ""

    def set_readonly(self, readonly: bool) -> None:
        self._readonly = readonly
        self._choose_btn.setEnabled(not readonly)
        self._clear_btn.setEnabled(not readonly and bool(self._ref))
        self.setAcceptDrops(not readonly)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._clear_btn.setEnabled(not self._readonly and bool(self._ref))
        if not self._ref:
            self._thumb.setText("(no image)")
            self._thumb.setPixmap(QPixmap())
            self._info_label.setText("")
            return

        pix = None
        if self._asset_store:
            pix = thumbnail_for_ref(self._asset_store, self._ref, QSize(72, 72))
        if pix is None:
            self._thumb.setText("(missing)")
            self._thumb.setPixmap(QPixmap())
            self._info_label.setText(self._ref)
        else:
            self._thumb.setText("")
            self._thumb.setPixmap(pix)
            self._info_label.setText(self._ref)

    def _ingest_path(self, path: Path) -> None:
        if not (self._asset_store and self._collection_store):
            return
        ref = store_image_from_path(self._asset_store, self._collection_store, path)
        if ref:
            self._ref = ref
            self._refresh()

    def _on_choose(self) -> None:
        if self._readonly:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg);;All files (*)",
        )
        if file_path:
            self._ingest_path(Path(file_path))

    def _on_clear(self) -> None:
        if self._readonly:
            return
        self._ref = None
        self._refresh()

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._readonly:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and is_image_file(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if self._readonly:
            event.ignore()
            return
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if is_image_file(path):
                    self._ingest_path(path)
                    event.acceptProposedAction()
                    return
        event.ignore()


# ---------------------------------------------------------------------------
# Table delegate
# ---------------------------------------------------------------------------

class ImageDelegate(QStyledItemDelegate):
    """Renders thumbnails inline and opens a file picker on edit."""

    def __init__(
        self,
        field: dict,
        asset_store: AssetStore | None,
        collection_store_provider,
        parent=None,
    ):
        super().__init__(parent)
        self.field = field
        self._asset_store = asset_store
        # ``collection_store_provider`` is a zero-arg callable so we always pull
        # the *current* CollectionStore (it can switch when the user opens a
        # different collection without rebuilding all delegates).
        self._collection_store_provider = collection_store_provider

    def set_asset_store(self, asset_store: AssetStore | None) -> None:
        self._asset_store = asset_store

    # Don't create an inline editor — clicks open a file picker (handled in
    # editorEvent).
    def createEditor(self, parent, option, index):
        return None

    def displayText(self, value, locale):
        # Don't overlay text on the thumbnail.
        return ""

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), TABLE_THUMB_HEIGHT + 4)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        # Let the base delegate draw selection highlight, focus state, etc.
        super().paint(painter, option, index)

        ref = index.data(Qt.ItemDataRole.EditRole)
        if not ref:
            return

        pix: QPixmap | None = None
        if self._asset_store:
            pix = thumbnail_for_ref(
                self._asset_store,
                str(ref),
                QSize(option.rect.height() - 4, TABLE_THUMB_HEIGHT),
            )
        if pix is None:
            painter.save()
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, "(missing)")
            painter.restore()
            return

        target = option.rect
        x = target.left() + (target.width() - pix.width()) // 2
        y = target.top() + (target.height() - pix.height()) // 2
        painter.drawPixmap(x, y, pix)

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option,
        index: QModelIndex,
    ) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            return self._pick_file(model, index)
        return super().editorEvent(event, model, option, index)

    def _pick_file(self, model: QAbstractItemModel, index: QModelIndex) -> bool:
        if not (self._asset_store and self._collection_store_provider):
            return False
        store = self._collection_store_provider()
        if store is None:
            return False
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Choose Image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg);;All files (*)",
        )
        if not file_path:
            return True
        ref = store_image_from_path(self._asset_store, store, Path(file_path))
        if ref:
            model.setData(index, ref, Qt.ItemDataRole.EditRole)
        return True
