"""Tests for safe JSON persistence of the workspace registry, settings and subcollections"""

import json
import shutil

import pytest

from src.core.collection_store import CollectionStore
from src.core.config import Config
from src.core.json_store import read_json, write_json_atomic
from src.core.subcollection_store import SubcollectionStore
from src.core.workspace import Workspace


def corrupt_backups(path):
    return sorted(path.parent.glob(f"{path.name}.corrupt-*"))


def test_write_json_atomic_leaves_no_temp_file(tmp_path):
    path = tmp_path / "data.json"
    write_json_atomic(path, {"a": 1})
    write_json_atomic(path, {"a": 2})
    assert json.loads(path.read_text()) == {"a": 2}
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


@pytest.mark.parametrize("contents", ['{"collections": {"Bo', "[1, 2, 3]", "\xff\xfe"])
def test_read_json_moves_unreadable_file_aside(tmp_path, contents):
    path = tmp_path / "data.json"
    path.write_text(contents, encoding="latin-1")
    data, backup = read_json(path)
    assert data is None
    assert backup == corrupt_backups(path)[0]
    assert backup.read_text(encoding="latin-1") == contents
    assert not path.exists()


def test_read_json_missing_file(tmp_path):
    assert read_json(tmp_path / "missing.json") == (None, None)


def test_corrupt_registry_is_kept_and_collections_recovered(tmp_path):
    ws = Workspace(tmp_path)
    ws.create_collection("Books")
    ws.create_collection("Restaurants", key_prefix="REST")
    ws.registry_path.write_text('{"collections": {"Books": {"na')  # truncated mid-write

    reopened = Workspace(tmp_path)
    assert reopened.registry_backup is not None
    assert reopened.registry_backup.read_text() == '{"collections": {"Books": {"na'
    assert sorted(reopened.recovered_collections) == ["Books", "Restaurants"]
    assert reopened.get_collection_info("Restaurants").key_prefix == "REST"
    assert reopened.get_collection_info("Books").key_prefix is None

    # The rebuilt list was saved, and the next open is clean
    again = Workspace(tmp_path)
    assert again.registry_backup is None
    assert sorted(again.list_collections()) == ["Books", "Restaurants"]


def test_recovered_prefixed_collection_keeps_numbering(tmp_path):
    ws = Workspace(tmp_path)
    db = ws.create_collection("Restaurants", key_prefix="REST")
    store = CollectionStore(db)
    store.key_prefix = "REST"
    store.add_field("name", "text", "Name")
    assert store.add_record({"name": "a"}) == "REST_1"
    store.close()
    ws.registry_path.write_text("not json")

    info = Workspace(tmp_path).get_collection_info("Restaurants")
    store = CollectionStore(tmp_path / info.db_path)
    store.key_prefix = info.key_prefix
    assert store.add_record({"name": "b"}) == "REST_2"
    store.close()


def test_registry_keeps_unknown_keys_and_unreadable_entries(tmp_path):
    ws = Workspace(tmp_path)
    ws.create_collection("Books")
    data = json.loads(ws.registry_path.read_text())
    data["collections"]["Books"]["colour"] = "#ff0000"  # written by a newer version
    data["collections"]["Broken"] = {"name": "Broken"}  # missing required keys
    data["view"] = {"sort": "name"}
    ws.registry_path.write_text(json.dumps(data))

    reopened = Workspace(tmp_path)
    assert reopened.list_collections() == ["Books"]
    reopened.create_collection("Films")
    reopened.rename_collection("Books", "Novels")

    saved = json.loads(reopened.registry_path.read_text())
    assert saved["collections"]["Novels"]["colour"] == "#ff0000"
    assert saved["collections"]["Broken"] == {"name": "Broken"}
    assert saved["view"] == {"sort": "name"}
    assert "Books" not in saved["collections"]


def test_failed_migration_keeps_registry(tmp_path, monkeypatch):
    ws = Workspace(tmp_path)
    for name in ("Alpha", "Beta"):
        ws.create_collection(name)
        # Move each database back to the pre-db/ layout
        legacy = tmp_path / name / "collection.sqlite"
        shutil.move(tmp_path / "db" / f"{name}.sqlite", legacy)
        ws.collections[name].db_path = f"{name}/collection.sqlite"
    ws.save_registry()

    real_move = shutil.move

    def move_alpha_only(src, dst):
        if "Beta" in str(src):
            raise PermissionError("in use")
        return real_move(src, dst)

    monkeypatch.setattr(shutil, "move", move_alpha_only)
    reopened = Workspace(tmp_path)
    assert reopened.registry_backup is None
    assert reopened.get_collection_info("Alpha").db_path == "db/Alpha.sqlite"
    assert reopened.get_collection_info("Beta").db_path == "Beta/collection.sqlite"
    # Alpha's move was recorded even though Beta's failed
    saved = json.loads(reopened.registry_path.read_text())
    assert saved["collections"]["Alpha"]["db_path"] == "db/Alpha.sqlite"


def test_corrupt_config_falls_back_to_defaults(tmp_path):
    path = tmp_path / "quartz_config.json"
    path.write_text("{oops")
    config = Config(config_path=path)
    assert config.load_backup.read_text() == "{oops"
    assert config.get("date_format") == "yyyy-MM-dd"
    config.set("date_format", "dd/MM/yyyy")
    assert json.loads(path.read_text())["date_format"] == "dd/MM/yyyy"
    assert config.load_backup.read_text() == "{oops"


def test_corrupt_subcollections_are_kept(tmp_path):
    (tmp_path / "subcollections.json").write_text('{"Books": [')
    store = SubcollectionStore(tmp_path)
    assert store.load_backup.read_text() == '{"Books": ['
    store.create("Books", "Favourites")
    assert [s.name for s in SubcollectionStore(tmp_path).list_for_collection("Books")] == ["Favourites"]
