"""Field key sanitization and validation

Field keys become column names in each collection's ``records`` table and in
its FTS5 index, and are interpolated into SQL unquoted. A key is only safe if
SQLite accepts it as a bare identifier in every statement we build.
"""

import re
import sqlite3
from functools import lru_cache

# Columns every records table already has (SQLite compares names case-insensitively)
BUILTIN_COLUMNS = {"id", "record_uuid", "created_at", "updated_at"}

# Names that would shadow SQLite's implicit rowid or the row-tag keys attached to records
RESERVED_KEYS = {"rowid", "oid", "_rowid_", "__row_tag_name", "__row_tag_color"}

_IDENTIFIER_RE = re.compile(r"[^\W\d]\w*")


@lru_cache(maxsize=1024)
def _sqlite_accepts(key: str) -> bool:
    """Return True if *key* works as a bare column name in the SQL Quartz generates."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(f"CREATE TABLE t (id INTEGER PRIMARY KEY, {key} TEXT)")
        conn.execute(f"INSERT INTO t ({key}) VALUES ('a')")
        conn.execute(f"UPDATE t SET {key} = 'b' WHERE t.{key} = 'a'")
        conn.execute(f"SELECT {key} FROM t ORDER BY {key}").fetchall()
        try:
            conn.execute(f"CREATE VIRTUAL TABLE f USING fts5({key}, content='t', content_rowid='id')")
        except sqlite3.OperationalError as e:
            # SQLite built without FTS5: search falls back to LIKE, so don't reject the key
            if "no such module" not in str(e):
                raise
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def field_key_error(key: str) -> str | None:
    """Return a user-facing reason *key* can't be used as a field key, or None if it can."""
    if not key:
        return "Field key cannot be empty"
    if not _IDENTIFIER_RE.fullmatch(key):
        return "Field key must start with a letter or underscore and contain only letters, digits and underscores"
    lowered = key.lower()
    if lowered in BUILTIN_COLUMNS or lowered in RESERVED_KEYS:
        return f"'{key}' is reserved by Quartz"
    if not _sqlite_accepts(key):
        return f"'{key}' is a reserved SQL word"
    return None


def sanitize_field_key(text: str) -> str:
    """Derive a valid field key from a label or CSV header (e.g. "Order Date" -> "order_date")."""
    key = text.strip().lower().replace(" ", "_").replace("-", "_")
    key = "".join(c for c in key if c.isalnum() or c == "_")
    if not key:
        return "field"
    if key[0].isdigit():
        key = f"field_{key}"
    if field_key_error(key):
        # Keywords ("order") and built-in names ("id") become "order_field", "id_field"
        key = f"{key}_field"
    return key
