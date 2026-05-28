"""Workspace comparison and sync utilities"""

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.core.workspace import CollectionInfo, Workspace


@dataclass
class CollectionDiff:
    """Comparison of a single collection across two workspaces."""

    name: str
    in_local: bool
    in_cloud: bool
    local_updated_at: str | None = None
    cloud_updated_at: str | None = None
    local_size_bytes: int | None = None
    cloud_size_bytes: int | None = None
    local_record_count: int | None = None
    cloud_record_count: int | None = None
    local_field_count: int | None = None
    cloud_field_count: int | None = None


def compare_workspaces(
    local_workspace: Workspace,
    cloud_workspace: Workspace,
) -> list[CollectionDiff]:
    """Return a diff list for every collection found in either workspace."""
    all_names = sorted(
        set(local_workspace.list_collections()) | set(cloud_workspace.list_collections())
    )
    diffs: list[CollectionDiff] = []
    for name in all_names:
        local_info = local_workspace.get_collection_info(name)
        cloud_info = cloud_workspace.get_collection_info(name)

        diff = CollectionDiff(
            name=name,
            in_local=local_info is not None,
            in_cloud=cloud_info is not None,
        )

        if local_info:
            diff.local_updated_at = local_info.updated_at
            diff.local_record_count = local_info.record_count
            local_db = local_workspace.workspace_path / local_info.db_path
            if local_db.exists():
                diff.local_size_bytes = local_db.stat().st_size
                diff.local_field_count = _count_fields(local_db)

        if cloud_info:
            diff.cloud_updated_at = cloud_info.updated_at
            diff.cloud_record_count = cloud_info.record_count
            cloud_db = cloud_workspace.workspace_path / cloud_info.db_path
            if cloud_db.exists():
                diff.cloud_size_bytes = cloud_db.stat().st_size
                diff.cloud_field_count = _count_fields(cloud_db)

        diffs.append(diff)
    return diffs


def _count_fields(db_path: Path) -> int:
    """Return the number of fields defined in a collection database."""
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM fields")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def sync_collection(
    name: str,
    source_workspace: Workspace,
    target_workspace: Workspace,
) -> None:
    """Copy a collection from *source_workspace* into *target_workspace*.

    Overwrites any existing copy in the target.  The target workspace's
    registry (workspace.json) is updated to reflect the copy.
    """
    src_info = source_workspace.get_collection_info(name)
    if src_info is None:
        raise ValueError(f"Collection '{name}' not found in source workspace")

    src_db = source_workspace.workspace_path / src_info.db_path

    # --- Database file ---
    target_db_folder = target_workspace.workspace_path / "db"
    target_db_folder.mkdir(parents=True, exist_ok=True)
    target_db = target_db_folder / f"{name}.sqlite"
    if src_db.exists():
        shutil.copy2(src_db, target_db)

    # --- Attachments directory ---
    src_attachments = source_workspace.workspace_path / name
    target_attachments = target_workspace.workspace_path / name
    if src_attachments.exists():
        if target_attachments.exists():
            shutil.rmtree(target_attachments)
        shutil.copytree(src_attachments, target_attachments)

    # --- Icon ---
    src_icon = source_workspace.workspace_path / "icons" / f"{name}.png"
    if src_icon.exists():
        target_icons = target_workspace.workspace_path / "icons"
        target_icons.mkdir(exist_ok=True)
        shutil.copy2(src_icon, target_icons / f"{name}.png")

    # --- Registry ---
    if name in target_workspace.collections:
        tgt = target_workspace.collections[name]
        tgt.updated_at = src_info.updated_at
        tgt.record_count = src_info.record_count
        tgt.icon_path = src_info.icon_path
        tgt.description = src_info.description
        tgt.key_prefix = src_info.key_prefix
    else:
        max_order = max(
            (i.order for i in target_workspace.collections.values() if i.order is not None),
            default=-1,
        )
        target_workspace.collections[name] = CollectionInfo(
            name=name,
            db_path=f"db/{name}.sqlite",
            created_at=src_info.created_at,
            updated_at=src_info.updated_at,
            record_count=src_info.record_count,
            icon_path=src_info.icon_path,
            description=src_info.description,
            order=max_order + 1,
            key_prefix=src_info.key_prefix,
        )

    target_workspace.save_registry()
