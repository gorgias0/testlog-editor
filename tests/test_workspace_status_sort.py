import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QDir, Qt
from PySide6.QtWidgets import QApplication

from testlog_archive import write_testlog_archive
from workspace_models import WorkspaceFileSystemModel, WorkspaceSortProxyModel


def _write_note(path, status, modified, images_dir):
    write_testlog_archive(str(path), f"---\nstatus: {status}\n---\n# {path.stem}\n", str(images_dir))
    os.utime(path, (modified, modified))


def _sorted_names(workspace, pinned_paths=frozenset()):
    app = QApplication.instance() or QApplication([])
    model = WorkspaceFileSystemModel(set(pinned_paths))
    model.setNameFilters(["*.testlog"])
    model.setNameFilterDisables(True)
    model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
    proxy = WorkspaceSortProxyModel(model, set(pinned_paths))
    proxy.set_sort_mode("status")
    model.setRootPath(str(workspace))
    expected_rows = len(os.listdir(workspace))
    deadline = time.monotonic() + 5
    while model.rowCount(model.index(str(workspace))) < expected_rows and time.monotonic() < deadline:
        app.processEvents()
        QCoreApplication.sendPostedEvents()
    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    root = proxy.mapFromSource(model.index(str(workspace)))
    return [proxy.index(row, 0, root).data() for row in range(proxy.rowCount(root))]


def test_status_sort_puts_doing_then_todo_then_done_newest_first(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    (workspace / "folder").mkdir()
    (workspace / "readme.txt").write_text("not a note")
    now = time.time()
    _write_note(workspace / "old doing.testlog", "doing", now - 300, images)
    _write_note(workspace / "new doing.testlog", "doing", now - 100, images)
    _write_note(workspace / "todo.testlog", "todo", now - 50, images)
    _write_note(workspace / "fresh done.testlog", "done", now, images)

    assert _sorted_names(workspace) == [
        "folder",
        "new doing",
        "old doing",
        "todo",
        "fresh done",
        "readme.txt",
    ]


def test_status_sort_keeps_pinned_notes_above_other_notes(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    images = tmp_path / "images"
    images.mkdir()
    now = time.time()
    _write_note(workspace / "active.testlog", "doing", now, images)
    _write_note(workspace / "pinned done.testlog", "done", now - 100, images)

    pinned = {QDir.fromNativeSeparators(str(workspace / "pinned done.testlog"))}
    assert _sorted_names(workspace, pinned) == ["pinned done", "active"]
