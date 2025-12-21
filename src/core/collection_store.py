"""Collection database store and schema management"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import json


class CollectionStore:
    """Manages a single collection's SQLite database"""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
    
    def connect(self):
        """Open database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def initialize_schema(self):
        """Initialize database schema"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Fields table (field definitions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_key TEXT UNIQUE NOT NULL,
                field_type TEXT NOT NULL,
                label TEXT NOT NULL,
                required INTEGER DEFAULT 0,
                default_value TEXT,
                validation_rules TEXT,  -- JSON
                options TEXT,  -- JSON (for select, multi-select)
                indexed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Layout nodes (form designer layout)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS layout_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_key TEXT,
                node_type TEXT NOT NULL,  -- field, label, divider, section, spacer
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                properties TEXT,  -- JSON
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (field_key) REFERENCES fields(field_key)
            )
        """)
        
        # Records table (dynamic columns will be added via ALTER TABLE)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_uuid TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Dependencies registry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,  -- field, layout, search
                source_id TEXT NOT NULL,
                target_type TEXT NOT NULL,  -- field
                target_id TEXT NOT NULL,
                dependency_type TEXT NOT NULL,  -- reference, validation, layout
                created_at TEXT NOT NULL
            )
        """)
        
        # Relationships table (for cross-collection relationships)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relationship_name TEXT NOT NULL,
                source_collection TEXT NOT NULL,
                source_field_key TEXT NOT NULL,
                target_collection TEXT NOT NULL,
                target_field_key TEXT NOT NULL,
                relationship_type TEXT NOT NULL,  -- one_to_one, one_to_many, many_to_many
                cascade_delete INTEGER DEFAULT 0,  -- 0 = no, 1 = yes
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_collection, source_field_key, target_collection, target_field_key)
            )
        """)
        
        # FTS5 search index (will be created when fields are indexed)
        # This is handled dynamically
        
        self.conn.commit()
    
    def add_field(self, field_key: str, field_type: str, label: str,
                  required: bool = False, default_value: Optional[str] = None,
                  validation_rules: Optional[Dict] = None,
                  options: Optional[List] = None, indexed: bool = False):
        """Add a new field to the schema"""
        self.connect()
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        # Add to fields table
        cursor.execute("""
            INSERT INTO fields (field_key, field_type, label, required, default_value,
                               validation_rules, options, indexed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            field_key, field_type, label, 1 if required else 0,
            default_value,
            json.dumps(validation_rules) if validation_rules else None,
            json.dumps(options) if options else None,
            1 if indexed else 0,
            now, now
        ))
        
        # Add column to records table
        cursor.execute(f"ALTER TABLE records ADD COLUMN {field_key} TEXT")
        
        # If indexed, add to FTS5 index
        if indexed:
            self.update_fts_index()
        
        self.conn.commit()
    
    def update_fts_index(self):
        """Create or update FTS5 search index"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Get all indexed fields
        cursor.execute("SELECT field_key FROM fields WHERE indexed = 1")
        indexed_fields = [row[0] for row in cursor.fetchall()]
        
        if not indexed_fields:
            return
        
        # Drop existing FTS table if it exists
        cursor.execute("DROP TABLE IF EXISTS records_fts")
        
        # Create FTS5 table with indexed fields
        fts_columns = ", ".join(indexed_fields)
        cursor.execute(f"""
            CREATE VIRTUAL TABLE records_fts USING fts5(
                {fts_columns},
                content='records',
                content_rowid='id'
            )
        """)
        
        # Populate FTS index
        if indexed_fields:
            select_cols = ", ".join(indexed_fields)
            cursor.execute(f"""
                INSERT INTO records_fts (rowid, {select_cols})
                SELECT id, {select_cols} FROM records
            """)
        
        self.conn.commit()
    
    def list_fields(self) -> List[Dict]:
        """List all fields"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT field_key, field_type, label, required, default_value,
                   validation_rules, options, indexed
            FROM fields
            ORDER BY created_at
        """)
        
        fields = []
        for row in cursor.fetchall():
            field = {
                "key": row[0],
                "type": row[1],
                "label": row[2],
                "required": bool(row[3]),
                "default_value": row[4],
                "validation_rules": json.loads(row[5]) if row[5] else None,
                "options": json.loads(row[6]) if row[6] else None,
                "indexed": bool(row[7])
            }
            fields.append(field)
        
        return fields
    
    def get_field(self, field_key: str) -> Optional[Dict]:
        """Get a single field definition"""
        fields = self.list_fields()
        return next((f for f in fields if f["key"] == field_key), None)
    
    def add_record(self, data: Dict[str, Any]) -> int:
        """Add a new record"""
        self.connect()
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        import uuid
        record_uuid = str(uuid.uuid4())
        
        # Build column list and values
        columns = ["record_uuid", "created_at", "updated_at"]
        placeholders = ["?", "?", "?"]
        values = [record_uuid, now, now]
        
        for key, value in data.items():
            columns.append(key)
            placeholders.append("?")
            # Convert value to string for storage
            if value is None:
                values.append(None)
            elif isinstance(value, (dict, list)):
                values.append(json.dumps(value))
            else:
                values.append(str(value))
        
        sql = f"""
            INSERT INTO records ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """
        cursor.execute(sql, values)
        record_id = cursor.lastrowid
        
        # Update FTS index if needed
        self.update_fts_index()
        
        self.conn.commit()
        return record_id
    
    def update_record(self, record_id: int, data: Dict[str, Any]):
        """Update an existing record"""
        self.connect()
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        updates = ["updated_at = ?"]
        values = [now]
        
        for key, value in data.items():
            updates.append(f"{key} = ?")
            if value is None:
                values.append(None)
            elif isinstance(value, (dict, list)):
                values.append(json.dumps(value))
            else:
                values.append(str(value))
        
        values.append(record_id)
        sql = f"UPDATE records SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(sql, values)
        
        # Update FTS index
        self.update_fts_index()
        
        self.conn.commit()
    
    def delete_record(self, record_id: int):
        """Delete a record"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
        
        # Update FTS index
        self.update_fts_index()
        
        self.conn.commit()
    
    def get_record(self, record_id: int) -> Optional[Dict]:
        """Get a single record"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def list_records(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict]:
        """List records"""
        self.connect()
        cursor = self.conn.cursor()
        sql = "SELECT * FROM records ORDER BY id"
        if limit:
            sql += f" LIMIT {limit} OFFSET {offset}"
        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
    
    def count_records(self) -> int:
        """Count total records"""
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM records")
        return cursor.fetchone()[0]
    
    def search_records(self, query: str, limit: Optional[int] = None,
                       filter_tree: Optional[Dict] = None) -> List[Dict]:
        """Search records using FTS5 or query parser"""
        self.connect()
        cursor = self.conn.cursor()
        
        # If filter tree provided, use advanced query
        if filter_tree:
            from src.core.query_parser import QueryParser
            fields = [f["key"] for f in self.list_fields()]
            parser = QueryParser(fields)
            where_clause, params = parser.build_sql_filter(filter_tree, "r")
            if not where_clause:
                return []
            sql = f"SELECT r.* FROM records r WHERE {where_clause}"
            if limit:
                sql += f" LIMIT {limit}"
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        
        # Simple FTS5 search (backward compatible)
        # Check if FTS table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'records_fts'
        """)
        if not cursor.fetchone():
            # Fallback to simple LIKE search
            return self.simple_search(query, limit)
        
        # Use FTS5 search
        sql = """
            SELECT r.* FROM records r
            JOIN records_fts fts ON r.id = fts.rowid
            WHERE records_fts MATCH ?
        """
        if limit:
            sql += f" LIMIT {limit}"
        cursor.execute(sql, (query,))
        return [dict(row) for row in cursor.fetchall()]
    
    def simple_search(self, query: str, limit: Optional[int] = None) -> List[Dict]:
        """Fallback simple search using LIKE"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Get all text fields
        fields = self.list_fields()
        text_fields = [f["key"] for f in fields if f["type"] in ("text", "notes")]
        
        if not text_fields:
            return []
        
        conditions = " OR ".join([f"{field} LIKE ?" for field in text_fields])
        sql = f"SELECT * FROM records WHERE {conditions}"
        if limit:
            sql += f" LIMIT {limit}"
        pattern = f"%{query}%"
        cursor.execute(sql, [pattern] * len(text_fields))
        return [dict(row) for row in cursor.fetchall()]
