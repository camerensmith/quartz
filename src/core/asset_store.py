"""Content-addressed asset storage for Quartz workspaces.

Cell values store stable references (``asset:sha256:<hex>``). Bytes live under
``workspace/assets/``. Per-collection ``_assets`` / ``_asset_refs`` tables
hold queryable metadata and reference tracking.

Other export formats (``.sqlite``, CSV, Excel) are unchanged — they carry
references and metadata only. The ``.qz`` bundle is the lossless format that
includes the actual asset bytes.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.collection_store import CollectionStore

ASSET_REF_PATTERN = re.compile(
    r"^asset:(?P<algorithm>[a-z0-9]+):(?P<hash>[a-f0-9]{64})$"
)
DEFAULT_HASH_ALGORITHM = "sha256"

# MIME → preferred file extension for on-disk storage
_MIME_EXT: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/svg+xml": "svg",
}


def canonical_ref(hash_hex: str, algorithm: str = DEFAULT_HASH_ALGORITHM) -> str:
    """Build the canonical cell reference string."""
    return f"asset:{algorithm}:{hash_hex}"


def parse_asset_ref(value: str | None) -> tuple[str, str] | None:
    """Parse ``asset:<algorithm>:<hex>`` → ``(algorithm, hash_hex)`` or None."""
    if not value or not isinstance(value, str):
        return None
    m = ASSET_REF_PATTERN.match(value.strip())
    if not m:
        return None
    return m.group("algorithm"), m.group("hash")


def ext_for_mime(mime: str | None, original_name: str | None = None) -> str:
    """Return a file extension for *mime*, falling back to the original name."""
    if mime and mime in _MIME_EXT:
        return _MIME_EXT[mime]
    if mime:
        guessed = mimetypes.guess_extension(mime, strict=False)
        if guessed:
            return guessed.lstrip(".")
    if original_name:
        suffix = Path(original_name).suffix.lstrip(".")
        if suffix:
            return suffix.lower()
    return "bin"


_ASSETS_DDL = """
CREATE TABLE IF NOT EXISTS _assets (
    hash_algorithm TEXT NOT NULL,
    hash_hex       TEXT NOT NULL,
    canonical_ref  TEXT GENERATED ALWAYS AS
                   ('asset:' || hash_algorithm || ':' || hash_hex) STORED,

    original_name  TEXT,
    mime           TEXT,
    ext            TEXT,

    width          INTEGER,
    height         INTEGER,
    byte_size      INTEGER,

    dominant_color TEXT,
    perceptual_hash TEXT,
    ocr_text       TEXT,

    created_at     TEXT NOT NULL,

    PRIMARY KEY (hash_algorithm, hash_hex)
);
CREATE INDEX IF NOT EXISTS _assets_canonical_ref ON _assets (canonical_ref);
"""

_ASSET_REFS_DDL = """
CREATE TABLE IF NOT EXISTS _asset_refs (
    record_id      TEXT NOT NULL,
    field_key      TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL,
    hash_hex       TEXT NOT NULL,
    PRIMARY KEY (record_id, field_key, hash_algorithm, hash_hex),
    FOREIGN KEY (hash_algorithm, hash_hex)
        REFERENCES _assets(hash_algorithm, hash_hex) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS _asset_refs_by_hash
    ON _asset_refs (hash_algorithm, hash_hex);
"""


class AssetStore:
    """Workspace-level store for content-addressed asset bytes."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self.assets_root = self.workspace_path / "assets"
        self.assets_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Schema (per-collection SQLite)
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_collection_asset_schema(store: CollectionStore) -> None:
        """Create ``_assets`` and ``_asset_refs`` in a collection database."""
        store.connect()
        cursor = store.conn.cursor()
        cursor.executescript(_ASSETS_DDL)
        cursor.executescript(_ASSET_REFS_DDL)
        store.conn.commit()

    @staticmethod
    def ensure_all_collections(workspace_path: Path, collection_db_paths: list[Path]) -> None:
        """Ensure asset schema exists in every collection DB before export."""
        from src.core.collection_store import CollectionStore

        for db_path in collection_db_paths:
            if not db_path.exists():
                continue
            store = CollectionStore(db_path)
            try:
                AssetStore.ensure_collection_asset_schema(store)
            finally:
                store.close()

    # ------------------------------------------------------------------
    # Byte storage
    # ------------------------------------------------------------------

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def asset_file_path(
        self,
        hash_hex: str,
        ext: str,
        algorithm: str = DEFAULT_HASH_ALGORITHM,
    ) -> Path:
        """``workspace/assets/sha256/ab/cd/<hash>.<ext>``"""
        return (
            self.assets_root
            / algorithm
            / hash_hex[:2]
            / hash_hex[2:4]
            / f"{hash_hex}.{ext}"
        )

    def store_bytes(
        self,
        data: bytes,
        *,
        store: CollectionStore,
        original_name: str | None = None,
        mime: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> str:
        """Write bytes to the workspace asset tree and register metadata.

        Returns the canonical reference ``asset:sha256:<hex>``.
        """
        hash_hex = self.hash_bytes(data)
        algorithm = DEFAULT_HASH_ALGORITHM
        ref = canonical_ref(hash_hex, algorithm)
        ext = ext_for_mime(mime, original_name)
        dest = self.asset_file_path(hash_hex, ext, algorithm)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(data)

        self._upsert_asset_row(
            store,
            algorithm=algorithm,
            hash_hex=hash_hex,
            original_name=original_name,
            mime=mime,
            ext=ext,
            width=width,
            height=height,
            byte_size=len(data),
        )
        return ref

    def resolve_bytes(self, ref: str) -> bytes | None:
        """Load asset bytes for a canonical reference, or None if missing."""
        parsed = parse_asset_ref(ref)
        if not parsed:
            return None
        algorithm, hash_hex = parsed
        store_row = self._find_on_disk(algorithm, hash_hex)
        if store_row is None:
            return None
        return store_row.read_bytes()

    def _find_on_disk(self, algorithm: str, hash_hex: str) -> Path | None:
        base = self.assets_root / algorithm / hash_hex[:2] / hash_hex[2:4]
        if not base.is_dir():
            return None
        for candidate in base.glob(f"{hash_hex}.*"):
            if candidate.is_file():
                return candidate
        return None

    # ------------------------------------------------------------------
    # Metadata / reference tracking
    # ------------------------------------------------------------------

    @staticmethod
    def _upsert_asset_row(
        store: CollectionStore,
        *,
        algorithm: str,
        hash_hex: str,
        original_name: str | None,
        mime: str | None,
        ext: str,
        width: int | None,
        height: int | None,
        byte_size: int,
    ) -> None:
        AssetStore.ensure_collection_asset_schema(store)
        now = datetime.now().isoformat()
        store.connect()
        cursor = store.conn.cursor()
        cursor.execute(
            """
            INSERT INTO _assets (
                hash_algorithm, hash_hex, original_name, mime, ext,
                width, height, byte_size, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(hash_algorithm, hash_hex) DO NOTHING
            """,
            (algorithm, hash_hex, original_name, mime, ext, width, height, byte_size, now),
        )
        store.conn.commit()

    @staticmethod
    def track_ref(
        store: CollectionStore,
        record_id: str | int,
        field_key: str,
        ref: str,
    ) -> None:
        """Record that *record_id* / *field_key* references *ref*."""
        parsed = parse_asset_ref(ref)
        if not parsed:
            return
        algorithm, hash_hex = parsed
        AssetStore.ensure_collection_asset_schema(store)
        store.connect()
        cursor = store.conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO _asset_refs
                (record_id, field_key, hash_algorithm, hash_hex)
            VALUES (?, ?, ?, ?)
            """,
            (str(record_id), field_key, algorithm, hash_hex),
        )
        store.conn.commit()

    @staticmethod
    def untrack_refs_for_record(store: CollectionStore, record_id: str | int) -> None:
        """Remove all asset references for a deleted record."""
        store.connect()
        cursor = store.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_asset_refs'"
        )
        if not cursor.fetchone():
            return
        cursor.execute(
            "DELETE FROM _asset_refs WHERE record_id = ?",
            (str(record_id),),
        )
        store.conn.commit()

    @staticmethod
    def format_for_spreadsheet(value: str | None, field_type: str) -> str:
        """Lossy export helper for CSV/Excel when *field_type* is ``image``."""
        if field_type != "image" or not value:
            return value or ""
        if parse_asset_ref(value):
            return value  # keep reference string; bytes are not exported
        return str(value)
