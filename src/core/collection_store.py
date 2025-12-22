"""Collection database store and schema management"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
import json


class CollectionStore:
    """Manages a single collection's SQLite database"""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self.key_prefix: Optional[str] = None  # Prefix for record IDs (e.g., "REST" -> "REST_1")
    
    def connect(self):
        """Open database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Performance optimizations for large datasets
            self.conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging for better concurrency
            self.conn.execute("PRAGMA synchronous = NORMAL")  # Balance between safety and speed
            self.conn.execute("PRAGMA cache_size = -64000")  # 64MB cache (negative = KB)
            self.conn.execute("PRAGMA temp_store = MEMORY")  # Store temp tables in memory
            self.conn.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O
    
    def close(self):
        """Close database connection"""
        if self.conn:
            try:
                # Commit any pending transactions
                self.conn.commit()
            except Exception:
                # If commit fails, rollback
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            finally:
                # Close the connection
                self.conn.close()
                self.conn = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def initialize_schema(self, key_prefix: Optional[str] = None):
        """Initialize database schema"""
        self.connect()
        self.key_prefix = key_prefix
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
                field_order INTEGER DEFAULT 0,  -- Display order in form
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # Add order column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE fields ADD COLUMN field_order INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
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
        
        # Records table - use TEXT ID if prefix is provided, otherwise INTEGER
        if key_prefix:
            # Use TEXT ID with prefix
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    record_uuid TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            # Create indexes for faster sorting and queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_records_created_at ON records(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_records_updated_at ON records(updated_at)
            """)
            # Create sequence table to track counter for this prefix
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS id_sequence (
                    prefix TEXT PRIMARY KEY,
                    counter INTEGER DEFAULT 0
                )
            """)
            # Initialize counter for this prefix
            cursor.execute("""
                INSERT OR IGNORE INTO id_sequence (prefix, counter) VALUES (?, 0)
            """, (key_prefix,))
        else:
            # Use INTEGER AUTOINCREMENT (default)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_uuid TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            # Create indexes for faster sorting and queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_records_created_at ON records(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_records_updated_at ON records(updated_at)
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
        
        # Get the next order value (highest order + 1)
        cursor.execute("SELECT MAX(field_order) FROM fields")
        max_order = cursor.fetchone()[0]
        next_order = (max_order or 0) + 1
        
        # Check if field_order column exists
        cursor.execute("PRAGMA table_info(fields)")
        columns = [col[1] for col in cursor.fetchall()]
        has_order = 'field_order' in columns
        
        if has_order:
            cursor.execute("""
                INSERT INTO fields (field_key, field_type, label, required, default_value,
                                   validation_rules, options, indexed, field_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                field_key, field_type, label, 1 if required else 0,
                default_value,
                json.dumps(validation_rules) if validation_rules else None,
                json.dumps(options) if options else None,
                1 if indexed else 0, next_order,
                now, now
            ))
        else:
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
    
    def set_field_order(self, field_key: str, new_order: int):
        """Update the display order of a field"""
        self._ensure_schema()
        self.connect()
        cursor = self.conn.cursor()
        
        # Check if field_order column exists
        cursor.execute("PRAGMA table_info(fields)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'field_order' not in columns:
            # Add the column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE fields ADD COLUMN field_order INTEGER DEFAULT 0")
                self.conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        cursor.execute("""
            UPDATE fields SET field_order = ?, updated_at = ?
            WHERE field_key = ?
        """, (new_order, datetime.now().isoformat(), field_key))
        self.conn.commit()
    
    def reorder_fields(self, field_keys: List[str]):
        """Reorder fields by providing a list of field keys in the desired order"""
        self._ensure_schema()
        self.connect()
        cursor = self.conn.cursor()
        
        # Check if field_order column exists
        cursor.execute("PRAGMA table_info(fields)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'field_order' not in columns:
            # Add the column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE fields ADD COLUMN field_order INTEGER DEFAULT 0")
                self.conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        now = datetime.now().isoformat()
        for order, field_key in enumerate(field_keys, start=1):
            cursor.execute("""
                UPDATE fields SET field_order = ?, updated_at = ?
                WHERE field_key = ?
            """, (order, now, field_key))
        self.conn.commit()
    
    def remove_field(self, field_key: str):
        """Remove a field from the collection schema
        
        Note: SQLite doesn't support DROP COLUMN directly, so the column
        will remain in the records table but will be ignored by the UI.
        To fully remove the column, the table would need to be recreated.
        """
        self.connect()
        cursor = self.conn.cursor()
        
        # Check if this field was indexed (before deleting)
        cursor.execute("SELECT indexed FROM fields WHERE field_key = ?", (field_key,))
        field_row = cursor.fetchone()
        was_indexed = field_row and field_row[0] == 1
        
        # Remove from fields table
        cursor.execute("DELETE FROM fields WHERE field_key = ?", (field_key,))
        
        # Remove any layout nodes referencing this field
        cursor.execute("DELETE FROM layout_nodes WHERE field_key = ?", (field_key,))
        
        # Remove any dependencies referencing this field
        cursor.execute("DELETE FROM deps WHERE source_id = ? OR target_id = ?", (field_key, field_key))
        
        # Update FTS index if needed (will rebuild without this field)
        if was_indexed:
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
    
    def _ensure_schema(self):
        """Ensure database schema is initialized"""
        self.connect()
        cursor = self.conn.cursor()
        # Check if fields table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='fields'
        """)
        if not cursor.fetchone():
            # Schema not initialized, initialize it now
            self.initialize_schema(self.key_prefix)
    
    def list_fields(self) -> List[Dict]:
        """List all fields"""
        self._ensure_schema()
        self.connect()
        cursor = self.conn.cursor()
        # Check if field_order column exists
        cursor.execute("PRAGMA table_info(fields)")
        columns = [col[1] for col in cursor.fetchall()]
        has_order = 'field_order' in columns
        
        if has_order:
            cursor.execute("""
                SELECT field_key, field_type, label, required, default_value,
                       validation_rules, options, indexed, field_order
                FROM fields
                ORDER BY field_order, created_at
            """)
        else:
            cursor.execute("""
                SELECT field_key, field_type, label, required, default_value,
                       validation_rules, options, indexed
                FROM fields
                ORDER BY created_at
            """)
        
        fields = []
        for row in cursor.fetchall():
            if has_order:
                field = {
                    "key": row[0],
                    "type": row[1],
                    "label": row[2],
                    "required": bool(row[3]),
                    "default_value": row[4],
                    "validation_rules": json.loads(row[5]) if row[5] else None,
                    "options": json.loads(row[6]) if row[6] else None,
                    "indexed": bool(row[7]),
                    "order": row[8] if row[8] is not None else 0
                }
            else:
                field = {
                    "key": row[0],
                    "type": row[1],
                    "label": row[2],
                    "required": bool(row[3]),
                    "default_value": row[4],
                    "validation_rules": json.loads(row[5]) if row[5] else None,
                    "options": json.loads(row[6]) if row[6] else None,
                    "indexed": bool(row[7]),
                    "order": 0
                }
            fields.append(field)
        
        return fields
    
    def get_field(self, field_key: str) -> Optional[Dict]:
        """Get a single field definition"""
        fields = self.list_fields()
        return next((f for f in fields if f["key"] == field_key), None)
    
    def add_record(self, data: Dict[str, Any]) -> Union[int, str]:
        """Add a new record - returns ID (int or str depending on prefix)"""
        self._ensure_schema()
        self.connect()
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        import uuid
        record_uuid = str(uuid.uuid4())
        
        # Generate record ID based on prefix
        if self.key_prefix:
            # Use prefix-based ID: "PREFIX_1", "PREFIX_2", etc.
            # Get and increment counter
            cursor.execute("""
                UPDATE id_sequence SET counter = counter + 1 WHERE prefix = ?
            """, (self.key_prefix,))
            cursor.execute("""
                SELECT counter FROM id_sequence WHERE prefix = ?
            """, (self.key_prefix,))
            result = cursor.fetchone()
            counter = result[0] if result else 1
            record_id = f"{self.key_prefix}_{counter}"
            
            # Build column list and values (include id)
            columns = ["id", "record_uuid", "created_at", "updated_at"]
            placeholders = ["?", "?", "?", "?"]
            values = [record_id, record_uuid, now, now]
        else:
            # Use auto-increment INTEGER ID
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
        
        # Get the ID (for INTEGER, use lastrowid; for TEXT, we already have it)
        if not self.key_prefix:
            record_id = cursor.lastrowid
        
        # Update FTS index if needed
        self.update_fts_index()
        
        self.conn.commit()
        return record_id
    
    def update_record(self, record_id: int, data: Dict[str, Any]):
        """Update an existing record"""
        self._ensure_schema()
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
    
    def delete_record(self, record_id: Union[int, str]):
        """Delete a record"""
        self._ensure_schema()
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
        
        # Update FTS index
        self.update_fts_index()
        
        self.conn.commit()
    
    def get_record(self, record_id: Union[int, str]) -> Optional[Dict]:
        """Get a single record"""
        self._ensure_schema()
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def list_records(self, limit: Optional[int] = None, offset: int = 0, order_by: Optional[str] = None) -> List[Dict]:
        """List records with optional ordering"""
        self._ensure_schema()
        self.connect()
        cursor = self.conn.cursor()
        
        # Use provided order_by or default to id
        order_clause = f"ORDER BY {order_by}" if order_by else "ORDER BY id"
        
        sql = f"SELECT * FROM records {order_clause}"
        if limit:
            sql += f" LIMIT {limit} OFFSET {offset}"
        
        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
    
    def count_records(self) -> int:
        """Count total records"""
        self._ensure_schema()
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
