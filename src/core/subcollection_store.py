"""Subcollection data layer — stored as JSON alongside the workspace registry"""

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class SubcollectionInfo:
    """Metadata for a single subcollection"""
    id: str
    name: str
    color: str  # hex, e.g. "#8000FF"
    order: int
    record_ids: list  # list of record primary-key values (integers or strings)
    icon_path: str | None = None  # relative to workspace root

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SubcollectionInfo":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Untitled"),
            color=data.get("color", "#8000FF"),
            order=data.get("order", 0),
            record_ids=data.get("record_ids", []),
            icon_path=data.get("icon_path"),
        )


class SubcollectionStore:
    """Reads/writes subcollection metadata from workspace/subcollections.json.

    File structure::

        {
          "CollectionName": [
            { "id": "...", "name": "...", "color": "#...", "order": 0,
              "record_ids": [1, 2, 3], "icon_path": null }
          ]
        }
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self.store_path = self.workspace_path / "subcollections.json"
        self._data: dict[str, list[dict]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self):
        if self.store_path.exists():
            try:
                with open(self.store_path, encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        with open(self.store_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def _get_list(self, collection_name: str) -> list[dict]:
        return self._data.get(collection_name, [])

    def _set_list(self, collection_name: str, items: list[dict]):
        self._data[collection_name] = items
        self._save()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_for_collection(self, collection_name: str) -> list[SubcollectionInfo]:
        """Return subcollections for *collection_name*, sorted by order."""
        items = [SubcollectionInfo.from_dict(d) for d in self._get_list(collection_name)]
        items.sort(key=lambda s: s.order)
        return items

    def create(self, collection_name: str, name: str, color: str = "#8000FF") -> SubcollectionInfo:
        """Create a new (empty) subcollection and persist it."""
        items = self._get_list(collection_name)
        max_order = max((d.get("order", 0) for d in items), default=-1)
        sub = SubcollectionInfo(
            id=str(uuid.uuid4()),
            name=name,
            color=color,
            order=max_order + 1,
            record_ids=[],
            icon_path=None,
        )
        items.append(sub.to_dict())
        self._set_list(collection_name, items)
        return sub

    def rename(self, collection_name: str, sub_id: str, new_name: str):
        """Rename a subcollection."""
        items = self._get_list(collection_name)
        for item in items:
            if item["id"] == sub_id:
                item["name"] = new_name
                break
        self._set_list(collection_name, items)

    def set_icon(self, collection_name: str, sub_id: str, icon_path: str | None):
        """Set the icon path (relative to workspace root)."""
        items = self._get_list(collection_name)
        for item in items:
            if item["id"] == sub_id:
                item["icon_path"] = icon_path
                break
        self._set_list(collection_name, items)

    def set_color(self, collection_name: str, sub_id: str, color: str):
        """Update the hex color of a subcollection."""
        items = self._get_list(collection_name)
        for item in items:
            if item["id"] == sub_id:
                item["color"] = color
                break
        self._set_list(collection_name, items)

    def set_order(self, collection_name: str, ordered_ids: list[str]):
        """Persist the display order given a list of sub IDs in the desired order."""
        items = self._get_list(collection_name)
        id_to_pos = {sid: pos for pos, sid in enumerate(ordered_ids)}
        for item in items:
            item["order"] = id_to_pos.get(item["id"], len(ordered_ids))
        self._set_list(collection_name, items)

    def add_records(self, collection_name: str, sub_id: str, record_ids: list):
        """Add record IDs to a subcollection (deduplicates)."""
        items = self._get_list(collection_name)
        for item in items:
            if item["id"] == sub_id:
                existing = {str(r) for r in item.get("record_ids", [])}
                existing.update(str(r) for r in record_ids)
                item["record_ids"] = sorted(existing)
                break
        self._set_list(collection_name, items)

    def remove_records(self, collection_name: str, sub_id: str, record_ids: list):
        """Remove record IDs from a subcollection."""
        to_remove = set(record_ids)
        items = self._get_list(collection_name)
        for item in items:
            if item["id"] == sub_id:
                item["record_ids"] = [r for r in item.get("record_ids", []) if r not in to_remove]
                break
        self._set_list(collection_name, items)

    def delete(self, collection_name: str, sub_id: str):
        """Delete a subcollection entirely."""
        items = [d for d in self._get_list(collection_name) if d["id"] != sub_id]
        self._set_list(collection_name, items)

    def delete_all_for_collection(self, collection_name: str):
        """Remove all subcollections for a collection (e.g. when collection is deleted)."""
        if collection_name in self._data:
            del self._data[collection_name]
            self._save()
