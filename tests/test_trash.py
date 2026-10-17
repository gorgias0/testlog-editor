import json
import os

import pytest

import trash
from trash import (
    TRASH_RECORD_NAME,
    available_path,
    empty_trash,
    is_in_trash,
    move_to_trash,
    purge_trash,
    restore_from_trash,
    skip_trash_dirs,
)

DAY = 86400
NOW = 1_800_000_000.0


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    (root / "tdialog").mkdir(parents=True)
    (root / "tdialog" / "login.testlog").write_text("login", encoding="utf-8")
    (root / "tdialog" / "checkout.testlog").write_text("checkout", encoding="utf-8")
    (root / "top.testlog").write_text("top", encoding="utf-8")
    return root


def _records(workspace):
    path = workspace / "Trash" / TRASH_RECORD_NAME
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _age(path, days_ago):
    timestamp = NOW - days_ago * DAY
    os.utime(path, (timestamp, timestamp))


def test_move_to_trash_keeps_relative_path_and_records_it(workspace):
    destination = move_to_trash(workspace, workspace / "tdialog" / "login.testlog", now=NOW)

    assert destination == str(workspace / "Trash" / "tdialog" / "login.testlog")
    assert not (workspace / "tdialog" / "login.testlog").exists()
    assert (workspace / "Trash" / "tdialog" / "login.testlog").read_text(encoding="utf-8") == "login"
    assert _records(workspace) == {"tdialog/login.testlog": {"original": "tdialog/login.testlog", "trashed_at": NOW}}


def test_move_to_trash_numbers_a_taken_name(workspace):
    move_to_trash(workspace, workspace / "top.testlog", now=NOW)
    (workspace / "top.testlog").write_text("second", encoding="utf-8")

    destination = move_to_trash(workspace, workspace / "top.testlog", now=NOW)

    assert destination == str(workspace / "Trash" / "top 2.testlog")
    assert _records(workspace)["top 2.testlog"]["original"] == "top.testlog"


def test_move_folder_to_trash(workspace):
    destination = move_to_trash(workspace, workspace / "tdialog", now=NOW)

    assert destination == str(workspace / "Trash" / "tdialog")
    assert sorted(os.listdir(destination)) == ["checkout.testlog", "login.testlog"]
    assert list(_records(workspace)) == ["tdialog"]


@pytest.mark.parametrize("target", ["workspace", "trash", "in_trash", "outside", "missing"])
def test_move_to_trash_refuses_invalid_targets(workspace, tmp_path, target):
    move_to_trash(workspace, workspace / "top.testlog", now=NOW)
    (tmp_path / "outside.testlog").write_text("x", encoding="utf-8")
    paths = {
        "workspace": workspace,
        "trash": workspace / "Trash",
        "in_trash": workspace / "Trash" / "top.testlog",
        "outside": tmp_path / "outside.testlog",
        "missing": workspace / "nope.testlog",
    }

    with pytest.raises(trash.TrashError):
        move_to_trash(workspace, paths[target], now=NOW)


def test_restore_puts_note_back_and_drops_record(workspace):
    trashed = move_to_trash(workspace, workspace / "tdialog" / "login.testlog", now=NOW)

    restored = restore_from_trash(workspace, trashed)

    assert restored == str(workspace / "tdialog" / "login.testlog")
    assert (workspace / "tdialog" / "login.testlog").read_text(encoding="utf-8") == "login"
    assert _records(workspace) == {}
    # The emptied mirror folder inside Trash is cleaned up.
    assert not (workspace / "Trash" / "tdialog").exists()


def test_restore_recreates_missing_folder_and_numbers_taken_name(workspace):
    trashed = move_to_trash(workspace, workspace / "tdialog" / "login.testlog", now=NOW)
    move_to_trash(workspace, workspace / "tdialog", now=NOW)
    assert not (workspace / "tdialog").exists()

    restored = restore_from_trash(workspace, trashed)
    assert restored == str(workspace / "tdialog" / "login.testlog")

    (workspace / "top.testlog").rename(workspace / "tdialog" / "x.testlog")
    other = move_to_trash(workspace, workspace / "tdialog" / "x.testlog", now=NOW)
    (workspace / "tdialog" / "x.testlog").write_text("new", encoding="utf-8")
    assert restore_from_trash(workspace, other) == str(workspace / "tdialog" / "x 2.testlog")


def test_restore_file_from_inside_trashed_folder(workspace):
    folder = move_to_trash(workspace, workspace / "tdialog", now=NOW)

    restored = restore_from_trash(workspace, os.path.join(folder, "login.testlog"))

    assert restored == str(workspace / "tdialog" / "login.testlog")
    assert list(_records(workspace)) == ["tdialog"]


def test_restore_without_record_mirrors_trash_path(workspace):
    trashed = move_to_trash(workspace, workspace / "tdialog" / "login.testlog", now=NOW)
    (workspace / "Trash" / TRASH_RECORD_NAME).unlink()

    assert restore_from_trash(workspace, trashed) == str(workspace / "tdialog" / "login.testlog")


def test_restore_ignores_record_pointing_outside_workspace(workspace):
    trashed = move_to_trash(workspace, workspace / "top.testlog", now=NOW)
    record_path = workspace / "Trash" / TRASH_RECORD_NAME
    record_path.write_text(json.dumps({"top.testlog": {"original": "../escape.testlog", "trashed_at": NOW}}), encoding="utf-8")

    assert restore_from_trash(workspace, trashed) == str(workspace / "top.testlog")


