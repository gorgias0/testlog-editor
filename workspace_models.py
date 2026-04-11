import os
from pathlib import Path

from PySide6.QtCore import Qt, QFileInfo, QSortFilterProxyModel
from PySide6.QtWidgets import QFileSystemModel

from testlog_utils import TESTLOG_STATUS_LABELS, read_testlog_status_from_archive

TESTLOG_STATUS_ROLE = Qt.ItemDataRole.UserRole + 20


class WorkspaceFileSystemModel(QFileSystemModel):
    def __init__(
        self,
        pinned_paths=None,
        folder_icon=None,
        folder_pinned_icon=None,
        testlog_icon=None,
        testlog_pinned_icon=None,
        file_icon=None,
        parent=None,
    ):
        super().__init__(parent)
        self.pinned_paths = pinned_paths if pinned_paths is not None else set()
        self.folder_icon = folder_icon
        self.folder_pinned_icon = folder_pinned_icon
        self.testlog_icon = testlog_icon
        self.testlog_pinned_icon = testlog_pinned_icon
        self.file_icon = file_icon
        self._status_cache = {}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.ToolTipRole:
            path = self.filePath(index)
            if path.endswith(".testlog") and not self.isDir(index):
                return self._build_tooltip(path)

        if role == Qt.ItemDataRole.DecorationRole and index.column() == 0:
            path = self.filePath(index)
            is_pinned = path in self.pinned_paths
            if self.isDir(index):
                return self.folder_pinned_icon if is_pinned else self.folder_icon
            if path.endswith(".testlog"):
                return self.testlog_pinned_icon if is_pinned else self.testlog_icon
            return self.file_icon

        if role == Qt.ItemDataRole.DisplayRole and index.column() == 0:
            path = self.filePath(index)
            if path.endswith(".testlog"):
                return Path(path).stem

        if role == TESTLOG_STATUS_ROLE and index.column() == 0:
            path = self.filePath(index)
            if path.endswith(".testlog") and not self.isDir(index):
                return self._status_for_path(path)

        return super().data(index, role)

    def _build_tooltip(self, path):
        try:
            stat_result = os.stat(path)
        except OSError:
            return ""

        size_bytes = stat_result.st_size
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

        file_info = QFileInfo(path)
        modified = file_info.lastModified().toString("yyyy-MM-dd HH:mm")
        created = self._format_datetime(file_info.birthTime())

        return (
            f"Status:   {TESTLOG_STATUS_LABELS[self._status_for_path(path)]}\n"
            f"Ändrad:   {modified}\n"
            f"Skapad:   {created}\n"
            f"Storlek:  {size_str}"
        )

    def refresh_status(self, path):
        self._status_cache.pop(path, None)
        index = self.index(path)
        if index.isValid():
            self.dataChanged.emit(
                index,
                index,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole, TESTLOG_STATUS_ROLE],
            )

    def _status_for_path(self, path):
        try:
            modified = os.stat(path).st_mtime
        except OSError:
            return "todo"

        cached = self._status_cache.get(path)
        if cached is not None and cached[0] == modified:
            return cached[1]

        status = read_testlog_status_from_archive(path)
        self._status_cache[path] = (modified, status)
        return status

    @staticmethod
    def _format_datetime(date_time):
        if not date_time.isValid():
            return "Ej tillgänglig"
        return date_time.toString("yyyy-MM-dd HH:mm")


class WorkspaceSortProxyModel(QSortFilterProxyModel):
    def __init__(self, source_model, pinned_paths=None, parent=None):
        super().__init__(parent)
        self._source_model = source_model
        self.pinned_paths = pinned_paths if pinned_paths is not None else set()
        self.search_term = ""
        self.sort_mode = "name"
        self.setSourceModel(source_model)
        self.setDynamicSortFilter(True)
        self.setRecursiveFilteringEnabled(True)

    def lessThan(self, left, right):
        left_path = self._source_model.filePath(left)
        right_path = self._source_model.filePath(right)

        left_is_dir = self._source_model.isDir(left)
        right_is_dir = self._source_model.isDir(right)
        left_is_pinned_file = left_path in self.pinned_paths and not left_is_dir
        right_is_pinned_file = right_path in self.pinned_paths and not right_is_dir

        left_rank = self._sort_rank(left_is_pinned_file, left_is_dir)
        right_rank = self._sort_rank(right_is_pinned_file, right_is_dir)
        if left_rank != right_rank:
            return left_rank < right_rank

        if self.sort_mode == "name":
            left_name = Path(left_path).stem if left_path.endswith(".testlog") else self._source_model.fileName(left)
            right_name = Path(right_path).stem if right_path.endswith(".testlog") else self._source_model.fileName(right)
            return left_name.lower() < right_name.lower()

        if self.sort_mode in ("modified", "created"):
            left_timestamp = self._timestamp(left_path, self.sort_mode)
            right_timestamp = self._timestamp(right_path, self.sort_mode)
            if left_timestamp != right_timestamp:
                return left_timestamp > right_timestamp
            left_name = Path(left_path).stem if left_path.endswith(".testlog") else self._source_model.fileName(left)
            right_name = Path(right_path).stem if right_path.endswith(".testlog") else self._source_model.fileName(right)
            return left_name.lower() < right_name.lower()

        return super().lessThan(left, right)

    @staticmethod
    def _timestamp(path, sort_mode):
        if sort_mode == "created":
            return WorkspaceSortProxyModel._created_timestamp(path)
        try:
            stat_result = os.stat(path)
        except OSError:
            return 0.0
        return stat_result.st_mtime

    @staticmethod
    def _created_timestamp(path):
        created = QFileInfo(path).birthTime()
        if not created.isValid():
            return 0.0
        return created.toSecsSinceEpoch()

    def set_sort_mode(self, mode):
        self.sort_mode = mode
        self.invalidate()

    @staticmethod
    def _sort_rank(is_pinned_file, is_dir):
        if is_dir:
            return 0
        if is_pinned_file:
            return 1
        return 2

    def set_search(self, term):
        self.search_term = term.lower().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        index = self._source_model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False

        if not self.search_term:
            return True

        if self._source_model.isDir(index):
            return self._directory_contains_match(index)

        filename = self._source_model.fileName(index).lower()
        return self.search_term in filename

    def _directory_contains_match(self, directory_index):
        for row in range(self._source_model.rowCount(directory_index)):
            child_index = self._source_model.index(row, 0, directory_index)
            if not child_index.isValid():
                continue
            if self._source_model.isDir(child_index):
                if self._directory_contains_match(child_index):
                    return True
            else:
                filename = self._source_model.fileName(child_index).lower()
                if self.search_term in filename:
                    return True
        return False
