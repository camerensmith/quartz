"""Workspace and collection registry management"""

import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from src.core.collection_store import copy_database
from src.core.json_store import read_json, write_json_atomic

logger = logging.getLogger(__name__)


@dataclass
class CollectionInfo:
    """Metadata for a collection"""
    name: str
    db_path: str  # Relative to workspace
    created_at: str
    updated_at: str
    record_count: int = 0
    icon_path: str | None = None  # Path to collection icon/image
    description: str | None = None  # Short description of the collection
    order: int | None = None  # Display order (for drag and drop)
    key_prefix: str | None = None  # Prefix for record IDs (e.g., "REST" -> "REST_1", "REST_2")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CollectionInfo':
        # Handle missing fields for backward compatibility
        if 'icon_path' not in data:
            data['icon_path'] = None
        if 'description' not in data:
            data['description'] = None
        if 'order' not in data:
            data['order'] = None
        if 'key_prefix' not in data:
            data['key_prefix'] = None
        # Ignore keys written by newer versions; save_registry keeps them in the file
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class Workspace:
    """Manages workspace and collection registry"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.workspace_path / "workspace.json"
        self.collections: dict[str, CollectionInfo] = {}
        # Registry entries as read, so saving keeps keys and entries this version doesn't understand
        self._raw_collections: dict[str, dict] = {}
        self._raw_extra: dict = {}
        self._unreadable: set[str] = set()
        # Set when workspace.json couldn't be read; it was moved here instead of being overwritten
        self.registry_backup: Path | None = None
        # Collections re-registered from db/ after an unreadable workspace.json
        self.recovered_collections: list[str] = []
        self.load_registry()

    def load_registry(self):
        """Load collection registry"""
        self.collections = {}
        self._raw_collections = {}
        self._raw_extra = {}
        self._unreadable = set()
        self.recovered_collections = []
        data, self.registry_backup = read_json(self.registry_path)
        if data is None:
            if self.registry_backup:
                # The databases are intact; rebuild the list from them so the collections reappear
                self.recovered_collections = self._recover_from_databases()
                if self.recovered_collections:
                    self.save_registry()
            return

        self._raw_extra = {k: v for k, v in data.items() if k != "collections"}
        raw = data.get("collections", {})
        if not isinstance(raw, dict):
            logger.error("Ignoring malformed 'collections' in %s", self.registry_path)
            raw = {}
        self._raw_collections = raw
        for name, info in raw.items():
            try:
                self.collections[name] = CollectionInfo.from_dict(dict(info))
            except (TypeError, ValueError):
                # Keep it in the file; just don't show it
                self._unreadable.add(name)
                logger.error("Skipping unreadable registry entry %r in %s", name, self.registry_path)

        # Migrate old database structure to new db/ folder
        try:
            self._migrate_database_structure()
        except OSError:
            logger.exception("Could not migrate collection databases in %s", self.workspace_path)

    def _recover_from_databases(self) -> list[str]:
        """Register every db/*.sqlite file; descriptions and custom order aren't recoverable"""
        import sqlite3
        from datetime import datetime

        recovered = []
        for order, db_path in enumerate(sorted((self.workspace_path / "db").glob("*.sqlite"))):
            name = db_path.stem
            try:
                conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
                try:
                    row = conn.execute("SELECT prefix FROM id_sequence LIMIT 1").fetchone()
                    key_prefix = row[0] if row else None
                except sqlite3.OperationalError:
                    key_prefix = None  # No id_sequence table: integer record IDs
                finally:
                    conn.close()
            except sqlite3.Error:
                logger.exception("Could not open %s while recovering the collection list", db_path)
                continue
            modified = datetime.fromtimestamp(db_path.stat().st_mtime).isoformat()
            icon = self.workspace_path / "icons" / f"{name}.png"
            self.collections[name] = CollectionInfo(
                name=name,
                db_path=f"db/{name}.sqlite",
                created_at=modified,
                updated_at=modified,
                icon_path=f"icons/{name}.png" if icon.exists() else None,
                order=order,
                key_prefix=key_prefix,
            )
            recovered.append(name)
        if recovered:
            logger.warning("Recovered %d collections from %s", len(recovered), self.workspace_path / "db")
        return recovered

    def _migrate_database_structure(self):
        """Migrate collections from old structure (collection_name/collection.sqlite) to new (db/collection_name.sqlite)"""
        import shutil
        from datetime import datetime

        db_folder = self.workspace_path / "db"
        db_folder.mkdir(exist_ok=True)
        migrated = False

        for name, info in list(self.collections.items()):
            old_db_path = self.workspace_path / info.db_path
            # Check if using old structure (collection_name/collection.sqlite)
            if old_db_path.exists() and info.db_path == f"{name}/collection.sqlite":
                # Migrate to new structure
                new_db_path = db_folder / f"{name}.sqlite"
                if not new_db_path.exists():
                    # Move database; on failure leave this one where it is and still record the others
                    try:
                        shutil.move(str(old_db_path), str(new_db_path))
                    except OSError:
                        logger.exception("Could not move %s to %s", old_db_path, new_db_path)
                        continue
                    migrated = True
                    # Update registry
                    info.db_path = f"db/{name}.sqlite"
                    info.updated_at = datetime.now().isoformat()

            # Keep collection directory for attachments (if it exists)
            collection_dir = self.workspace_path / name
            if collection_dir.exists() and not (collection_dir / "collection.sqlite").exists():
                # Directory still needed for attachments, keep it
                pass

        if migrated:
            self.save_registry()

    def save_registry(self):
        """Save collection registry"""
        def raw(name: str) -> dict:
            entry = self._raw_collections.get(name)
            return entry if isinstance(entry, dict) else {}

        collections = {
            name: {**raw(name), **info.to_dict()}
            for name, info in self.collections.items()
        }
        # Entries this version couldn't read stay as they were
        for name in self._unreadable - collections.keys():
            collections[name] = self._raw_collections[name]
        data = {**self._raw_extra, "collections": collections}
        write_json_atomic(self.registry_path, data)
        self._raw_collections = collections

    def list_collections(self) -> list[str]:
        """List all collection names in order"""
        # Sort by order field if present, otherwise by name
        collections_with_order = [
            (name, info.order if info.order is not None else float('inf'))
            for name, info in self.collections.items()
        ]
        collections_with_order.sort(key=lambda x: (x[1], x[0]))  # Sort by order, then by name
        return [name for name, _ in collections_with_order]

    def get_collection_info(self, name: str) -> CollectionInfo | None:
        """Get collection info by name"""
        return self.collections.get(name)

    def create_collection(self, name: str, key_prefix: str | None = None) -> Path:
        """Create a new collection"""
        if name in self.collections:
            raise ValueError(f"Collection '{name}' already exists")

        # Create db folder if it doesn't exist
        db_folder = self.workspace_path / "db"
        db_folder.mkdir(exist_ok=True)

        # Create collection directory for attachments
        collection_dir = self.workspace_path / name
        collection_dir.mkdir(exist_ok=True)
        attachments_dir = collection_dir / "attachments"
        attachments_dir.mkdir(exist_ok=True)

        # Create SQLite database in db folder
        db_path = db_folder / f"{name}.sqlite"

        # Initialize database schema
        from src.core.collection_store import CollectionStore
        store = CollectionStore(db_path)
        # Pass key_prefix to initialize schema if provided
        store.initialize_schema(key_prefix=key_prefix)

        # Register collection
        from datetime import datetime
        now = datetime.now().isoformat()
        # Set order to be after all existing collections
        max_order = max([info.order for info in self.collections.values() if info.order is not None], default=-1)
        info = CollectionInfo(
            name=name,
            db_path=str(db_path.relative_to(self.workspace_path)),
            created_at=now,
            updated_at=now,
            record_count=0,
            icon_path=None,
            description=None,
            order=max_order + 1,
            key_prefix=key_prefix
        )
        self.collections[name] = info
        self.save_registry()

        return db_path

    def set_collection_icon(self, name: str, icon_path: Path | None):
        """Set collection icon/image"""
        if name not in self.collections:
            raise ValueError(f"Collection '{name}' not found")

        info = self.collections[name]
        if icon_path:
            # Copy icon to collection directory
            icons_dir = self.workspace_path / "icons"
            icons_dir.mkdir(exist_ok=True)
            target_icon = icons_dir / f"{name}.png"
            import shutil
            shutil.copy2(icon_path, target_icon)
            info.icon_path = str(target_icon.relative_to(self.workspace_path))
        else:
            # Remove icon
            if info.icon_path:
                icon_full_path = self.workspace_path / info.icon_path
                if icon_full_path.exists():
                    icon_full_path.unlink()
                info.icon_path = None

        from datetime import datetime
        info.updated_at = datetime.now().isoformat()
        self.save_registry()

    def get_collection_icon_path(self, name: str) -> Path | None:
        """Get collection icon path"""
        if name not in self.collections:
            return None

        info = self.collections[name]
        if info.icon_path:
            icon_path = self.workspace_path / info.icon_path
            if icon_path.exists():
                return icon_path
        return None

    def rename_collection(self, old_name: str, new_name: str):
        """Rename a collection"""
        if old_name not in self.collections:
            raise ValueError(f"Collection '{old_name}' not found")
        if new_name in self.collections:
            raise ValueError(f"Collection '{new_name}' already exists")

        # Rename collection directory
        old_dir = self.workspace_path / old_name
        new_dir = self.workspace_path / new_name
        if old_dir.exists():
            old_dir.rename(new_dir)

        # Rename database file
        db_folder = self.workspace_path / "db"
        old_db = db_folder / f"{old_name}.sqlite"
        new_db = db_folder / f"{new_name}.sqlite"
        if old_db.exists():
            old_db.rename(new_db)

        # Rename icon if exists
        icons_dir = self.workspace_path / "icons"
        old_icon = icons_dir / f"{old_name}.png"
        new_icon = icons_dir / f"{new_name}.png"
        if old_icon.exists():
            old_icon.rename(new_icon)

        # Update registry
        info = self.collections.pop(old_name)
        self._raw_collections[new_name] = self._raw_collections.pop(old_name, {})
        info.name = new_name
        # Update db_path
        info.db_path = f"db/{new_name}.sqlite"
        # Update icon_path
        if info.icon_path:
            info.icon_path = f"icons/{new_name}.png"
        self.collections[new_name] = info
        self.save_registry()

    def delete_collection(self, name: str, backup: bool = True):
        """Delete a collection"""
        if name not in self.collections:
            raise ValueError(f"Collection '{name}' not found")

        import shutil
        from datetime import datetime

        collection_dir = self.workspace_path / name
        db_folder = self.workspace_path / "db"
        db_path = db_folder / f"{name}.sqlite"
        icons_dir = self.workspace_path / "icons"
        icon_path = icons_dir / f"{name}.png"

        # Optional backup
        if backup:
            backup_dir = self.workspace_path / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_name = f"{name}{datetime.now().strftime('%Y%m%d%H%M%S')}"
            backup_path = backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)

            # Backup database
            if db_path.exists():
                copy_database(db_path, backup_path / f"{name}.sqlite")

            # Backup collection directory
            if collection_dir.exists():
                shutil.copytree(collection_dir, backup_path / name)

            # Backup icon
            if icon_path.exists():
                shutil.copy2(icon_path, backup_path / f"{name}.png")

        # Remove from registry
        del self.collections[name]
        self.save_registry()

        # Remove files
        if collection_dir.exists():
            shutil.rmtree(collection_dir)

        # Try to delete database file with retry (Windows file locking issue)
        if db_path.exists():
            import time
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    db_path.unlink()
                    break
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.2)  # Wait 200ms before retry
                    else:
                        # Last attempt failed, raise the error
                        raise PermissionError(
                            f"Cannot delete database file '{db_path}'. "
                            f"The file may be locked by another process. "
                            f"Please close any applications using this collection and try again."
                        ) from e

        if icon_path.exists():
            icon_path.unlink()

    def duplicate_collection(self, name: str, new_name: str) -> Path:
        """Duplicate a collection"""
        if name not in self.collections:
            raise ValueError(f"Collection '{name}' not found")
        if new_name in self.collections:
            raise ValueError(f"Collection '{new_name}' already exists")

        import shutil

        # Duplicate collection directory
        old_dir = self.workspace_path / name
        new_dir = self.workspace_path / new_name
        if old_dir.exists():
            shutil.copytree(old_dir, new_dir)

        # Duplicate database file
        db_folder = self.workspace_path / "db"
        old_db = db_folder / f"{name}.sqlite"
        new_db = db_folder / f"{new_name}.sqlite"
        if old_db.exists():
            copy_database(old_db, new_db)

        # Duplicate icon if exists
        icons_dir = self.workspace_path / "icons"
        old_icon = icons_dir / f"{name}.png"
        new_icon = icons_dir / f"{new_name}.png"
        if old_icon.exists():
            shutil.copy2(old_icon, new_icon)

        # Register new collection
        from datetime import datetime
        now = datetime.now().isoformat()
        old_info = self.collections[name]
        info = CollectionInfo(
            name=new_name,
            db_path=f"db/{new_name}.sqlite",
            created_at=now,
            updated_at=now,
            record_count=old_info.record_count,
            icon_path=f"icons/{new_name}.png" if old_info.icon_path else None
        )
        self.collections[new_name] = info
        self.save_registry()

        return new_db

    def set_collection_order(self, collection_names: list[str]):
        """Set the display order of collections"""
        from datetime import datetime

        # Update order for each collection
        for index, name in enumerate(collection_names):
            if name in self.collections:
                info = self.collections[name]
                info.order = index
                info.updated_at = datetime.now().isoformat()

        # Collections not in the list get a high order (appear at end)
        max_order = len(collection_names)
        for name, info in self.collections.items():
            if name not in collection_names:
                if info.order is None or info.order >= max_order:
                    info.order = max_order
                    info.updated_at = datetime.now().isoformat()

        self.save_registry()