def test_restore_refuses_items_outside_trash(workspace):
    with pytest.raises(trash.TrashError):
        restore_from_trash(workspace, workspace / "top.testlog")
    move_to_trash(workspace, workspace / "top.testlog", now=NOW)
    with pytest.raises(trash.TrashError):
        restore_from_trash(workspace, workspace / "Trash")


def test_purge_removes_items_older_than_30_days_only(workspace):
    old = move_to_trash(workspace, workspace / "tdialog" / "login.testlog", now=NOW - 31 * DAY)
    recent = move_to_trash(workspace, workspace / "tdialog" / "checkout.testlog", now=NOW - 29 * DAY)
    _age(old, 40)
    _age(recent, 40)

    purged = purge_trash(workspace, now=NOW)

    assert purged == [old]
    assert not os.path.exists(old)
    assert os.path.exists(recent)
    assert list(_records(workspace)) == ["tdialog/checkout.testlog"]


def test_purge_keeps_item_edited_recently(workspace):
    item = move_to_trash(workspace, workspace / "top.testlog", now=NOW - 40 * DAY)
    _age(item, 5)

    assert purge_trash(workspace, now=NOW) == []
    assert os.path.exists(item)


def test_purge_gives_unrecorded_file_a_fresh_start(workspace):
    (workspace / "Trash" / "moved").mkdir(parents=True)
    stray = workspace / "Trash" / "moved" / "stray.testlog"
    stray.write_text("x", encoding="utf-8")
    _age(stray, 100)

    assert purge_trash(workspace, now=NOW) == []
    assert _records(workspace) == {"moved/stray.testlog": {"original": "moved/stray.testlog", "trashed_at": NOW}}
    assert purge_trash(workspace, now=NOW + 31 * DAY) == [str(stray)]


def test_purge_with_damaged_record_file_keeps_everything(workspace):
    item = move_to_trash(workspace, workspace / "top.testlog", now=NOW - 100 * DAY)
    _age(item, 100)
    (workspace / "Trash" / TRASH_RECORD_NAME).write_text("{not json", encoding="utf-8")

    assert purge_trash(workspace, now=NOW) == []
    assert _records(workspace) == {"top.testlog": {"original": "top.testlog", "trashed_at": NOW}}


def test_purge_cleans_empty_mirror_folders_but_keeps_trashed_folder_contents(workspace):
    old = move_to_trash(workspace, workspace / "tdialog" / "login.testlog", now=NOW - 31 * DAY)
    _age(old, 40)
    (workspace / "keep" / "empty-sub").mkdir(parents=True)
    kept_folder = move_to_trash(workspace, workspace / "keep", now=NOW)

    purge_trash(workspace, now=NOW)

    assert not (workspace / "Trash" / "tdialog").exists()
    assert os.path.isdir(os.path.join(kept_folder, "empty-sub"))


def test_purge_continues_when_one_item_cannot_be_removed(workspace, monkeypatch):
    first = move_to_trash(workspace, workspace / "tdialog" / "login.testlog", now=NOW - 31 * DAY)
    second = move_to_trash(workspace, workspace / "top.testlog", now=NOW - 31 * DAY)
    _age(first, 40)
    _age(second, 40)
    real_remove = os.remove

    def flaky_remove(path):
        if os.path.abspath(path) == os.path.abspath(first):
            raise PermissionError("in use")
        real_remove(path)

    monkeypatch.setattr(os, "remove", flaky_remove)
    purged = purge_trash(workspace, now=NOW)

    assert purged == [second]
    assert os.path.exists(first)
    assert "tdialog/login.testlog" in _records(workspace)


def test_purge_without_trash_folder_does_nothing(workspace):
    assert purge_trash(workspace, now=NOW) == []
    assert not (workspace / "Trash").exists()


def test_empty_trash_leaves_empty_folder(workspace):
    move_to_trash(workspace, workspace / "tdialog", now=NOW)
    move_to_trash(workspace, workspace / "top.testlog", now=NOW)

    empty_trash(workspace)

    assert os.listdir(workspace / "Trash") == []


def test_records_use_forward_slashes(workspace):
    move_to_trash(workspace, workspace / "tdialog" / "login.testlog", now=NOW)

    text = (workspace / "Trash" / TRASH_RECORD_NAME).read_text(encoding="utf-8")
    assert '"tdialog/login.testlog"' in text
    assert "\\\\" not in text


def test_is_in_trash(workspace):
    assert is_in_trash(workspace, workspace / "Trash")
    assert is_in_trash(workspace, workspace / "Trash" / "a" / "b.testlog")
    assert not is_in_trash(workspace, workspace / "Trashcan" / "b.testlog")
    assert not is_in_trash(workspace, workspace / "top.testlog")
    assert not is_in_trash(None, workspace / "Trash")


def test_skip_trash_dirs_only_at_workspace_root(workspace):
    dirs = ["tdialog", "Trash", "meetings"]
    skip_trash_dirs(workspace, str(workspace), dirs)
    assert dirs == ["tdialog", "meetings"]

    nested = ["Trash"]
    skip_trash_dirs(workspace, str(workspace / "tdialog"), nested)
    assert nested == ["Trash"]


def test_available_path(tmp_path):
    (tmp_path / "a.testlog").write_text("x", encoding="utf-8")
    (tmp_path / "a 2.testlog").write_text("x", encoding="utf-8")

    assert available_path(str(tmp_path / "b.testlog")) == str(tmp_path / "b.testlog")
    assert available_path(str(tmp_path / "a.testlog")) == str(tmp_path / "a 3.testlog")
