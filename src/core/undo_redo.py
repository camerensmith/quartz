"""Undo/Redo command system"""

from typing import Any, Dict, Optional, Callable
from abc import ABC, abstractmethod


class Command(ABC):
    """Base class for undoable commands"""
    
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
    
    def __init__(self, store, record_id: int, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        self.store = store
        self.record_id = record_id
        self.old_data = old_data.copy()
        self.new_data = new_data.copy()
    
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
    
    def __init__(self, store, record_id: int, data: Dict[str, Any]):
        self.store = store
        self.record_id = record_id
        self.data = data.copy()
    
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
    
    def __init__(self, store, record_id: int, data: Dict[str, Any]):
        self.store = store
        self.record_id = record_id
        self.data = data.copy()
    
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

