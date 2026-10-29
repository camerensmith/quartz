"""Copies of collection databases must include changes still in the WAL file"""

import sqlite3
import zipfile

import pytest

from src.core.collection_store import CollectionStore, copy_database
from src.core.export_service import ExportService
from src.core.qz_packager import QzPackager
from src.core.workspace import Workspace
from src.core.workspace_sync import sync_collection


def record_names(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        return sorted(row[0] for row in conn.execute("SELECT name FROM records"))
    finally:
        conn.close()


@pytest.fixture
def open_collection(tmp_path):
    """A workspace whose 'Books' collection is open, with its changes still in the WAL file"""
    ws = Workspace(tmp_path / "ws")
    db_path = ws.create_collection("Books")
    store = CollectionStore(db_path)
    store.add_field("name", "text", "Name")
    store.add_record({"name": "Dune"})
    store.add_record({"name": "Emma"})
    wal = db_path.with_name(db_path.name + "-wal")
    assert wal.exists() and wal.stat().st_size > 0
    yield ws, store
    store.close()


def test_copy_database_includes_wal_changes(open_collection, tmp_path):
    _, store = open_collection
    copy_database(store.db_path, tmp_path / "copy.sqlite")
    assert record_names(tmp_path / "copy.sqlite") == ["Dune", "Emma"]


def test_copy_database_replaces_existing_target(open_collection, tmp_path):
    _, store = open_collection
    target = tmp_path / "target.sqlite"
    conn = sqlite3.connect(str(target))
    conn.execute("CREATE TABLE records (name TEXT)")
    conn.execute("INSERT INTO records VALUES ('stale')")
    conn.commit()
    conn.close()
    copy_database(store.db_path, target)
    assert record_names(target) == ["Dune", "Emma"]


def test_copy_database_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        copy_database(tmp_path / "missing.sqlite", tmp_path / "copy.sqlite")
    assert not (tmp_path / "copy.sqlite").exists()


def test_export_db_and_pack(open_collection, tmp_path):
    _, store = open_collection
    service = ExportService(store)
    assert service.export_db(tmp_path / "export.sqlite")
    assert record_names(tmp_path / "export.sqlite") == ["Dune", "Emma"]

    assert service.export_pack(tmp_path / "pack.zip")
    with zipfile.ZipFile(tmp_path / "pack.zip") as zf:
        zf.extract("Books.sqlite", tmp_path / "unpacked")
    assert record_names(tmp_path / "unpacked" / "Books.sqlite") == ["Dune", "Emma"]


def test_export_errors_propagate(open_collection, tmp_path):
    _, store = open_collection
    with pytest.raises(OSError):
        ExportService(store).export_csv(tmp_path / "no-such-dir" / "out.csv")


def test_duplicate_and_delete_backup(open_collection):
    ws, store = open_collection
    new_db = ws.duplicate_collection("Books", "Books copy")
    assert record_names(new_db) == ["Dune", "Emma"]

    store.close()
    store.connect()  # still open when deleted, like the current collection in the app
    ws.delete_collection("Books copy", backup=True)
    backups = list((ws.workspace_path / "backups").glob("Books copy*/Books copy.sqlite"))
    assert len(backups) == 1
    assert record_names(backups[0]) == ["Dune", "Emma"]


def test_sync_collection(open_collection, tmp_path):
    ws, _ = open_collection
    cloud = Workspace(tmp_path / "cloud")
    sync_collection("Books", ws, cloud)
    assert record_names(cloud.workspace_path / "db" / "Books.sqlite") == ["Dune", "Emma"]


def test_qz_bundle(open_collection, tmp_path):
    ws, _ = open_collection
    QzPackager(ws).pack(tmp_path / "bundle.qz")
    with zipfile.ZipFile(tmp_path / "bundle.qz") as zf:
        names = zf.namelist()
        zf.extract("db/Books.sqlite", tmp_path / "unpacked")
    assert not [n for n in names if n.endswith(("-wal", "-shm"))]
    assert record_names(tmp_path / "unpacked" / "db" / "Books.sqlite") == ["Dune", "Emma"]
