import os
from pathlib import Path

from PySide6.QtCore import Qt, QFileInfo, QSortFilterProxyModel
from PySide6.QtWidgets import QFileSystemModel

from testlog_utils import (
    TESTLOG_STATUS_LABELS,
    format_testlog_tags,
    normalize_testlog_tags,
    read_testlog_header_from_archive,
)

TESTLOG_STATUS_ROLE = Qt.ItemDataRole.UserRole + 20
TESTLOG_TAGS_ROLE = Qt.ItemDataRole.UserRole + 21


def parse_sidebar_search(text):
    # "#td login" -> name term "login" and tag terms ["td"]; a lone "#" stays name text.
    name_words = []
    tag_terms = []
    for word in (text or "").split():
        if word.startswith("#") and len(word) > 1:
            tag_terms.extend(tag for tag in normalize_testlog_tags(word) if tag not in tag_terms)
        else:
            name_words.append(word)
    return " ".join(name_words).lower(), tag_terms


def sidebar_search_matches(name_term, tag_terms, filename, tags):
    # Tag terms match whole tags only, so "#td" does not match "tdialog".
    if name_term and name_term not in filename.lower():
        return False
    return all(tag in tags for tag in tag_terms)


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
        self._header_cache = {}

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

        if role == TESTLOG_TAGS_ROLE and index.column() == 0:
            path = self.filePath(index)
            if path.endswith(".testlog") and not self.isDir(index):
                return self.tags_for_path(path)

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

        status, tags = self._header_for_path(path)
        tags_line = f"Taggar:   {format_testlog_tags(tags)}\n" if tags else ""
        return (
            f"Status:   {TESTLOG_STATUS_LABELS[status]}\n"
            f"{tags_line}"
            f"Ändrad:   {modified}\n"
            f"Skapad:   {created}\n"
            f"Storlek:  {size_str}"
        )

    def refresh_status(self, path):
        self._header_cache.pop(path, None)
        index = self.index(path)
        if index.isValid():
            self.dataChanged.emit(
                index,
                index,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole, TESTLOG_STATUS_ROLE, TESTLOG_TAGS_ROLE],
            )

    def _status_for_path(self, path):
        return self._header_for_path(path)[0]

    def tags_for_path(self, path):
        return self._header_for_path(path)[1]

    def _header_for_path(self, path):
        # Status and tags come from one read of the note header, cached until the file changes.
        try:
            modified = os.stat(path).st_mtime
        except OSError:
            return "todo", []

        cached = self._header_cache.get(path)
        if cached is not None and cached[0] == modified:
            return cached[1], cached[2]

        status, tags = read_testlog_header_from_archive(path)
        self._header_cache[path] = (modified, status, tags)
        return status, tags

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
        self.search_tags = []
        self._matching_dirs = set()
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
        self.search_term, self.search_tags = parse_sidebar_search(term)
        self._matching_dirs = self._find_matching_dirs() if self.search_term or self.search_tags else set()
        self.invalidateFilter()

    @staticmethod
    def _path_key(path):
        # QFileSystemModel uses "/" on Windows while os.walk uses "\\"; compare normalized paths.
        return os.path.normcase(os.path.normpath(path))

    def _find_matching_dirs(self):
        # QFileSystemModel only lists folders once they are expanded, so folder matches are
        # decided from the files on disk; otherwise notes in collapsed folders are never found.
        root = self._source_model.rootPath()
        if not root or not os.path.isdir(root):
            return set()

        matching_dirs = set()
        for directory, _, filenames in os.walk(root):
            if any(self._name_and_tags_match(directory, filename) for filename in filenames):
                key = self._path_key(directory)
                root_key = self._path_key(root)
                while key not in matching_dirs:
                    matching_dirs.add(key)
                    if key == root_key:
                        break
                    parent = os.path.dirname(key)
                    if parent == key:
                        break
                    key = parent
        return matching_dirs

    def _name_and_tags_match(self, directory, filename):
        path = os.path.join(directory, filename)
        tags = self._source_model.tags_for_path(path) if self.search_tags and filename.endswith(".testlog") else []
        return sidebar_search_matches(self.search_term, self.search_tags, filename, tags)

    def filterAcceptsRow(self, source_row, source_parent):
        index = self._source_model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False

        if not self.search_term and not self.search_tags:
            return True

        if self._source_model.isDir(index):
            return self._directory_contains_match(index)

        return self._file_matches(index)

    def _file_matches(self, index):
        return self._name_and_tags_match(os.path.dirname(self._source_model.filePath(index)), self._source_model.fileName(index))

    def _directory_contains_match(self, directory_index):
        key = self._path_key(self._source_model.filePath(directory_index))
        # The workspace root and the folders above it always stay, so the tree keeps its root.
        root_key = self._path_key(self._source_model.rootPath())
        if root_key == key or root_key.startswith(key.rstrip(os.sep) + os.sep):
            return True
        return key in self._matching_dirs
