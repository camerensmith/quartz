"""Tests for CollectionStore schema changes and the FTS search index"""

import sqlite3

import pytest

from src.core.collection_store import FTS_TRIGGERS, CollectionStore


@pytest.fixture(params=[None, "REST"], ids=["integer-ids", "prefixed-ids"])
def store(request, tmp_path):
    s = CollectionStore(tmp_path / "test.sqlite")
    s.initialize_schema(request.param)
    s.add_field("name", "text", "Name", indexed=True)
    s.add_field("notes", "text", "Notes")
    yield s
    s.close()


def search_names(store, query):
    return sorted(r["name"] for r in store.search_records(query))


def fts_triggers(store):
    cursor = store.conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")
    return {row[0] for row in cursor.fetchall()} & set(FTS_TRIGGERS)


def test_search_tracks_inserts_updates_and_deletes(store):
    alpha = store.add_record({"name": "alpha"})
    store.add_record({"name": "beta"})
    assert search_names(store, "alp") == ["alpha"]

    store.update_record(alpha, {"name": "gamma"})
    assert search_names(store, "alp") == []
    assert search_names(store, "gam") == ["gamma"]

    store.delete_record(alpha)
    assert search_names(store, "gam") == []
    assert search_names(store, "bet") == ["beta"]


def test_record_writes_do_not_rebuild_index(store, monkeypatch):
    def fail():
        raise AssertionError("update_fts_index called on a record write")

    monkeypatch.setattr(store, "update_fts_index", fail)
    record_id = store.add_record({"name": "alpha"})
    store.update_record(record_id, {"name": "beta"})
    assert search_names(store, "bet") == ["beta"]
    store.delete_record(record_id)
    assert search_names(store, "bet") == []


def test_prefixed_ids_keep_prefix(tmp_path):
    s = CollectionStore(tmp_path / "prefixed.sqlite")
    s.initialize_schema("REST")
    s.add_field("name", "text", "Name", indexed=True)
    assert s.add_record({"name": "alpha"}) == "REST_1"
    assert [r["id"] for r in s.search_records("alpha")] == ["REST_1"]
    s.close()


def test_add_field_rejects_invalid_key_without_side_effects(store):
    for bad in ("order", "my key", "id"):
        with pytest.raises(ValueError):
            store.add_field(bad, "text", "Bad")
    store.add_record({"name": "alpha"})  # commits anything left pending
    assert [f["key"] for f in store.list_fields()] == ["name", "notes"]


def test_add_field_rejects_case_insensitive_duplicate(store):
    with pytest.raises(ValueError, match="already exists"):
        store.add_field("Name", "text", "Name again")


def test_add_field_failure_rolls_back_fields_row(store, monkeypatch):
    # Bypass validation to simulate the ALTER TABLE itself failing
    monkeypatch.setattr("src.core.collection_store.field_key_error", lambda key: None)
    with pytest.raises(sqlite3.Error):
        store.add_field("order", "text", "Order")
    store.add_record({"name": "alpha"})
    assert [f["key"] for f in store.list_fields()] == ["name", "notes"]


def test_index_new_field_and_remove_indexed_field(store):
    store.add_record({"name": "alpha", "notes": "ignored"})
    store.add_field("city", "text", "City", indexed=True)
    record_id = store.add_record({"name": "beta", "city": "paris"})
    assert search_names(store, "paris") == ["beta"]

    store.remove_field("city")
    assert search_names(store, "alp") == ["alpha"]
    store.update_record(record_id, {"name": "delta"})
    assert search_names(store, "del") == ["delta"]


def test_remove_unindexed_field_keeps_index(store):
    store.add_record({"name": "alpha", "notes": "hello"})
    store.remove_field("notes")
    assert fts_triggers(store) == set(FTS_TRIGGERS)
    store.add_record({"name": "beta"})
    assert search_names(store, "bet") == ["beta"]


def test_removing_last_indexed_field_drops_index(store):
    store.add_record({"name": "alpha", "notes": "hello"})
    store.remove_field("name")
    assert fts_triggers(store) == set()
    # Writes still work and search falls back to a LIKE scan
    store.add_record({"notes": "world"})
    assert [r["notes"] for r in store.search_records("wor")] == ["world"]


def test_toggling_indexed_flag_then_rebuilding(store):
    store.add_record({"name": "alpha", "notes": "hello"})
    store.conn.execute("UPDATE fields SET indexed = 1 WHERE field_key = 'notes'")
    store.conn.commit()
    store.update_fts_index()
    assert [r["name"] for r in store.search_records("hel")] == ["alpha"]


def test_legacy_index_without_triggers_is_migrated(store):
    store.add_record({"name": "alpha"})
    # Older versions kept the FTS table but rebuilt it on every write instead of using triggers
    for trigger in FTS_TRIGGERS:
        store.conn.execute(f"DROP TRIGGER {trigger}")
    store.conn.commit()
    store.close()

    reopened = CollectionStore(store.db_path)
    reopened.key_prefix = store.key_prefix
    reopened.add_record({"name": "beta"})
    assert fts_triggers(reopened) == set(FTS_TRIGGERS)
    assert search_names(reopened, "bet") == ["beta"]
    assert search_names(reopened, "alp") == ["alpha"]
    reopened.close()
