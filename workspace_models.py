from pathlib import Path

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import QFileSystemModel


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

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
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

        return super().data(index, role)


class WorkspaceSortProxyModel(QSortFilterProxyModel):
    def __init__(self, source_model, pinned_paths=None, parent=None):
        super().__init__(parent)
        self._source_model = source_model
        self.pinned_paths = pinned_paths if pinned_paths is not None else set()
        self.search_term = ""
        self.setSourceModel(source_model)
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

        left_name = Path(left_path).stem if left_path.endswith(".testlog") else self._source_model.fileName(left)
        right_name = Path(right_path).stem if right_path.endswith(".testlog") else self._source_model.fileName(right)
        return left_name.lower() < right_name.lower()

    @staticmethod
    def _sort_rank(is_pinned_file, is_dir):
        if is_pinned_file:
            return 0
        if is_dir:
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
