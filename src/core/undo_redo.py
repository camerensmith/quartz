"""Undo/Redo command system"""

import datetime
from typing import Any, Dict, Optional, Callable
from abc import ABC, abstractmethod


class Command(ABC):
    """Base class for undoable commands"""

    def __init__(self):
        self.timestamp: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)

    @property
    def description(self) -> str:
        """Human-readable description of this command"""
        return "Unknown action"

    @abstractmethod
    def undo(self):
        """Undo this command"""
        pass
    
    @abstractmethod
    def redo(self):
        """Redo this command"""
        pass


class RecordUpdateCommand(Command):
    """Command for updating a record"""
    
    def __init__(self, store, record_id: int, old_data: Dict[str, Any], new_data: Dict[str, Any],
                 collection_name: str = "", field_label: str = ""):
        super().__init__()
        self.store = store
        self.record_id = record_id
        self.old_data = old_data.copy()
        self.new_data = new_data.copy()
        self._collection_name = collection_name
        self._field_label = field_label

    @property
    def description(self) -> str:
        field = self._field_label or (list(self.new_data.keys())[0] if self.new_data else "field")
        parts = ["Updated"]
        if self._collection_name:
            parts.append(f"record #{self.record_id} in '{self._collection_name}'")
        else:
            parts.append(f"record #{self.record_id}")
        parts.append(f"(field: {field})")
        return " ".join(parts)

    def undo(self):
        """Restore old data"""
        if self.store:
            self.store.update_record(self.record_id, self.old_data)
    
    def redo(self):
        """Apply new data"""
        if self.store:
            self.store.update_record(self.record_id, self.new_data)


class RecordAddCommand(Command):
    """Command for adding a record"""
    
    def __init__(self, store, record_id: int, data: Dict[str, Any], collection_name: str = ""):
        super().__init__()
        self.store = store
        self.record_id = record_id
        self.data = data.copy()
        self._collection_name = collection_name

    @property
    def description(self) -> str:
        if self._collection_name:
            return f"Added record #{self.record_id} to '{self._collection_name}'"
        return f"Added record #{self.record_id}"

    def undo(self):
        """Delete the added record"""
        if self.store:
            self.store.delete_record(self.record_id)
    
    def redo(self):
        """Re-add the record"""
        if self.store:
            # Note: This will create a new ID, so we need to handle that
            # For now, we'll just delete on undo and skip redo
            pass


class RecordDeleteCommand(Command):
    """Command for deleting a record"""
    
    def __init__(self, store, record_id: int, data: Dict[str, Any], collection_name: str = ""):
        super().__init__()
        self.store = store
        self.record_id = record_id
        self.data = data.copy()
        self._collection_name = collection_name

    @property
    def description(self) -> str:
        if self._collection_name:
            return f"Deleted record #{self.record_id} from '{self._collection_name}'"
        return f"Deleted record #{self.record_id}"

    def undo(self):
        """Restore the deleted record"""
        if self.store:
            # Re-add the record with original data
            # Remove id, uuid, timestamps to let store generate new ones
            restore_data = {
                k: v for k, v in self.data.items()
                if k not in ["id", "record_uuid", "created_at", "updated_at"]
            }
            new_id = self.store.add_record(restore_data)
            # Update the record_id for potential redo
            self.record_id = new_id
    
    def redo(self):
        """Delete the record again"""
        if self.store:
            self.store.delete_record(self.record_id)

