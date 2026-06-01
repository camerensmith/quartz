"""Quartz workspace bundle format (``.qz``).

A ``.qz`` file is a ZIP archive containing the full workspace: collection
SQLite databases (with ``_assets`` metadata), ``workspace.json``,
``subcollections.json``, collection/subcollection icons, and the
``assets/`` byte store.

Other export paths (raw ``.sqlite``, CSV, Excel) are unchanged and do not
include asset bytes — only references and metadata travel with those formats.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from src.core.asset_store import AssetStore
from src.core.version import VERSION
from src.core.workspace import Workspace

QZ_FORMAT_VERSION = 1
QZ_EXTENSION = ".qz"

# Top-level workspace entries included in every .qz bundle (relative paths).
_BUNDLE_ROOT_FILES = ("workspace.json", "subcollections.json")
_BUNDLE_DIRS = ("db", "icons", "subcollection_icons", "assets")


class QzPackager:
    """Pack and unpack Quartz workspace bundles."""

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.workspace_path = workspace.workspace_path

    def pack(self, target_path: Path) -> None:
        """Write a lossless ``.qz`` bundle to *target_path*."""
        target_path = Path(target_path)
        if target_path.suffix.lower() != QZ_EXTENSION:
            target_path = target_path.with_suffix(QZ_EXTENSION)

        # Ensure asset schema exists in all collection DBs before bundling.
        db_paths = self._collection_db_paths()
        AssetStore.ensure_all_collections(self.workspace_path, db_paths)

        manifest = self._build_manifest()
        with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Manifest first so readers can validate before extracting.
            zf.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )
            for rel in _BUNDLE_ROOT_FILES:
                src = self.workspace_path / rel
                if src.is_file():
                    zf.write(src, rel)

            for dir_name in _BUNDLE_DIRS:
                src_dir = self.workspace_path / dir_name
                if not src_dir.is_dir():
                    continue
                for file_path in src_dir.rglob("*"):
                    if file_path.is_file():
                        arc = file_path.relative_to(self.workspace_path).as_posix()
                        zf.write(file_path, arc)

            # Legacy per-collection attachment folders (pre-asset-store).
            for name in self.workspace.list_collections():
                attachments = self.workspace_path / name / "attachments"
                if attachments.is_dir():
                    for file_path in attachments.rglob("*"):
                        if file_path.is_file():
                            arc = file_path.relative_to(self.workspace_path).as_posix()
                            zf.write(file_path, arc)

    def unpack(self, qz_path: Path, dest_path: Path) -> Path:
        """Extract a ``.qz`` bundle into *dest_path*."""
        return unpack_qz(qz_path, dest_path)

    def _collection_db_paths(self) -> list[Path]:
        paths: list[Path] = []
        for name in self.workspace.list_collections():
            info = self.workspace.get_collection_info(name)
            if info:
                paths.append(self.workspace_path / info.db_path)
        return paths

    def _build_manifest(self) -> dict:
        collections_meta = []
        for name in self.workspace.list_collections():
            info = self.workspace.get_collection_info(name)
            if not info:
                continue
            collections_meta.append(
                {
                    "name": name,
                    "db_path": info.db_path,
                    "record_count": info.record_count,
                    "key_prefix": info.key_prefix,
                    "icon_path": info.icon_path,
                }
            )

        asset_count = 0
        assets_dir = self.workspace_path / "assets"
        if assets_dir.is_dir():
            asset_count = sum(1 for p in assets_dir.rglob("*") if p.is_file())

        return {
            "qz_format_version": QZ_FORMAT_VERSION,
            "quartz_app_version": VERSION,
            "created_at": datetime.now().isoformat(),
            "workspace_path": str(self.workspace_path.name),
            "collections": collections_meta,
            "asset_file_count": asset_count,
            "bundle_contract": (
                "Cell values store asset:sha256:<hex> references. "
                "Each collection .sqlite includes _assets metadata. "
                "This .qz bundle includes the bytes needed to rehydrate assets."
            ),
        }


def unpack_qz(qz_path: Path, dest_path: Path) -> Path:
    """Extract a ``.qz`` bundle into *dest_path* and return the workspace root."""
    qz_path = Path(qz_path)
    dest_path = Path(dest_path)
    dest_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(qz_path, "r") as zf:
        manifest_raw = zf.read("manifest.json")
        manifest = json.loads(manifest_raw)
        if manifest.get("qz_format_version", 0) > QZ_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported .qz format version {manifest['qz_format_version']}. "
                "Please upgrade Quartz."
            )
        for name in zf.namelist():
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"Unsafe path in .qz archive: {name}")
        zf.extractall(dest_path)

    return dest_path


def import_qz_to_workspace(qz_path: Path, workspace_parent: Path, workspace_name: str) -> Workspace:
    """Extract a ``.qz`` file into a new workspace folder and return a Workspace."""
    dest = workspace_parent / workspace_name
    if dest.exists():
        raise FileExistsError(f"Workspace folder already exists: {dest}")

    unpack_qz(qz_path, dest)
    return Workspace(dest)
