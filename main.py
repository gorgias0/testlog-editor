import sys
import os
import uuid
import json
import zipfile
import shutil
import re
import base64
import tempfile
import ctypes
import threading
from enum import Enum
from html import escape as html_escape
from html.parser import HTMLParser
from urllib.parse import quote as url_quote, unquote as url_unquote, urlparse
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter,
    QTextEdit, QFileDialog, QTreeView,
    QWidget, QVBoxLayout,
    QPushButton, QHBoxLayout, QInputDialog,
    QToolBar, QStatusBar, QLabel, QComboBox,
    QMenu, QMessageBox,
    QLineEdit, QStyle, QSizePolicy, QToolButton,
    QDialog, QDialogButtonBox, QFormLayout, QCheckBox,
    QListWidget, QListWidgetItem, QGraphicsDropShadowEffect,
    QStyledItemDelegate, QStyleOptionViewItem,
)
from PySide6.QtCore import Qt, QTimer, QDir, QMarginsF, QUrl, QSettings, QDate, QTime, QObject, Slot, Signal, QItemSelectionModel, QSize, QPoint, QFileInfo, QRect
from PySide6.QtGui import QImage, QAction, QActionGroup, QPageLayout, QPageSize, QFont, QFontDatabase, QKeySequence, QTextCursor, QTextBlockFormat, QIntValidator, QShortcut, QColor, QTextCharFormat, QSyntaxHighlighter, QDesktopServices, QPainter
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineContextMenuRequest, QWebEnginePage, QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel
from markdown_it import MarkdownIt
from styles import PREVIEW_STYLE
from icons import (
    APP_ICON_SVG,
    FOLDER_ICON_SVG,
    FOLDER_PINNED_ICON_SVG,
    TESTLOG_ICON_SVG,
    TESTLOG_PINNED_ICON_SVG,
    icon_from_svg,
    multi_icon_from_svg,
)
from diff_window import DiffWindow
from document_find_bar import DocumentFindBar
from json_tools import format_json_best_effort
from text_tool_dialog import TextToolDialog
from testlog_utils import (
    build_fulltext_search_results,
    collect_referenced_image_filenames,
    DEFAULT_TESTLOG_STATUS,
    get_testlog_status,
    guess_markdown_from_plain_text,
    highlight_fulltext_snippet,
    normalize_testlog_status,
    read_testlog_status_from_archive,
    resolve_preview_image_path,
    set_testlog_status,
    suggest_filename_from_heading,
    strip_testlog_front_matter,
    TESTLOG_STATUS_LABELS,
    TESTLOG_STATUS_OPTIONS,
)
from translations import TRANSLATIONS
from workspace_models import TESTLOG_STATUS_ROLE, WorkspaceFileSystemModel, WorkspaceSortProxyModel

try:
    from mdit_py_plugins.tasklists import tasklists_plugin
except ImportError:
    tasklists_plugin = None


class SortMode(Enum):
    NAME = "name"
    MODIFIED = "modified"
    CREATED = "created"


class ViewMode(Enum):
    SINGLE = "single"
    SPLIT = "split"


DEFAULT_INDENT_STYLE = "spaces2"
INDENT_STYLE_TEXT = {
    "spaces2": "  ",
    "spaces4": "    ",
    "tabs": "\t",
}
EDITOR_LINE_HEIGHT_PERCENT = 115
EDITOR_LINE_HEIGHT_TYPE = QTextBlockFormat.LineHeightTypes.ProportionalHeight.value


EDITOR_ON_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 52">
  <rect x="0" y="0" width="72" height="52" rx="6" fill="#555"/>
  <text x="36" y="35" text-anchor="middle" font-family="monospace" font-size="18" font-weight="bold" fill="white">&lt;/&gt;</text>
</svg>'''

EDITOR_OFF_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 52">
  <rect x="0" y="0" width="72" height="52" rx="6" fill="none" stroke="#aaa" stroke-width="2"/>
  <text x="36" y="35" text-anchor="middle" font-family="monospace" font-size="18" font-weight="bold" fill="#aaa">&lt;/&gt;</text>
</svg>'''

class Editor(QTextEdit):
    def __init__(
        self,
        on_image_paste,
        translate=lambda text: text,
        link_base_path=lambda: None,
        indent_text=INDENT_STYLE_TEXT[DEFAULT_INDENT_STYLE],
    ):
        super().__init__()
        self.on_image_paste = on_image_paste
        self._tr = translate
        self._link_base_path = link_base_path
        self.indent_text = indent_text
        self.setAcceptRichText(False)
        self._preview_scroll_sync_active = False
        self._preview_scroll_sync_timer = QTimer(self)
        self._preview_scroll_sync_timer.setSingleShot(True)
        self._preview_scroll_sync_timer.timeout.connect(self._clear_preview_scroll_sync)
        self.verticalScrollBar().sliderPressed.connect(self._begin_preview_scroll_sync)
        self.verticalScrollBar().sliderReleased.connect(self._hold_preview_scroll_sync_briefly)
        self._applying_block_spacing = False
        self.document().contentsChange.connect(self._apply_line_spacing_for_changed_range)
        QTimer.singleShot(0, self.apply_line_spacing_to_document)

    def _capture_view_state(self):
        return (
            self.verticalScrollBar().value(),
            self.horizontalScrollBar().value(),
        )

    def _restore_view_state(self, view_state):
        vertical_value, horizontal_value = view_state
        self.verticalScrollBar().setValue(vertical_value)
        self.horizontalScrollBar().setValue(horizontal_value)

    def _begin_preview_scroll_sync(self):
        self._preview_scroll_sync_active = True
        self._preview_scroll_sync_timer.stop()

    def _hold_preview_scroll_sync_briefly(self):
        self._preview_scroll_sync_active = True
        self._preview_scroll_sync_timer.start(180)

    def _clear_preview_scroll_sync(self):
        self._preview_scroll_sync_active = False

    def should_sync_preview_scroll(self):
        return self._preview_scroll_sync_active

    def _get_leading_whitespace(self, line: str) -> str:
        match = re.match(r'^(\s+)', line)
        return match.group(1) if match else ""

    def set_indent_text(self, indent_text):
        self.indent_text = indent_text or INDENT_STYLE_TEXT[DEFAULT_INDENT_STYLE]

    def _set_text_cursor_visible(self, cursor):
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        QTimer.singleShot(0, self.ensureCursorVisible)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = QImage(source.imageData())
            self.on_image_paste(image)
        elif source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

    def apply_line_spacing_to_document(self):
        self._apply_line_spacing_range(0, self.document().characterCount())

    def _apply_line_spacing_for_changed_range(self, position, chars_removed, chars_added):
        if self._applying_block_spacing:
            return

        span = max(chars_removed, chars_added, 1)
        self._apply_line_spacing_range(position, span)

    def _apply_line_spacing_range(self, position, span):
        doc = self.document()
        if doc is None or self._applying_block_spacing:
            return

        start_block = doc.findBlock(max(0, position))
        end_pos = min(max(0, position) + max(0, span), max(0, doc.characterCount() - 1))
        end_block = doc.findBlock(end_pos)

        if not start_block.isValid():
            start_block = doc.firstBlock()
        if not end_block.isValid():
            end_block = doc.lastBlock()
        if not start_block.isValid() or not end_block.isValid():
            return

        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        self._applying_block_spacing = True
        try:
            block = start_block
            while block.isValid():
                block_format = block.blockFormat()
                if (
                    block_format.lineHeight() != EDITOR_LINE_HEIGHT_PERCENT
                    or block_format.lineHeightType() != EDITOR_LINE_HEIGHT_TYPE
                ):
                    block_format.setLineHeight(
                        float(EDITOR_LINE_HEIGHT_PERCENT),
                        EDITOR_LINE_HEIGHT_TYPE,
                    )
                    cursor.setPosition(block.position())
                    cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                    cursor.mergeBlockFormat(block_format)

                if block == end_block:
                    break
                block = block.next()
        finally:
            self._applying_block_spacing = False
            cursor.endEditBlock()

    def keyPressEvent(self, event):
        if event.key() in (
            Qt.Key.Key_PageUp,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            self._hold_preview_scroll_sync_briefly()
        if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._handle_smart_enter()
            return
        elif event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if self.textCursor().hasSelection():
                super().keyPressEvent(event)
            else:
                self.copy_line()
            return
        elif event.key() == Qt.Key.Key_X and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if self.textCursor().hasSelection():
                super().keyPressEvent(event)
            else:
                self.cut_line()
            return
        elif event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._handle_tab()
            return
        elif (
            event.key() == Qt.Key.Key_Backtab
            or event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            self._handle_shift_tab()
            return
        elif event.key() == Qt.Key.Key_Up and event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self.move_lines_up()
            return
        elif event.key() == Qt.Key.Key_Down and event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self.move_lines_down()
            return
        elif event.text() == '`':
            self._handle_backtick()
            return
        elif event.key() == Qt.Key.Key_B and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.format_bold()
            return
        elif event.key() == Qt.Key.Key_I and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.format_italic()
            return
        elif event.key() == Qt.Key.Key_K and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            self.format_code_block()
            return
        elif event.key() == Qt.Key.Key_D and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            self.insert_current_date()
            return
        elif event.key() == Qt.Key.Key_D and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            self.duplicate_lines_down()
            return
        
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        self._hold_preview_scroll_sync_briefly()
        super().wheelEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            link_url = self._link_at_position(self.cursorForPosition(event.pos()).position())
            if link_url:
                self.copy_link(link_url)
                return
        if event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            link_url = self._link_at_position(self.cursorForPosition(event.pos()).position())
            if link_url:
                self.open_link(link_url)
                return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        link_url = self._link_at_position(self.cursorForPosition(event.pos()).position())
        menu = self.createStandardContextMenu()
        if link_url:
            menu.insertSeparator(menu.actions()[0] if menu.actions() else None)
            copy_link_action = QAction(self._tr("Copy Link"), menu)
            copy_link_action.triggered.connect(lambda checked=False, url=link_url: self.copy_link(url))
            open_link_action = QAction(self._tr("Open Link"), menu)
            open_link_action.triggered.connect(lambda checked=False, url=link_url: self.open_link(url))
            menu.insertAction(menu.actions()[0] if menu.actions() else None, copy_link_action)
            menu.insertAction(copy_link_action, open_link_action)
            open_link_action.setEnabled(not link_url.startswith("#"))
        menu.exec(event.globalPos())
        menu.deleteLater()

    def copy_link(self, url):
        QApplication.clipboard().setText(url)

    def open_link(self, url):
        if not url or url.startswith("#"):
            return

        parsed_url = urlparse(url)
        if parsed_url.scheme:
            target = QUrl(url)
        else:
            base_path = self._link_base_path()
            if base_path:
                target_path = url
                fragment = ""
                if "#" in target_path:
                    target_path, fragment = target_path.split("#", 1)
                    fragment = f"#{fragment}"
                if target_path:
                    target = QUrl.fromLocalFile(
                        os.path.abspath(os.path.join(base_path, url_unquote(target_path)))
                    )
                    if fragment:
                        target.setFragment(fragment[1:])
                else:
                    return
            else:
                target = QUrl.fromUserInput(url)

        QDesktopServices.openUrl(target)

    def _link_at_position(self, position):
        text = self.toPlainText()
        if not text:
            return None

        lookup_position = max(0, min(position, len(text) - 1))
        for pattern, url_group in (
            (r"!?\[[^\]\n]*\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)", 1),
            (r"<((?:https?|ftp)://[^>\s]+|mailto:[^>\s]+)>", 1),
            (r"((?:https?|ftp)://[^\s<>()]+|mailto:[^\s<>()]+)", 1),
        ):
            for match in re.finditer(pattern, text):
                if match.start() <= lookup_position <= match.end():
                    return match.group(url_group).rstrip(".,;:")
        return None

    def _handle_smart_enter(self):
        cursor = self.textCursor()
        block = cursor.block()
        line_text = block.text()
        doc = self.document()
        is_last_line = block.blockNumber() == doc.blockCount() - 1
        position_in_block = cursor.positionInBlock()
        indent = self._get_leading_whitespace(line_text)

        if indent and not line_text.strip():
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.insertText("")
            cursor.insertText("\n")
            self._set_text_cursor_visible(cursor)
            return

        list_text = line_text[len(indent):]

        checkbox_match = re.match(r'^(-\s+\[( |x|X)\]\s?)(.*)$', list_text)
        if checkbox_match:
            prefix = checkbox_match.group(1)
            content = checkbox_match.group(3)
            if not content.strip():
                cursor.movePosition(cursor.MoveOperation.StartOfLine)
                cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                if indent:
                    cursor.insertText(indent)
                self._set_text_cursor_visible(cursor)
                if not indent and not is_last_line:
                    cursor.insertText('\n')
                    self._set_text_cursor_visible(cursor)
            elif position_in_block < len(line_text):
                self._split_list_item(f'{indent}{prefix}', content, position_in_block, f'{indent}- [ ] ')
            else:
                cursor.movePosition(cursor.MoveOperation.EndOfLine)
                cursor.insertText(f'\n{indent}- [ ] ')
                self._set_text_cursor_visible(cursor)
            return

        # Check for bullet list
        bullet_match = re.match(r'^(-\s+)(.*)$', list_text)
        if bullet_match:
            prefix = bullet_match.group(1)
            content = bullet_match.group(2)
            if not content.strip():
                # Empty list item, exit list mode
                cursor.movePosition(cursor.MoveOperation.StartOfLine)
                cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                if indent:
                    cursor.insertText(indent)
                self._set_text_cursor_visible(cursor)
                if not indent and not is_last_line:
                    cursor.insertText('\n')
                    self._set_text_cursor_visible(cursor)
            elif position_in_block < len(line_text):
                self._split_list_item(f'{indent}{prefix}', content, position_in_block, f'{indent}{prefix}')
            else:
                # Continue list
                cursor.movePosition(cursor.MoveOperation.EndOfLine)
                cursor.insertText(f'\n{indent}{prefix}')
                self._set_text_cursor_visible(cursor)
            return

        # Check for numbered list
        match = re.match(r'^((\d+)\.\s+)(.*)$', list_text)
        if match:
            prefix = match.group(1)
            num = int(match.group(2))
            content = match.group(3)
            if not content.strip():
                # Empty numbered item, exit list mode
                cursor.movePosition(cursor.MoveOperation.StartOfLine)
                cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                if indent:
                    cursor.insertText(indent)
                self._set_text_cursor_visible(cursor)
                if not indent and not is_last_line:
                    cursor.insertText('\n')
                    self._set_text_cursor_visible(cursor)
            elif position_in_block < len(line_text):
                self._split_list_item(f'{indent}{prefix}', content, position_in_block, f'{indent}{num + 1}. ')
            else:
                # Continue numbered list
                cursor.movePosition(cursor.MoveOperation.EndOfLine)
                cursor.insertText(f'\n{indent}{num + 1}. ')
                self._set_text_cursor_visible(cursor)
            return

        if indent:
            cursor.insertText(f'\n{indent}')
            self._set_text_cursor_visible(cursor)
            return

        cursor.insertText('\n')
        self._set_text_cursor_visible(cursor)

    def _split_list_item(self, current_prefix, content, position_in_block, next_prefix):
        cursor = self.textCursor()
        split_offset = max(0, position_in_block - len(current_prefix))
        before_content = content[:split_offset]
        after_content = content[split_offset:]

        cursor.beginEditBlock()
        cursor.movePosition(cursor.MoveOperation.StartOfLine)
        cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(f"{current_prefix}{before_content}\n{next_prefix}{after_content}")
        cursor.setPosition(cursor.position() - len(after_content))
        self._set_text_cursor_visible(cursor)
        cursor.endEditBlock()

    def _handle_tab(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            self._indent_selected_lines(cursor)
            return

        block = cursor.block()
        line_text = block.text()

        if self._is_list_line(line_text):
            # Indent list item
            indent_size = len(self._indent_prefix_for_line(line_text))
            cursor.beginEditBlock()
            self._indent_block(block)
            cursor.endEditBlock()
            cursor.setPosition(block.position() + indent_size)
            self._set_text_cursor_visible(cursor)
        else:
            # Default tab
            cursor.insertText(self._indent_prefix_for_line(line_text))

    def _handle_shift_tab(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            self._unindent_selected_lines(cursor)
            return

        block = cursor.block()
        line_text = block.text()

        # Remove one indentation unit from the start of the line
        cursor.movePosition(cursor.MoveOperation.StartOfLine)
        self._set_text_cursor_visible(cursor)
        chars_to_remove = self._unindent_char_count(line_text)

        for _ in range(chars_to_remove):
            cursor.deleteChar()

    def _selected_block_range(self, cursor):
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        start_block = self.document().findBlock(selection_start)
        end_block = self.document().findBlock(selection_end)
        if (
            selection_end > selection_start
            and selection_end == end_block.position()
            and end_block.previous().isValid()
        ):
            end_block = end_block.previous()
        return start_block, end_block, selection_start, selection_end

    def _indent_prefix_for_line(self, line_text):
        return self.indent_text

    def _is_list_line(self, line_text):
        return bool(re.match(r'^\s*[-+*]\s+', line_text) or self._ordered_list_match(line_text))

    def _ordered_list_match(self, line_text):
        return re.match(r'^(\s*)(\d+)(\.)(\s*)', line_text)

    def _unindent_char_count(self, line_text):
        if not line_text:
            return 0
        if self.indent_text == '\t' and line_text.startswith('\t'):
            return 1
        if line_text.startswith('\t'):
            return 1
        space_match = re.match(r'^( +)', line_text)
        if space_match:
            leading_spaces = len(space_match.group(1))
            if re.match(r'^ +(?:[-+*]|\d+\.)\s+', line_text):
                if self.indent_text == '\t':
                    return min(4, leading_spaces)
                indent_width = len(self.indent_text)
                if indent_width == 2 and leading_spaces % 3 == 0:
                    return min(3, leading_spaces)
                return min(indent_width, leading_spaces)
            if self.indent_text != '\t' and line_text.startswith(self.indent_text):
                return len(self.indent_text)
            if leading_spaces >= 4 and len(self.indent_text) <= 4:
                return min(4, leading_spaces)
            if leading_spaces >= 2:
                return min(2, leading_spaces)
            return 1
        if line_text.startswith(' '):
            return 1
        return 0

    def _indent_selected_lines(self, cursor):
        start_block, end_block, selection_start, selection_end = self._selected_block_range(cursor)
        block = start_block
        inserted_count = 0
        ordered_counter = None
        ordered_indent = None

        cursor.beginEditBlock()
        while block.isValid() and block.blockNumber() <= end_block.blockNumber():
            ordered_match = self._ordered_list_match(block.text())
            ordered_number = None
            if ordered_match:
                current_indent = ordered_match.group(1)
                if ordered_counter is None or current_indent != ordered_indent:
                    ordered_counter = 1
                    ordered_indent = current_indent
                else:
                    ordered_counter += 1
                ordered_number = ordered_counter
            else:
                ordered_counter = None
                ordered_indent = None

            inserted_count += self._indent_block(block, ordered_number=ordered_number)
            block = block.next()
        cursor.endEditBlock()

        cursor.setPosition(selection_start)
        cursor.setPosition(selection_end + inserted_count, QTextCursor.MoveMode.KeepAnchor)
        self._set_text_cursor_visible(cursor)

    def _indent_block(self, block, ordered_number=None):
        line_text = block.text()
        prefix = self._indent_prefix_for_line(line_text)
        edit_cursor = QTextCursor(block)
        edit_cursor.insertText(prefix)
        change_count = len(prefix)

        numbered_match = self._ordered_list_match(line_text)
        if numbered_match:
            next_number = ordered_number or 1
            next_marker = f'{next_number}. '
            marker_length = (
                len(numbered_match.group(2))
                + len(numbered_match.group(3))
                + len(numbered_match.group(4))
            )
            number_start = block.position() + len(prefix) + len(numbered_match.group(1))
            edit_cursor.setPosition(number_start)
            edit_cursor.setPosition(
                number_start + marker_length,
                QTextCursor.MoveMode.KeepAnchor,
            )
            edit_cursor.insertText(next_marker)
            change_count += len(next_marker) - marker_length

        return change_count

    def _unindent_selected_lines(self, cursor):
        start_block, end_block, selection_start, selection_end = self._selected_block_range(cursor)
        block = start_block
        removed_count = 0

        cursor.beginEditBlock()
        while block.isValid() and block.blockNumber() <= end_block.blockNumber():
            next_block = block.next()
            chars_to_remove = self._unindent_char_count(block.text())
            if chars_to_remove:
                edit_cursor = QTextCursor(block)
                for _ in range(chars_to_remove):
                    edit_cursor.deleteChar()
                removed_count += chars_to_remove
            block = next_block
        cursor.endEditBlock()

        cursor.setPosition(selection_start)
        cursor.setPosition(max(selection_start, selection_end - removed_count), QTextCursor.MoveMode.KeepAnchor)
        self._set_text_cursor_visible(cursor)

    def format_bold(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.removeSelectedText()
            cursor.insertText(f'**{text}**')
        else:
            cursor.insertText('****')
            cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.MoveAnchor, 2)
            self.setTextCursor(cursor)

    def format_italic(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.removeSelectedText()
            cursor.insertText(f'*{text}*')
        else:
            cursor.insertText('**')
            cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.MoveAnchor, 1)
            self.setTextCursor(cursor)

    def format_inline_code(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.removeSelectedText()
            cursor.insertText(f'`{text}`')
        else:
            cursor.insertText('``')
            cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.MoveAnchor, 1)
            self.setTextCursor(cursor)

    def format_underline(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.removeSelectedText()
            cursor.insertText(f'<u>{text}</u>')
        else:
            cursor.insertText('<u></u>')
            cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.MoveAnchor, 4)
            self.setTextCursor(cursor)

    def _handle_backtick(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            self.format_inline_code()
        else:
            # Insert single backtick
            cursor.insertText('`')
            self.setTextCursor(cursor)
            
            # Check if we now have three consecutive backticks
            self._check_for_triple_backtick()

    def _check_for_triple_backtick(self):
        cursor = self.textCursor()
        pos = cursor.positionInBlock()
        block = cursor.block()
        line_text = block.text()
        
        # Get the three characters before cursor
        if pos >= 3:
            before_text = line_text[max(0, pos - 3):pos]
            if before_text == '```':
                # Check if preceded by whitespace or at start of line
                if pos == 3 or line_text[pos - 4].isspace():
                    # Delete the three backticks
                    cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.MoveAnchor, 3)
                    cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, 3)
                    cursor.removeSelectedText()
                    self.setTextCursor(cursor)
                    
                    # Insert code block
                    cursor.insertText('```\n\n```')
                    cursor.movePosition(cursor.MoveOperation.Up)
                    cursor.movePosition(cursor.MoveOperation.EndOfLine)
                    self.setTextCursor(cursor)

    def format_code_block(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.removeSelectedText()
            cursor.insertText(f'```\n{text}\n```')
        else:
            cursor.insertText('```\n\n```')
            cursor.movePosition(cursor.MoveOperation.Up)
            cursor.movePosition(cursor.MoveOperation.EndOfLine)
            self.setTextCursor(cursor)

    def insert_current_date(self):
        cursor = self.textCursor()
        cursor.insertText(QDate.currentDate().toString("yyyy-MM-dd"))

    def insert_current_time(self):
        cursor = self.textCursor()
        cursor.insertText(QTime.currentTime().toString("HH:mm:ss"))
        self.setTextCursor(cursor)

    def insert_current_date_time(self):
        cursor = self.textCursor()
        cursor.insertText(
            f"{QDate.currentDate().toString('yyyy-MM-dd')} {QTime.currentTime().toString('HH:mm:ss')}"
        )
        self.setTextCursor(cursor)

    def insert_markdown_text(self, text):
        cursor = self.textCursor()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def copy_line(self):
        line_text, _ = self._selected_line_range()
        QApplication.clipboard().setText(line_text)

    def cut_line(self):
        line_text, (start_pos, end_pos) = self._selected_line_range()
        QApplication.clipboard().setText(line_text)

        view_state = self._capture_view_state()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(start_pos)
        cursor.setPosition(end_pos, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self._restore_view_state(view_state)

    def move_lines_up(self):
        self._move_selected_lines(-1)

    def move_lines_down(self):
        self._move_selected_lines(1)

    def duplicate_lines_down(self):
        text, (_, end_pos) = self._selected_line_range()
        view_state = self._capture_view_state()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(end_pos)

        insert_text = text
        if end_pos > 0:
            doc_text = self.toPlainText()
            if end_pos >= len(doc_text) or doc_text[end_pos - 1] != "\n":
                insert_text = "\n" + insert_text

        cursor.insertText(insert_text)

        new_start = end_pos + (len(insert_text) - len(text))
        new_cursor = self.textCursor()
        new_cursor.setPosition(new_start)
        new_cursor.setPosition(new_start + len(text), new_cursor.MoveMode.KeepAnchor)
        self.setTextCursor(new_cursor)
        cursor.endEditBlock()
        self._restore_view_state(view_state)

    def _selected_line_range(self):
        cursor = self.textCursor()
        doc = self.document()

        start_pos = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        end_pos = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()

        start_block = doc.findBlock(start_pos)
        end_block = doc.findBlock(end_pos)

        if cursor.hasSelection() and end_pos > start_pos and end_pos == end_block.position():
            end_block = end_block.previous()

        if not end_block.isValid():
            end_block = start_block

        start_pos = start_block.position()
        last_block_number = end_block.blockNumber()
        if last_block_number < doc.blockCount() - 1:
            end_pos = doc.findBlockByNumber(last_block_number + 1).position()
        else:
            end_pos = doc.characterCount() - 1

        range_cursor = self.textCursor()
        range_cursor.setPosition(start_pos)
        range_cursor.setPosition(end_pos, range_cursor.MoveMode.KeepAnchor)
        return range_cursor.selectedText().replace("\u2029", "\n"), (start_pos, end_pos)

    def _move_selected_lines(self, direction):
        doc = self.document()
        full_text = self.toPlainText()
        view_state = self._capture_view_state()
        original_cursor = self.textCursor()
        _, (start_pos, end_pos) = self._selected_line_range()
        anchor_offset = original_cursor.anchor() - start_pos
        position_offset = original_cursor.position() - start_pos

        start_block = doc.findBlock(start_pos)
        end_lookup_pos = max(start_pos, end_pos - 1)
        end_block = doc.findBlock(end_lookup_pos)

        if direction < 0:
            previous_block = start_block.previous()
            if not previous_block.isValid():
                return
            replace_start = previous_block.position()
            replace_end = end_pos
            moved_text = full_text[start_pos:end_pos]
            adjacent_text = full_text[replace_start:start_pos]
            replacement_text = moved_text + adjacent_text
            selection_start = replace_start
            selection_end = replace_start + len(moved_text)
        else:
            next_block = end_block.next()
            if not next_block.isValid():
                return
            replace_start = start_pos
            if next_block.blockNumber() < doc.blockCount() - 1:
                replace_end = doc.findBlockByNumber(next_block.blockNumber() + 1).position()
            else:
                replace_end = len(full_text)
            moved_text = full_text[start_pos:end_pos]
            adjacent_text = full_text[end_pos:replace_end]
            if adjacent_text and not adjacent_text.endswith("\n") and moved_text.endswith("\n"):
                adjacent_text += "\n"
                moved_text = moved_text[:-1]
            replacement_text = adjacent_text + moved_text
            selection_start = start_pos + len(adjacent_text)
            selection_end = selection_start + len(moved_text)

        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(replace_start)
        cursor.setPosition(replace_end, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(replacement_text)
        self._renumber_ordered_lists()

        new_cursor = self.textCursor()
        moved_length = len(moved_text)
        new_anchor = selection_start + max(0, min(anchor_offset, moved_length))
        new_position = selection_start + max(0, min(position_offset, moved_length))
        new_cursor.setPosition(new_anchor)
        if original_cursor.hasSelection():
            new_cursor.setPosition(new_position, new_cursor.MoveMode.KeepAnchor)
        else:
            new_cursor.setPosition(new_position)
        self.setTextCursor(new_cursor)

        cursor.endEditBlock()
        self._restore_view_state(view_state)

    def _renumber_ordered_lists(self):
        doc = self.document()
        block = doc.firstBlock()
        ordered_levels = []
        cursor = QTextCursor(doc)

        while block.isValid():
            ordered_match = self._ordered_list_match(block.text())
            if not ordered_match:
                ordered_levels.clear()
                block = block.next()
                continue

            indent = ordered_match.group(1)

            while ordered_levels and len(ordered_levels[-1][0]) > len(indent):
                ordered_levels.pop()

            while ordered_levels and ordered_levels[-1][0] != indent and len(ordered_levels[-1][0]) >= len(indent):
                ordered_levels.pop()

            if ordered_levels and ordered_levels[-1][0] == indent:
                next_number = ordered_levels[-1][1] + 1
                ordered_levels[-1] = (indent, next_number)
            else:
                next_number = 1
                ordered_levels.append((indent, next_number))

            marker_length = (
                len(ordered_match.group(2))
                + len(ordered_match.group(3))
                + len(ordered_match.group(4))
            )
            replacement_marker = f"{next_number}. "
            existing_marker = block.text()[
                len(indent):len(indent) + marker_length
            ]
            if existing_marker != replacement_marker:
                number_start = block.position() + len(indent)
                cursor.setPosition(number_start)
                cursor.setPosition(
                    number_start + marker_length,
                    QTextCursor.MoveMode.KeepAnchor,
                )
                cursor.insertText(replacement_marker)

            block = block.next()


class MarkdownHighlighter(QSyntaxHighlighter):
    CODE_BLOCK_STATE = 1

    def __init__(self, document, theme_mode="light"):
        super().__init__(document)
        self.theme_mode = theme_mode
        self._build_formats()

    def set_theme_mode(self, theme_mode):
        if theme_mode == self.theme_mode:
            return
        self.theme_mode = theme_mode
        self._build_formats()
        self.rehighlight()

    def _build_formats(self):
        dark = self.theme_mode == "dark"

        def make_format(*, foreground=None, background=None, bold=False, italic=False, underline=False):
            text_format = QTextCharFormat()
            if foreground is not None:
                text_format.setForeground(QColor(foreground))
            if background is not None:
                text_format.setBackground(QColor(background))
            if bold:
                text_format.setFontWeight(QFont.Weight.Bold)
            if italic:
                text_format.setFontItalic(True)
            if underline:
                text_format.setFontUnderline(True)
            return text_format

        self.heading_line_formats = {
            1: make_format(foreground="#1d4ed8" if not dark else "#93c5fd", bold=True),
            2: make_format(foreground="#2563eb" if not dark else "#7dd3fc", bold=True),
            3: make_format(foreground="#0f766e" if not dark else "#5eead4", bold=True),
            4: make_format(foreground="#7c3aed" if not dark else "#c4b5fd", bold=True),
            5: make_format(foreground="#9333ea" if not dark else "#d8b4fe", bold=True),
            6: make_format(foreground="#a16207" if not dark else "#fcd34d", bold=True),
        }
        self.heading_marker_format = make_format(foreground="#94a3b8" if not dark else "#6b7280", bold=True)
        self.list_marker_format = make_format(foreground="#0284c7" if not dark else "#7dd3fc", bold=True)
        self.checkbox_format = make_format(foreground="#059669" if not dark else "#86efac", bold=True)
        self.quote_format = make_format(foreground="#6b7280" if not dark else "#9ca3af", italic=True)
        self.quote_marker_format = make_format(foreground="#94a3b8" if not dark else "#6b7280", bold=True)
        self.code_block_format = make_format(
            foreground="#f8fafc" if not dark else "#f8fafc",
        )
        self.code_fence_format = make_format(
            foreground="#cbd5e1" if not dark else "#cbd5e1",
            bold=True,
        )
        self.inline_code_format = make_format(
            foreground="#b45309" if not dark else "#fdba74",
            background="#f3f4f6" if not dark else "#1f2937",
        )
        self.emphasis_marker_format = make_format(foreground="#94a3b8" if not dark else "#6b7280")
        self.bold_text_format = make_format(foreground="#111827" if not dark else "#f9fafb", bold=True)
        self.italic_text_format = make_format(foreground="#1f2937" if not dark else "#e5e7eb", italic=True)
        self.link_text_format = make_format(foreground="#2563eb" if not dark else "#93c5fd", underline=True)
        self.link_url_format = make_format(foreground="#7c3aed" if not dark else "#c4b5fd", underline=True)
        self.image_alt_format = make_format(foreground="#0f766e" if not dark else "#5eead4")
        self.image_url_format = make_format(foreground="#b45309" if not dark else "#fdba74")
        self.rule_format = make_format(foreground="#94a3b8" if not dark else "#6b7280", bold=True)

    def _apply_match_format(self, text, pattern, groups):
        for match in re.finditer(pattern, text):
            for group_index, text_format in groups:
                start, end = match.span(group_index)
                if end > start:
                    self.setFormat(start, end - start, text_format)

    def highlightBlock(self, text):
        self.setCurrentBlockState(0)
        previous_state = self.previousBlockState()
        fence_match = re.match(r"^(\s*)(`{3,}|~{3,})(.*)$", text)

        if previous_state == self.CODE_BLOCK_STATE:
            self.setFormat(0, len(text), self.code_block_format)
            if fence_match:
                self.setFormat(0, len(text), self.code_fence_format)
                self.setCurrentBlockState(0)
            else:
                self.setCurrentBlockState(self.CODE_BLOCK_STATE)
            return

        if fence_match:
            self.setFormat(0, len(text), self.code_fence_format)
            self.setCurrentBlockState(self.CODE_BLOCK_STATE)
            return

        heading_match = re.match(r"^(#{1,6})(\s+)(.*)$", text)
        if heading_match:
            level = len(heading_match.group(1))
            self.setFormat(0, len(text), self.heading_line_formats[level])
            self.setFormat(0, len(heading_match.group(1)), self.heading_marker_format)
            return

        if re.fullmatch(r"\s{0,3}([-*_])(?:\s*\1){2,}\s*", text):
            self.setFormat(0, len(text), self.rule_format)
            return

        quote_match = re.match(r"^(\s*>\s?)(.*)$", text)
        if quote_match:
            marker_length = len(quote_match.group(1))
            self.setFormat(0, len(text), self.quote_format)
            self.setFormat(0, marker_length, self.quote_marker_format)

        list_match = re.match(r"^(\s*)([-+*]|\d+[.)])(\s+)", text)
        if list_match:
            marker_start = len(list_match.group(1))
            marker_length = len(list_match.group(2))
            self.setFormat(marker_start, marker_length, self.list_marker_format)
            checkbox_match = re.match(r"^(\s*(?:[-+*]|\d+[.)])\s+)(\[(?: |x|X)\])", text)
            if checkbox_match:
                checkbox_start = len(checkbox_match.group(1))
                self.setFormat(checkbox_start, len(checkbox_match.group(2)), self.checkbox_format)

        self._apply_match_format(text, r"(`+)([^`].*?)(\1)", [
            (1, self.emphasis_marker_format),
            (2, self.inline_code_format),
            (3, self.emphasis_marker_format),
        ])
        self._apply_match_format(text, r"(\*\*|__)(?=\S)(.+?[*_]*)(?<=\S)\1", [
            (1, self.emphasis_marker_format),
            (2, self.bold_text_format),
            (0, self.bold_text_format),
        ])
        self._apply_match_format(text, r"(?<!\*)\*(?!\*)(?=\S)(.+?)(?<=\S)\*(?!\*)|(?<!_)_(?!_)(?=\S)(.+?)(?<=\S)_(?!_)", [
            (1, self.italic_text_format),
            (2, self.italic_text_format),
        ])
        self._apply_match_format(text, r"(!\[)([^\]]*)(\]\()([^)]+)(\))", [
            (1, self.emphasis_marker_format),
            (2, self.image_alt_format),
            (3, self.emphasis_marker_format),
            (4, self.image_url_format),
            (5, self.emphasis_marker_format),
        ])
        self._apply_match_format(text, r"(?<!!)(\[)([^\]]+)(\]\()([^)]+)(\))", [
            (1, self.emphasis_marker_format),
            (2, self.link_text_format),
            (3, self.emphasis_marker_format),
            (4, self.link_url_format),
            (5, self.emphasis_marker_format),
        ])
        self._apply_match_format(text, r"(<)((?:https?|ftp)://[^>\s]+|mailto:[^>\s]+)(>)", [
            (1, self.emphasis_marker_format),
            (2, self.link_url_format),
            (3, self.emphasis_marker_format),
        ])
        self._apply_match_format(text, r"(?<![\](<])((?:https?|ftp)://[^\s<>()]+|mailto:[^\s<>()]+)", [
            (1, self.link_url_format),
        ])


class PreviewPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if (
            nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked
            and url.scheme().lower() == "file"
        ):
            return False
        if url.scheme().lower() not in {"", "about", "data", "file"}:
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class PreviewBridge(QObject):
    def __init__(self, copy_text_handler, checkbox_toggle_handler, parent=None):
        super().__init__(parent)
        self._copy_text_handler = copy_text_handler
        self._checkbox_toggle_handler = checkbox_toggle_handler

    @Slot(str)
    def copyText(self, text):
        self._copy_text_handler(text)

    @Slot(int, bool)
    def toggleCheckbox(self, index, checked):
        self._checkbox_toggle_handler(index, checked)


class PreviewBareUrlLinkifier(HTMLParser):
    URL_PATTERN = re.compile(r"(?P<url>(?:https?|ftp)://[^\s<>()]+|mailto:[^\s<>()]+)")
    SKIP_TAGS = {"a", "code", "pre", "script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        self.parts.append(self.get_starttag_text())
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.parts.append(f"</{tag}>")
        if tag.lower() in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            self.parts.append(html_escape(data))
            return
        self.parts.append(self.URL_PATTERN.sub(self._link_replacement, data))

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")

    def _link_replacement(self, match):
        url = match.group("url")
        trailing = ""
        while url and url[-1] in ".,;:":
            trailing = url[-1] + trailing
            url = url[:-1]
        safe_url = html_escape(url, quote=True)
        return f'<a href="{safe_url}">{html_escape(url)}</a>{html_escape(trailing)}'

    def result(self):
        return "".join(self.parts)


def read_testlog_note_text(path):
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "note.md" not in zf.namelist():
                return None
            with zf.open("note.md") as note_file:
                return strip_testlog_front_matter(note_file.read().decode("utf-8"))
    except Exception:
        return None


class FullTextIndexSignals(QObject):
    progress = Signal(int, int, int)
    complete = Signal(int, dict)


class Indexer(threading.Thread):
    def __init__(self, workspace_dir, on_progress, on_complete):
        super().__init__(daemon=True)
        self.workspace_dir = workspace_dir
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.index = {}

    def run(self):
        files = []
        for root, _, filenames in os.walk(self.workspace_dir):
            for name in filenames:
                if name.endswith(".testlog"):
                    files.append(os.path.join(root, name))

        for current_index, path in enumerate(files, start=1):
            note_text = read_testlog_note_text(path)
            if note_text is not None:
                self.index[path] = note_text
            self.on_progress(current_index, len(files))

        self.on_complete(dict(self.index))


class FullTextSearchDialog(QDialog):
    resultActivated = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workspace_dir = None
        self._index = {}
        self._results = []
        self._last_query = ""
        self._theme_colors = {}

        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setModal(False)
        self.setFixedWidth(600)
        self.setObjectName("fullTextSearchDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._shadow_margin = 0 if sys.platform == "win32" else 10

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(32)
        self.shadow.setOffset(0, 12)
        self.shadow.setEnabled(self._shadow_margin > 0)
        self.setGraphicsEffect(self.shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self._shadow_margin,
            self._shadow_margin,
            self._shadow_margin,
            self._shadow_margin,
        )
        layout.setSpacing(0)

        self.frame = QWidget(self)
        self.frame.setObjectName("fullTextSearchFrame")
        layout.addWidget(self.frame)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(2, 2, 2, 2)
        frame_layout.setSpacing(0)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Sök i alla dokument...")
        frame_layout.addWidget(self.search_input)

        self.status_label = QLabel(self)
        self.status_label.setStyleSheet("padding: 8px 12px; color: #64748b; font-size: 12px;")
        self.status_label.hide()
        frame_layout.addWidget(self.status_label)

        self.results_list = QListWidget(self)
        self.results_list.setMinimumHeight(0)
        self.results_list.setMaximumHeight(360)
        self.results_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.results_list.hide()
        frame_layout.addWidget(self.results_list)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(200)
        self.search_timer.timeout.connect(self._refresh_results)

        self.search_input.textChanged.connect(lambda _text: self._schedule_search())
        self.search_input.installEventFilter(self)
        self.results_list.installEventFilter(self)
        self.results_list.itemActivated.connect(self._open_current_item)
        self.results_list.itemClicked.connect(self._open_current_item)

    def apply_theme(self, palette, theme_mode):
        if theme_mode == "dark":
            colors = {
                "dialog_bg": "#111827",
                "dialog_border": "#9ca3af",
                "dialog_text": "#e6edf3",
                "muted_text": "#9fb0c3",
                "path_text": "#7f92a8",
                "input_bg": "#111827",
                "input_border": "#334155",
                "result_hover": "#1e293b",
                "result_selected": "#334155",
                "selected_border": "#6cb6ff",
                "result_selected_text": "#f8fafc",
                "status_bg": "#162033",
                "shadow": QColor(0, 0, 0, 150),
            }
        else:
            colors = {
                "dialog_bg": "#ffffff",
                "dialog_border": "#b8c5d6",
                "dialog_text": "#17202b",
                "muted_text": "#526070",
                "path_text": "#7c8da1",
                "input_bg": "#f8fbff",
                "input_border": "#d7e0eb",
                "result_hover": "#eef4fb",
                "result_selected": "#dbeafe",
                "selected_border": "#2280e0",
                "result_selected_text": "#0f172a",
                "status_bg": "#f3f7fb",
                "shadow": QColor(15, 23, 42, 85),
            }

        self._theme_colors = colors
        self.shadow.setColor(colors["shadow"])
        self.setStyleSheet(
            f"""
            QDialog#fullTextSearchDialog {{
                background: transparent;
                border: none;
            }}
            QWidget#fullTextSearchFrame {{
                background: {colors["dialog_bg"]};
                color: {colors["dialog_text"]};
                border: 2px solid {colors["dialog_border"]};
                border-radius: 8px;
            }}
            QLineEdit {{
                background: {colors["input_bg"]};
                color: {colors["dialog_text"]};
                font-size: 15px;
                padding: 10px 12px;
                border: none;
                border-bottom: 1px solid {colors["input_border"]};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QLineEdit::placeholder {{
                color: {colors["muted_text"]};
            }}
            QListWidget {{
                background: {colors["dialog_bg"]};
                border: none;
                font-size: 13px;
                outline: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-left: 3px solid transparent;
            }}
            QListWidget::item:hover {{
                background: {colors["result_hover"]};
            }}
            QListWidget::item:selected {{
                background: {colors["result_selected"]};
                border-left: 3px solid {colors["selected_border"]};
                color: {colors["result_selected_text"]};
            }}
            """
        )
        self.status_label.setStyleSheet(
            f"padding: 8px 12px; color: {colors['muted_text']}; "
            f"background: {colors['status_bg']}; font-size: 12px;"
        )

    def open_for_workspace(self, workspace_dir, index, indexing_active=False, progress=None):
        self._workspace_dir = workspace_dir
        self._index = dict(index or {})
        parent = self.parent()
        if parent is not None and hasattr(parent, "_show_modal_overlay"):
            parent._show_modal_overlay()
        self._set_indexing_status(indexing_active, progress or (0, 0))
        self.search_input.clear()
        self.results_list.clear()
        self.results_list.hide()
        self.results_list.setFixedHeight(0)
        self._sync_dialog_height()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def hideEvent(self, event):
        super().hideEvent(event)
        parent = self.parent()
        if parent is not None and hasattr(parent, "_hide_modal_overlay"):
            parent._hide_modal_overlay()

    def update_index(self, index):
        self._index = dict(index or {})
        if self.isVisible() and self.search_input.text().strip():
            self._schedule_search()

    def update_progress(self, current, total):
        self._set_indexing_status(True, (current, total))

    def mark_index_complete(self):
        self._set_indexing_status(False, (0, 0))
        if self.isVisible() and self.search_input.text().strip():
            self._schedule_search()

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is None:
            return
        center = parent.rect().center()
        x_pos = center.x() - self.width() // 2
        y_pos = center.y() - 220
        self.move(parent.mapToGlobal(QPoint(max(24, x_pos), max(80, y_pos))))

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.close()
                return True
            if obj is self.search_input:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._activate_selected_result()
                    return True
                if event.key() == Qt.Key.Key_Down and self.results_list.isVisible() and self.results_list.count():
                    self.results_list.setFocus(Qt.FocusReason.ShortcutFocusReason)
                    self.results_list.setCurrentRow(max(0, self.results_list.currentRow()))
                    return True
            if obj is self.results_list and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_selected_result()
                return True
        return super().eventFilter(obj, event)

    def _schedule_search(self):
        self.search_timer.start()

    def _set_indexing_status(self, indexing_active, progress):
        if indexing_active:
            current, total = progress
            self.status_label.setText(f"Indexerar... ({current}/{total})")
            self.status_label.show()
            return
        self.status_label.hide()

    def _refresh_results(self):
        query = self.search_input.text().strip()
        self._last_query = query
        self.results_list.clear()
        self._results = []

        if not query:
            self.results_list.hide()
            self.results_list.setFixedHeight(0)
            self._sync_dialog_height()
            return

        self._results = build_fulltext_search_results(query, self._index)
        for result in self._results:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, result)
            item.setSizeHint(QSize(560, 74))
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, self._build_result_widget(result, query))

        self.results_list.setVisible(bool(self._results))
        if self._results:
            frame_height = self.results_list.frameWidth() * 2
            content_height = self.results_list.sizeHintForRow(0) * self.results_list.count()
            if content_height <= 0:
                content_height = 74 * self.results_list.count()
            visible_height = min(360, frame_height + content_height)
            self.results_list.setFixedHeight(visible_height)
            self.results_list.setCurrentRow(0)
        else:
            self.results_list.setFixedHeight(0)
        self._sync_dialog_height()

    def _sync_dialog_height(self):
        self.layout().activate()
        self.frame.layout().activate()
        content_height = self.frame.sizeHint().height() + (self._shadow_margin * 2)
        self.setFixedHeight(content_height)
        self.resize(self.width(), content_height)

    def _build_result_widget(self, result, query):
        container = QWidget(self.results_list)
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        display_name = Path(result["path"]).stem
        filename_label = QLabel(f"<b>{display_name}</b>", container)
        filename_label.setStyleSheet(
            f"background: transparent; color: {self._theme_colors.get('dialog_text', '#111827')};"
        )
        layout.addWidget(filename_label)

        snippet_label = QLabel(highlight_fulltext_snippet(result["snippet"], query), container)
        snippet_label.setTextFormat(Qt.TextFormat.RichText)
        snippet_label.setWordWrap(True)
        snippet_label.setStyleSheet(
            f"background: transparent; color: {self._theme_colors.get('muted_text', '#475569')};"
        )
        layout.addWidget(snippet_label)

        if self._workspace_dir:
            relative_path = os.path.relpath(result["path"], self._workspace_dir)
            relative_parent = os.path.dirname(relative_path)
            if relative_parent and relative_parent != ".":
                path_label = QLabel(relative_parent, container)
                path_label.setStyleSheet(
                    f"background: transparent; color: {self._theme_colors.get('path_text', '#94a3b8')}; font-size: 11px;"
                )
                layout.addWidget(path_label)

        return container

    def _open_current_item(self, item):
        result = item.data(Qt.ItemDataRole.UserRole)
        if not result:
            return
        self.close()
        self.resultActivated.emit(result["path"], self._last_query)

    def _activate_selected_result(self):
        if not self.results_list.isVisible() or not self.results_list.count():
            return
        current_item = self.results_list.currentItem() or self.results_list.item(0)
        if current_item is not None:
            self._open_current_item(current_item)


class RecentFileItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = {
            "bg": "#ffffff",
            "selected_bg": "#dbeafe",
            "selected_border": "#2280e0",
            "text": "#17202b",
            "selected_text": "#0f172a",
            "muted": "#64748b",
        }

    def set_colors(self, colors):
        self.colors.update(colors)

    def paint(self, painter, option, index):
        item_data = index.data(Qt.ItemDataRole.UserRole) or {}
        filename = item_data.get("filename", "")
        relative_path = item_data.get("relative_path", "")
        modified = item_data.get("modified", "")
        number = item_data.get("number")
        status = item_data.get("status")
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        painter.save()
        rect = option.rect
        if selected:
            painter.fillRect(rect, QColor(self.colors["selected_bg"]))
            painter.fillRect(rect.x(), rect.y(), 3, rect.height(), QColor(self.colors["selected_border"]))
        else:
            painter.fillRect(rect, QColor(self.colors["bg"]))

        left = rect.x() + 12
        number_width = 32 if number else 0
        text_left = left + number_width
        modified_width = 160 if modified else 0
        status_width = 18 if status else 0
        text_width = rect.width() - text_left + rect.x() - modified_width - status_width - 28
        filename_rect = rect.adjusted(text_left - rect.x(), 7, -(modified_width + status_width + 28), -26)
        path_rect = rect.adjusted(text_left - rect.x(), 29, -12, -8)
        modified_rect = rect.adjusted(rect.width() - modified_width - 16, 7, -16, -26)

        if number:
            number_rect = rect.adjusted(12, 7, -(rect.width() - number_width - 12), -26)
            painter.setPen(QColor(self.colors["muted"]))
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{number}.")

        filename_font = option.font
        filename_font.setBold(True)
        painter.setFont(filename_font)
        painter.setPen(QColor(self.colors["selected_text"] if selected else self.colors["text"]))
        painter.drawText(
            filename_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            option.fontMetrics.elidedText(filename, Qt.TextElideMode.ElideRight, text_width),
        )
        if modified:
            modified_font = option.font
            modified_font.setPointSize(max(8, modified_font.pointSize() - 1))
            painter.setFont(modified_font)
            painter.setPen(QColor(self.colors["muted"]))
            painter.drawText(
                modified_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(modified, Qt.TextElideMode.ElideRight, modified_width),
            )

        if status:
            dot_size = 10
            dot_x = modified_rect.left() - status_width + ((status_width - dot_size) // 2)
            dot_y = filename_rect.center().y() - (dot_size // 2)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QColor(WorkspaceTreeItemDelegate.STATUS_COLORS.get(status, WorkspaceTreeItemDelegate.STATUS_COLORS["todo"])))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(dot_x, dot_y, dot_size, dot_size))

        path_font = option.font
        path_font.setPointSize(max(8, path_font.pointSize() - 1))
        painter.setFont(path_font)
        painter.setPen(QColor(self.colors["muted"]))
        painter.drawText(
            path_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            option.fontMetrics.elidedText(relative_path, Qt.TextElideMode.ElideMiddle, text_width),
        )
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(540, 58)


class WorkspaceTreeItemDelegate(QStyledItemDelegate):
    STATUS_COLORS = {
        "todo": "#737278",
        "doing": "#2f5ca0",
        "done": "#306440",
    }

    def paint(self, painter, option, index):
        status = index.data(TESTLOG_STATUS_ROLE)
        if not status:
            super().paint(painter, option, index)
            return

        dot_space = 18
        item_option = QStyleOptionViewItem(option)
        item_option.rect = option.rect.adjusted(0, 0, -dot_space, 0)
        super().paint(painter, item_option, index)

        dot_size = 10
        dot_x = option.rect.right() - dot_space + ((dot_space - dot_size) // 2)
        dot_y = option.rect.center().y() - (dot_size // 2)
        dot_rect = QRect(dot_x, dot_y, dot_size, dot_size)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor(self.STATUS_COLORS.get(status, self.STATUS_COLORS["todo"])))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(dot_rect)
        painter.restore()


class RecentFilesSwitcher(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workspace_dir = None
        self._items = []

        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setModal(False)
        self.setFixedWidth(560)
        self.setObjectName("recentFilesSwitcher")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._shadow_margin = 0 if sys.platform == "win32" else 10
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(32)
        self.shadow.setOffset(0, 12)
        self.shadow.setEnabled(self._shadow_margin > 0)
        self.setGraphicsEffect(self.shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self._shadow_margin,
            self._shadow_margin,
            self._shadow_margin,
            self._shadow_margin,
        )
        layout.setSpacing(0)

        self.frame = QWidget(self)
        self.frame.setObjectName("recentFilesSwitcherFrame")
        layout.addWidget(self.frame)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(2, 2, 2, 2)
        frame_layout.setSpacing(0)

        self.search_field = QLineEdit(self)
        self.search_field.setPlaceholderText("Öppna fil...")
        frame_layout.addWidget(self.search_field)

        self.results_list = QListWidget(self)
        self.item_delegate = RecentFileItemDelegate(self.results_list)
        self.results_list.setItemDelegate(self.item_delegate)
        self.results_list.setFixedHeight(8 * 58)
        self.results_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frame_layout.addWidget(self.results_list)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self.update_list)

        self.search_field.textChanged.connect(lambda _text: self.search_timer.start())
        self.search_field.installEventFilter(self)
        self.results_list.installEventFilter(self)
        self.results_list.itemActivated.connect(lambda _item: self._open_selected())
        self.results_list.itemClicked.connect(lambda _item: self._open_selected())

        self.apply_theme(
            {
                "panel_bg": "#ffffff",
                "panel_border": "#dddddd",
                "text": "#17202b",
                "muted_text": "#64748b",
                "chrome_hover": "#dbeafe",
            },
            "light",
        )

    def apply_theme(self, palette, theme_mode):
        if theme_mode == "dark":
            colors = {
                "bg": "#111827",
                "border": "#9ca3af",
                "text": palette["text"],
                "muted": palette["muted_text"],
                "selected_bg": palette["chrome_hover"],
                "selected_border": "#6cb6ff",
                "selected_text": palette["text"],
                "input_border": "#334155",
                "shadow": QColor(0, 0, 0, 150),
            }
        else:
            colors = {
                "bg": "#ffffff",
                "border": "#94a3b8",
                "text": "#17202b",
                "muted": "#64748b",
                "selected_bg": "#dbeafe",
                "selected_border": "#2280e0",
                "selected_text": "#0f172a",
                "input_border": "#eeeeee",
                "shadow": QColor(15, 23, 42, 90),
            }

        self.item_delegate.set_colors(colors)
        self.shadow.setColor(colors["shadow"])
        self.setStyleSheet(f"""
            QDialog#recentFilesSwitcher {{
                background: transparent;
                border: none;
            }}
            QWidget#recentFilesSwitcherFrame {{
                background: {colors["bg"]};
                color: {colors["text"]};
                border: 2px solid {colors["border"]};
                border-radius: 8px;
            }}
            QLineEdit {{
                background: {colors["bg"]};
                color: {colors["text"]};
                font-size: 15px;
                padding: 10px 12px;
                border: none;
                border-bottom: 1px solid {colors["input_border"]};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QListWidget {{
                border: none;
                outline: none;
                background: {colors["bg"]};
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-left: 3px solid transparent;
            }}
            QListWidget::item:selected {{
                background: {colors["selected_bg"]};
                border-left: 3px solid {colors["selected_border"]};
                color: {colors["selected_text"]};
            }}
        """)
        self.results_list.viewport().update()

    def open_for_workspace(self, workspace_dir):
        self._workspace_dir = workspace_dir
        parent = self.parent()
        if parent is not None and hasattr(parent, "_show_modal_overlay"):
            parent._show_modal_overlay()
        self.search_timer.stop()
        self.search_field.clear()
        self.update_list()
        self.adjustSize()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_field.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is None:
            return
        center = parent.rect().center()
        x_pos = center.x() - self.width() // 2
        y_pos = center.y() - 220
        self.move(parent.mapToGlobal(QPoint(max(24, x_pos), max(80, y_pos))))

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        focused = QApplication.focusWidget()
        if focused is None or (focused is not self and not self.isAncestorOf(focused)):
            self.reject()

    def hideEvent(self, event):
        super().hideEvent(event)
        parent = self.parent()
        if parent is not None and hasattr(parent, "_hide_modal_overlay"):
            parent._hide_modal_overlay()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress and obj in (self.search_field, self.results_list):
            if self._handle_key(event):
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if not self._handle_key(event):
            super().keyPressEvent(event)

    def _handle_key(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._open_selected()
            return True
        if key == Qt.Key.Key_Down:
            self._move_selection(1)
            return True
        if key == Qt.Key.Key_Up:
            self._move_selection(-1)
            return True
        if key in (
            Qt.Key.Key_1,
            Qt.Key.Key_2,
            Qt.Key.Key_3,
            Qt.Key.Key_4,
            Qt.Key.Key_5,
            Qt.Key.Key_6,
            Qt.Key.Key_7,
            Qt.Key.Key_8,
        ):
            if not self.search_field.text():
                self._open_at_index(int(key) - int(Qt.Key.Key_1))
                return True
        return False

    def update_list(self):
        query = self.search_field.text().strip().lower()
        if query:
            items = self._workspace_matches(query)
        else:
            items = self._recent_items()

        self._items = items[:8]
        self.results_list.clear()
        for index, item_data in enumerate(self._items, start=1):
            row_data = dict(item_data)
            row_data["number"] = None if query else index
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, row_data)
            item.setSizeHint(QSize(540, 58))
            self.results_list.addItem(item)

        if self.results_list.count():
            self.results_list.setCurrentRow(0)

    def _recent_items(self):
        parent = self.parent()
        if parent is None:
            return []
        paths = parent._recent_files()
        items = []
        for path in paths:
            item_data = self._item_for_path(path)
            if item_data is not None:
                items.append(item_data)
        return items

    def _workspace_matches(self, query):
        if not self._workspace_dir or not os.path.isdir(self._workspace_dir):
            return []
        matches = []
        for root, _, filenames in os.walk(self._workspace_dir):
            for filename in filenames:
                if not filename.endswith(".testlog"):
                    continue
                if query not in Path(filename).stem.lower():
                    continue
                item_data = self._item_for_path(os.path.join(root, filename))
                if item_data is not None:
                    matches.append(item_data)
        matches.sort(key=lambda item: item["filename"].lower())
        return matches[:8]

    def _item_for_path(self, path):
        if not path or not os.path.exists(path) or not path.endswith(".testlog"):
            return None
        workspace_dir = self._workspace_dir
        if workspace_dir and os.path.commonpath([os.path.abspath(workspace_dir), os.path.abspath(path)]) == os.path.abspath(workspace_dir):
            relative_path = os.path.relpath(path, workspace_dir)
        else:
            relative_path = path
        relative_path = os.path.splitext(relative_path)[0]
        return {
            "path": path,
            "filename": Path(path).stem,
            "relative_path": relative_path,
            "modified": QFileInfo(path).lastModified().toString("yyyy-MM-dd HH:mm"),
            "status": read_testlog_status_from_archive(path),
        }

    def _move_selection(self, delta):
        count = self.results_list.count()
        if count == 0:
            return
        current_row = self.results_list.currentRow()
        if current_row < 0:
            current_row = 0
        next_row = max(0, min(count - 1, current_row + delta))
        self.results_list.setCurrentRow(next_row)

    def _open_at_index(self, index):
        if index < 0 or index >= self.results_list.count():
            return
        self.results_list.setCurrentRow(index)
        self._open_selected()

    def _open_selected(self):
        item = self.results_list.currentItem()
        if item is None:
            return
        item_data = item.data(Qt.ItemDataRole.UserRole) or {}
        path = item_data.get("path")
        if not path:
            return
        parent = self.parent()
        if parent is not None:
            if hasattr(parent, "_flush_pending_changes") and not parent._flush_pending_changes():
                return
            parent.open_testlog(path)
            parent._add_to_recent(path)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("TestLog Editor", "TestLog Editor")
        self.current_language = self.settings.value("language", self._default_language(), type=str)
        self.editor_font_size = int(self.settings.value("editor_font_size", 12))
        self.theme_mode = self.settings.value("theme_mode", "light", type=str)
        self.indent_style = self._load_indent_style()
        self.setWindowTitle("TestLog Editor")
        self.setWindowIcon(multi_icon_from_svg(APP_ICON_SVG))
        self.resize(1400, 800)

        self.current_file = None
        self.workspace_dir = None
        self.text_tool_dialog = None
        self.diff_window = None
        self.pinned_files = self._load_pinned_files()
        self.pinned_paths = set(self.pinned_files)
        self.current_status = DEFAULT_TESTLOG_STATUS
        self.sort_mode = SortMode.NAME
        self.view_mode = ViewMode.SINGLE
        self._syncing_scrollbars = False
        self._pending_preview_scroll_ratio = 0.0
        self._preview_loaded = False
        self._preview_base_url = QUrl()
        self._pending_preview_body_html = ""
        self._preview_shell_key = None
        self.fulltext_index = {}
        self.fulltext_indexing = False
        self.fulltext_index_progress = (0, 0)
        self.fulltext_index_generation = 0
        self.fulltext_index_overrides = {}
        self.fulltext_search_dialog = None
        self.recent_files_switcher = None
        self.modal_overlay = None
        self.fulltext_index_signals = FullTextIndexSignals(self)
        self.fulltext_index_signals.progress.connect(self._on_fulltext_index_progress)
        self.fulltext_index_signals.complete.connect(self._on_fulltext_index_complete)
        self.md_parser = MarkdownIt("commonmark", {"html": False}).enable("table")
        if tasklists_plugin is not None:
            self.md_parser.use(tasklists_plugin)
        self._new_session()

        self._setup_ui()
        self.set_sort(self._load_sort_mode())
        self.refresh_pinned()
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self._setup_menu()
        self._setup_toolbar()
        self.view_mode = self._load_view_mode()
        self.action_split_view.setChecked(self.view_mode == ViewMode.SPLIT)
        self.set_split_mode(self.view_mode == ViewMode.SPLIT)
        self._configure_focus_navigation()
        self._apply_theme()
        self._retranslate_ui()
        self._load_last_workspace()

    def _default_language(self):
        return "sv" if os.environ.get("LANG", "").lower().startswith("sv") else "en"

    def _tr(self, text):
        return TRANSLATIONS.get(self.current_language, {}).get(text, text)

    def _with_mnemonic(self, text):
        return f"&{text}" if text else text

    def _window_title(self, filename=None):
        base = self._tr("TestLog Editor")
        if filename:
            return f"{base} - {filename}"
        return base

    def _editor_link_base_path(self):
        if self.current_file:
            return os.path.dirname(self.current_file)
        return self.workspace_dir

    def _theme_palette(self, theme_mode=None):
        active_theme = theme_mode or self.theme_mode
        if active_theme == "dark":
            return {
                "window_bg": "#1f232a",
                "chrome_bg": "#22272e",
                "chrome_hover": "#373e47",
                "panel_bg": "#2a3038",
                "panel_border": "#4b5563",
                "text": "#e6edf3",
                "muted_text": "#adbac7",
                "link": "#93c5fd",
                "code_bg": "#313843",
                "code_border": "#4b5563",
                "code_text": "#e6edf3",
                "table_header_bg": "#313843",
                "table_alt_bg": "#2d333b",
                "blockquote_border": "#768390",
                "hr": "#444c56",
                "copy_button_bg": "#3a424d",
                "copy_button_border": "#667281",
                "scrollbar_track": "#232830",
                "scrollbar_thumb": "#566170",
                "scrollbar_thumb_hover": "#6b7788",
                "selection_bg": "#2563eb",
                "selection_text": "#ffffff",
            }
        return {
            "window_bg": "#e9edf3",
            "chrome_bg": "#dde4ec",
            "chrome_hover": "#d2dae5",
            "panel_bg": "#f8fafc",
            "panel_border": "#c5cfdb",
            "text": "#17202b",
            "muted_text": "#526070",
            "link": "#2563eb",
            "code_bg": "#eef2f7",
            "code_border": "#cfd8e3",
            "code_text": "#273444",
            "table_header_bg": "#e7edf5",
            "table_alt_bg": "#f1f5f9",
            "blockquote_border": "#94a3b8",
            "hr": "#d6dee8",
            "copy_button_bg": "#d7dee8",
            "copy_button_border": "#b4c0ce",
            "scrollbar_track": "#edf2f7",
            "scrollbar_thumb": "#b8c3d1",
            "scrollbar_thumb_hover": "#9aa9bb",
            "selection_bg": "#bfdbfe",
            "selection_text": "#17202b",
        }

    def _editor_scrollbar_stylesheet(self, theme_mode=None):
        palette = self._theme_palette(theme_mode=theme_mode)
        return f"""
        QScrollBar:vertical {{
            background: {palette["scrollbar_track"]};
            width: 12px;
            margin: 0;
            border-left: 1px solid {palette["panel_border"]};
        }}
        QScrollBar::handle:vertical {{
            background: {palette["scrollbar_thumb"]};
            min-height: 28px;
            border-radius: 6px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {palette["scrollbar_thumb_hover"]};
        }}
        QScrollBar:horizontal {{
            background: {palette["scrollbar_track"]};
            height: 12px;
            margin: 0;
            border-top: 1px solid {palette["panel_border"]};
        }}
        QScrollBar::handle:horizontal {{
            background: {palette["scrollbar_thumb"]};
            min-width: 28px;
            border-radius: 6px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {palette["scrollbar_thumb_hover"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
            border: none;
            width: 0;
            height: 0;
        }}
        """

    def _preview_scrollbar_css(self, theme_mode=None):
        palette = self._theme_palette(theme_mode=theme_mode)
        return f"""
  html {{
    scrollbar-color: {palette["scrollbar_thumb"]} {palette["scrollbar_track"]};
  }}
  ::-webkit-scrollbar {{
    width: 12px;
    height: 12px;
  }}
  ::-webkit-scrollbar-track {{
    background: {palette["scrollbar_track"]};
  }}
  ::-webkit-scrollbar-thumb {{
    background: {palette["scrollbar_thumb"]};
    border-radius: 6px;
    border: 2px solid {palette["scrollbar_track"]};
  }}
  ::-webkit-scrollbar-thumb:hover {{
    background: {palette["scrollbar_thumb_hover"]};
  }}
  ::-webkit-scrollbar-corner {{
    background: {palette["scrollbar_track"]};
  }}
"""

    def _toolbar_stylesheet(self, theme_mode=None):
        palette = self._theme_palette(theme_mode=theme_mode)
        return f"""
            QToolBar {{
                spacing: 4px;
                padding: 4px;
                background: {palette["chrome_bg"]};
                border: none;
            }}
            QToolButton {{
                min-width: 34px;
                min-height: 30px;
                font-size: 13px;
                padding: 4px 8px;
            }}
            QToolBar::separator {{
                background: {palette["panel_border"]};
                width: 1px;
                margin: 4px 8px;
            }}
        """

    def _configure_web_view_security(self, web_view, *, allow_javascript=False):
        settings = web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, allow_javascript)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        if hasattr(QWebEngineSettings.WebAttribute, "HyperlinkAuditingEnabled"):
            settings.setAttribute(QWebEngineSettings.WebAttribute.HyperlinkAuditingEnabled, False)
        if hasattr(settings, "setUnknownUrlSchemePolicy") and hasattr(QWebEngineSettings, "UnknownUrlSchemePolicy"):
            settings.setUnknownUrlSchemePolicy(
                QWebEngineSettings.UnknownUrlSchemePolicy.DisallowUnknownUrlSchemes
            )

    def _preview_toggle_button_stylesheet(self, theme_mode=None):
        palette = self._theme_palette(theme_mode=theme_mode)
        return f"""
            QToolButton {{
                background: {palette["chrome_bg"]};
                color: {palette["text"]};
                border: 1px solid {palette["panel_border"]};
                border-radius: 4px;
                padding: 2px;
            }}
            QToolButton:hover {{
                background: {palette["chrome_hover"]};
            }}
            QToolButton:checked {{
                background: {palette["copy_button_bg"]};
                border-color: {palette["copy_button_border"]};
            }}
        """

    def _sanitize_preview_url(self, value, attribute_name):
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        if not scheme:
            return value
        if scheme == "file":
            return value
        if attribute_name == "src" and value.lower().startswith("data:image/"):
            return value
        if attribute_name == "href" and scheme in {"http", "https", "ftp", "mailto"}:
            return value
        return ""

    def _sanitize_preview_html(self, html):
        html = re.sub(
            r"<\s*(script|iframe|object|embed|form|svg|math)[^>]*>.*?<\s*/\s*\1\s*>",
            "",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        html = re.sub(
            r"<\s*(meta|link|base)[^>]*>",
            "",
            html,
            flags=re.IGNORECASE,
        )
        html = re.sub(
            r"\s+on[a-z0-9_-]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
            "",
            html,
            flags=re.IGNORECASE,
        )

        def replace_url_attr(match):
            attribute_name = match.group("attr").lower()
            quote = match.group("quote")
            safe_value = self._sanitize_preview_url(match.group("value"), attribute_name)
            return f' {attribute_name}={quote}{safe_value}{quote}'

        return re.sub(
            r"\s(?P<attr>href|src)\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
            replace_url_attr,
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    def _set_language(self, language_code):
        if language_code == self.current_language:
            return
        self.current_language = language_code
        self.settings.setValue("language", language_code)
        self._retranslate_ui()

    def _new_session(self):
        self.session_dir = tempfile.mkdtemp(prefix="testlog_")
        self.images_dir = os.path.join(self.session_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)
        self._preview_loaded = False
        self._preview_base_url = QUrl()
        self._preview_shell_key = None

    def _load_last_workspace(self):
        path = self.settings.value("last_workspace", "", type=str)
        if path and os.path.isdir(path):
            self._set_workspace(path)

    def _load_pinned_files(self):
        pinned = self.settings.value("pinned_files", [])
        if isinstance(pinned, str):
            pinned = [pinned]
        return list(pinned or [])

    def _save_pinned_files(self):
        self.settings.setValue("pinned_files", self.pinned_files)

    def _recent_files(self):
        recent = self.settings.value("recent_files", [])
        if isinstance(recent, str):
            recent = [recent]
        return [path for path in list(recent or []) if os.path.exists(path)]

    def _add_to_recent(self, path):
        if not path:
            return
        recent = self._recent_files()
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        recent = [recent_path for recent_path in recent if os.path.exists(recent_path)]
        self.settings.setValue("recent_files", recent[:8])

    def _load_sort_mode(self):
        saved_sort = self.settings.value("sort_mode", SortMode.NAME.value, type=str)
        try:
            return SortMode(saved_sort)
        except ValueError:
            return SortMode.NAME

    def _load_view_mode(self):
        saved_mode = self.settings.value("view_mode", ViewMode.SINGLE.value, type=str)
        try:
            return ViewMode(saved_mode)
        except ValueError:
            return ViewMode.SINGLE

    def _load_indent_style(self):
        saved_style = self.settings.value("indent_style", DEFAULT_INDENT_STYLE, type=str)
        return saved_style if saved_style in INDENT_STYLE_TEXT else DEFAULT_INDENT_STYLE

    def _set_indent_style(self, style):
        if style not in INDENT_STYLE_TEXT:
            style = DEFAULT_INDENT_STYLE
        if style == self.indent_style:
            return
        self.indent_style = style
        self.settings.setValue("indent_style", style)
        if hasattr(self, "editor"):
            self.editor.set_indent_text(INDENT_STYLE_TEXT[style])
        self._retranslate_ui()

    def _apply_editor_font(self):
        if not hasattr(self, "editor"):
            return
        if sys.platform == "win32":
            preferred_families = ["Cascadia Mono", "Consolas", "Courier New"]
        elif sys.platform == "darwin":
            preferred_families = ["SF Mono", "Menlo", "Monaco"]
        else:
            preferred_families = ["Noto Sans Mono", "DejaVu Sans Mono", "Liberation Mono", "Monospace"]

        available_families = set(QFontDatabase.families())
        chosen_family = next((family for family in preferred_families if family in available_families), "Monospace")

        font = QFont(chosen_family)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(self.editor_font_size)
        self.editor.setFont(font)
        if self.diff_window is not None:
            self.diff_window.apply_editor_font(font)

    def _set_editor_font_size(self, size):
        if size == self.editor_font_size:
            return
        self.editor_font_size = size
        self.settings.setValue("editor_font_size", size)
        self._apply_editor_font()
        self._retranslate_ui()

    def _increase_editor_font_size(self):
        self._step_editor_font_size(1)

    def _decrease_editor_font_size(self):
        self._step_editor_font_size(-1)

    def _step_editor_font_size(self, direction):
        sizes = sorted(self.font_size_actions)
        if not sizes:
            return
        if direction > 0:
            next_size = next((size for size in sizes if size > self.editor_font_size), sizes[-1])
        else:
            next_size = next((size for size in reversed(sizes) if size < self.editor_font_size), sizes[0])
        self._set_editor_font_size(next_size)

    def _set_theme_mode(self, mode):
        if mode == self.theme_mode:
            return
        self.theme_mode = mode
        self.settings.setValue("theme_mode", mode)
        self._apply_theme()
        self.update_preview()
        self._retranslate_ui()

    def _apply_theme(self):
        palette = self._theme_palette()
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                background: {palette["window_bg"]};
                color: {palette["text"]};
            }}
            QLabel {{
                background: transparent;
                color: {palette["text"]};
            }}
            QMenuBar, QMenuBar::item, QMenu, QStatusBar, QToolBar {{
                background: {palette["chrome_bg"]};
                color: {palette["text"]};
            }}
            QMenu::item:selected, QMenuBar::item:selected {{
                background: {palette["chrome_hover"]};
            }}
            QTreeView, QListWidget, QListView, QLineEdit, QTextEdit, QPlainTextEdit {{
                background: {palette["panel_bg"]};
                color: {palette["text"]};
                border: 1px solid {palette["panel_border"]};
            }}
            QTreeView::item:selected, QListView::item:selected {{
                background: {palette["chrome_hover"]};
                color: {palette["text"]};
            }}
            QLineEdit {{
                selection-background-color: {palette["selection_bg"]};
                selection-color: {palette["selection_text"]};
                padding: 4px 6px;
            }}
            QPushButton {{
                background: {palette["chrome_bg"]};
                color: {palette["text"]};
                border: 1px solid {palette["panel_border"]};
                padding: 4px 8px;
            }}
            QPushButton:hover {{ background: {palette["chrome_hover"]}; }}
            QSplitter::handle {{
                background: {palette["chrome_bg"]};
            }}
            QSplitter::handle:hover {{
                background: {palette["chrome_hover"]};
            }}
            {self._editor_scrollbar_stylesheet()}
            """
        )
        if hasattr(self, "editor"):
            self._apply_editor_stylesheet()
        if self.diff_window is not None:
            self.diff_window.apply_theme(palette)
        if hasattr(self, "preview"):
            self.preview.setStyleSheet(
                f"background: {palette['panel_bg']}; border: 1px solid {palette['panel_border']};"
            )
            self.preview.page().setBackgroundColor(QColor(palette["panel_bg"]))
        if hasattr(self, "toggle_btn"):
            self.toggle_btn.setStyleSheet(self._preview_toggle_button_stylesheet())
        if hasattr(self, "toolbar"):
            self.toolbar.setStyleSheet(self._toolbar_stylesheet())
        if hasattr(self, "editor_highlighter"):
            self.editor_highlighter.set_theme_mode(self.theme_mode)
        if self.fulltext_search_dialog is not None:
            self.fulltext_search_dialog.apply_theme(palette, self.theme_mode)
        if self.recent_files_switcher is not None:
            self.recent_files_switcher.apply_theme(palette, self.theme_mode)

    def _editor_selection_background_color(self):
        palette = self._theme_palette()
        if hasattr(self, "find_bar") and self.find_bar.has_active_match():
            return "#A57538" if self.theme_mode == "dark" else "#f59e0b"
        return palette["selection_bg"]

    def _editor_selection_text_color(self):
        palette = self._theme_palette()
        if hasattr(self, "find_bar") and self.find_bar.has_active_match():
            return palette["text"]
        return palette["selection_text"]

    def _apply_editor_stylesheet(self):
        if not hasattr(self, "editor"):
            return
        palette = self._theme_palette()
        selection_bg = self._editor_selection_background_color()
        selection_text = self._editor_selection_text_color()
        self.editor.setStyleSheet(
            f"""
            QTextEdit {{
                background: {palette['panel_bg']};
                color: {palette['text']};
                border: 1px solid {palette['panel_border']};
                selection-background-color: {selection_bg};
                selection-color: {selection_text};
            }}
            {self._editor_scrollbar_stylesheet()}
            """
        )

    def _show_modal_overlay(self):
        if self.modal_overlay is None:
            self.modal_overlay = QWidget(self)
            self.modal_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.modal_overlay.setGeometry(self.rect())
        self.modal_overlay.setStyleSheet("background: rgba(0, 0, 0, 120);")
        self.modal_overlay.show()
        self.modal_overlay.raise_()

    def _hide_modal_overlay(self):
        if self.modal_overlay is not None:
            self.modal_overlay.hide()

    def _set_workspace(self, path):
        if path != self.workspace_dir and not self._flush_pending_changes():
            return
        self.workspace_dir = path
        self.fs_model.setRootPath(path)
        if self._set_tree_workspace_root():
            self.tree.update()
            self.setWindowTitle(self._window_title(os.path.basename(path)))
            self.statusBar().showMessage(self._tr("Workspace opened: {path}").format(path=path), 3000)
            self.settings.setValue("last_workspace", path)
            self._start_fulltext_indexing()
            self._open_most_recent_testlog()

    def _set_tree_workspace_root(self):
        if not self.workspace_dir:
            return False

        source_root = self.fs_model.index(self.workspace_dir)
        if not source_root.isValid():
            return False

        proxy_root = self.fs_proxy_model.mapFromSource(source_root)
        if not proxy_root.isValid():
            return False

        if self.tree.rootIndex() != proxy_root:
            self.tree.setRootIndex(proxy_root)
        return True

    def _setup_menu(self):
        menubar = self.menuBar()
        self.file_menu = menubar.addMenu("")
        self.edit_menu = menubar.addMenu("")
        self.transform_menu = menubar.addMenu("")
        self.format_menu = menubar.addMenu("")
        self.insert_menu = menubar.addMenu("")
        self.view_menu = menubar.addMenu("")
        self.tools_menu = menubar.addMenu("")
        self.language_menu = menubar.addMenu("")

        self.new_action = QAction(self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.triggered.connect(self.new_file)

        self.open_action = QAction(self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_file)

        self.undo_action = QAction(self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.editor.undo)
        self.redo_action = QAction(self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.editor.redo)
        self.copy_line_action = QAction(self)
        self.copy_line_action.triggered.connect(self.editor.copy_line)
        self.cut_line_action = QAction(self)
        self.cut_line_action.triggered.connect(self.editor.cut_line)
        self.duplicate_lines_action = QAction(self)
        self.duplicate_lines_action.setShortcut("Ctrl+Shift+D")
        self.duplicate_lines_action.triggered.connect(self.editor.duplicate_lines_down)
        self.move_lines_up_action = QAction(self)
        self.move_lines_up_action.setShortcut("Alt+Up")
        self.move_lines_up_action.triggered.connect(self.editor.move_lines_up)
        self.move_lines_down_action = QAction(self)
        self.move_lines_down_action.setShortcut("Alt+Down")
        self.move_lines_down_action.triggered.connect(self.editor.move_lines_down)
        self.bold_menu_action = QAction(self)
        self.bold_menu_action.setShortcut("Ctrl+B")
        self.bold_menu_action.triggered.connect(self.editor.format_bold)
        self.italic_menu_action = QAction(self)
        self.italic_menu_action.setShortcut("Ctrl+I")
        self.italic_menu_action.triggered.connect(self.editor.format_italic)
        self.underline_menu_action = QAction(self)
        self.underline_menu_action.triggered.connect(self.editor.format_underline)
        self.inline_code_menu_action = QAction(self)
        self.inline_code_menu_action.triggered.connect(self.editor.format_inline_code)
        self.code_block_menu_action = QAction(self)
        self.code_block_menu_action.setShortcut("Ctrl+Shift+K")
        self.code_block_menu_action.triggered.connect(self.editor.format_code_block)
        self.heading1_action = QAction(self)
        self.heading1_action.setShortcut("Ctrl+1")
        self.heading1_action.triggered.connect(lambda: self._insert_line_prefix("# "))
        self.heading2_action = QAction(self)
        self.heading2_action.setShortcut("Ctrl+2")
        self.heading2_action.triggered.connect(lambda: self._insert_line_prefix("## "))
        self.heading3_action = QAction(self)
        self.heading3_action.setShortcut("Ctrl+3")
        self.heading3_action.triggered.connect(lambda: self._insert_line_prefix("### "))
        self.heading4_action = QAction(self)
        self.heading4_action.setShortcut("Ctrl+4")
        self.heading4_action.triggered.connect(lambda: self._insert_line_prefix("#### "))
        self.bullet_list_action = QAction(self)
        self.bullet_list_action.setShortcut("Ctrl+Shift+L")
        self.bullet_list_action.triggered.connect(lambda: self._insert_line_prefix("- "))
        self.numbered_list_action = QAction(self)
        self.numbered_list_action.setShortcut("Ctrl+Shift+O")
        self.numbered_list_action.triggered.connect(lambda: self._insert_line_prefix("1. "))
        self.blockquote_action = QAction(self)
        self.blockquote_action.triggered.connect(lambda: self._insert_line_prefix("> "))
        self.horizontal_rule_action = QAction(self)
        self.horizontal_rule_action.triggered.connect(self._insert_horizontal_rule)
        self.date_menu_action = QAction(self)
        self.date_menu_action.setShortcut("Ctrl+Alt+D")
        self.date_menu_action.triggered.connect(self.editor.insert_current_date)
        self.time_menu_action = QAction(self)
        self.time_menu_action.triggered.connect(self.editor.insert_current_time)
        self.date_time_menu_action = QAction(self)
        self.date_time_menu_action.triggered.connect(self.editor.insert_current_date_time)
        self.link_menu_action = QAction(self)
        self.link_menu_action.triggered.connect(self.insert_link)
        self.image_menu_action = QAction(self)
        self.image_menu_action.triggered.connect(self.insert_image)
        self.base64_encode_menu_action = QAction(self)
        self.base64_encode_menu_action.triggered.connect(self._transform_editor_base64_encode)
        self.base64_decode_menu_action = QAction(self)
        self.base64_decode_menu_action.triggered.connect(self._transform_editor_base64_decode)
        self.url_encode_menu_action = QAction(self)
        self.url_encode_menu_action.triggered.connect(self._transform_editor_url_encode)
        self.url_decode_menu_action = QAction(self)
        self.url_decode_menu_action.triggered.connect(self._transform_editor_url_decode)
        self.format_json_menu_action = QAction(self)
        self.format_json_menu_action.triggered.connect(self._transform_editor_format_json)
        self.guess_markdown_menu_action = QAction(self)
        self.guess_markdown_menu_action.triggered.connect(self._transform_editor_guess_markdown)
        self.text_tool_action = QAction(self)
        self.text_tool_action.triggered.connect(self.open_text_tool)
        self.diff_action = QAction(self)
        self.diff_action.triggered.connect(self.open_diff_window)
        self.send_to_diff_a_action = QAction(self)
        self.send_to_diff_a_action.triggered.connect(lambda: self.send_editor_text_to_diff("a"))
        self.send_to_diff_b_action = QAction(self)
        self.send_to_diff_b_action.triggered.connect(lambda: self.send_editor_text_to_diff("b"))

        self.font_size_menu = QMenu(self)
        self.font_size_group = QActionGroup(self)
        self.font_size_group.setExclusive(True)
        self.font_size_actions = {}
        for size in (10, 11, 12, 13, 14):
            action = QAction(str(size), self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, s=size: self._set_editor_font_size(s))
            self.font_size_group.addAction(action)
            self.font_size_menu.addAction(action)
            self.font_size_actions[size] = action

        self.indent_style_menu = QMenu(self)
        self.indent_style_group = QActionGroup(self)
        self.indent_style_group.setExclusive(True)
        self.indent_style_actions = {}
        for style in ("spaces2", "spaces4", "tabs"):
            action = QAction(self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, s=style: self._set_indent_style(s))
            self.indent_style_group.addAction(action)
            self.indent_style_menu.addAction(action)
            self.indent_style_actions[style] = action

        self.light_mode_action = QAction(self)
        self.light_mode_action.setCheckable(True)
        self.light_mode_action.triggered.connect(lambda: self._set_theme_mode("light"))
        self.dark_mode_action = QAction(self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.triggered.connect(lambda: self._set_theme_mode("dark"))
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_group.addAction(self.light_mode_action)
        self.theme_group.addAction(self.dark_mode_action)
        self.action_split_view = QAction(self)
        self.action_split_view.setCheckable(True)
        self.action_split_view.setShortcut("Ctrl+Shift+E")
        self.action_split_view.triggered.connect(self.set_split_mode)

        self.open_workspace_action = QAction(self)
        self.open_workspace_action.triggered.connect(self.open_workspace)

        self.save_action = QAction(self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_file)

        self.save_as_action = QAction(self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_file_as)

        self.export_md_action = QAction(self)
        self.export_md_action.triggered.connect(lambda: self.export_text_copy("md"))

        self.export_txt_action = QAction(self)
        self.export_txt_action.triggered.connect(lambda: self.export_text_copy("txt"))

        self.export_pdf_action = QAction(self)
        self.export_pdf_action.triggered.connect(self.export_pdf)
        self.quit_action = QAction(self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.triggered.connect(self.close)

        self.file_menu.addAction(self.new_action)
        self.file_menu.addAction(self.open_action)
        self.file_menu.addAction(self.open_workspace_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.save_action)
        self.file_menu.addAction(self.save_as_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.export_md_action)
        self.file_menu.addAction(self.export_txt_action)
        self.file_menu.addAction(self.export_pdf_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.quit_action)

        self.edit_menu.addAction(self.undo_action)
        self.edit_menu.addAction(self.redo_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.copy_line_action)
        self.edit_menu.addAction(self.cut_line_action)
        self.edit_menu.addAction(self.duplicate_lines_action)
        self.edit_menu.addAction(self.move_lines_up_action)
        self.edit_menu.addAction(self.move_lines_down_action)

        self.transform_menu.addAction(self.base64_encode_menu_action)
        self.transform_menu.addAction(self.base64_decode_menu_action)
        self.transform_menu.addSeparator()
        self.transform_menu.addAction(self.url_encode_menu_action)
        self.transform_menu.addAction(self.url_decode_menu_action)
        self.transform_menu.addSeparator()
        self.transform_menu.addAction(self.format_json_menu_action)
        self.transform_menu.addAction(self.guess_markdown_menu_action)

        self.format_menu.addAction(self.bold_menu_action)
        self.format_menu.addAction(self.italic_menu_action)
        self.format_menu.addAction(self.underline_menu_action)
        self.format_menu.addAction(self.inline_code_menu_action)
        self.format_menu.addAction(self.code_block_menu_action)
        self.format_menu.addSeparator()
        self.format_menu.addAction(self.heading1_action)
        self.format_menu.addAction(self.heading2_action)
        self.format_menu.addAction(self.heading3_action)
        self.format_menu.addAction(self.heading4_action)
        self.format_menu.addSeparator()
        self.format_menu.addAction(self.bullet_list_action)
        self.format_menu.addAction(self.numbered_list_action)
        self.format_menu.addAction(self.blockquote_action)
        self.format_menu.addAction(self.horizontal_rule_action)
        self.insert_menu.addAction(self.date_menu_action)
        self.insert_menu.addAction(self.time_menu_action)
        self.insert_menu.addAction(self.date_time_menu_action)
        self.insert_menu.addSeparator()
        self.insert_menu.addAction(self.link_menu_action)
        self.insert_menu.addAction(self.image_menu_action)

        self.view_menu.addAction(self.action_split_view)
        self.view_menu.addSeparator()
        self.view_menu.addMenu(self.font_size_menu)
        self.view_menu.addMenu(self.indent_style_menu)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.light_mode_action)
        self.view_menu.addAction(self.dark_mode_action)

        self.tools_menu.addAction(self.text_tool_action)
        self.tools_menu.addAction(self.diff_action)
        self.tools_menu.addAction(self.send_to_diff_a_action)
        self.tools_menu.addAction(self.send_to_diff_b_action)

        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)
        self.english_action = QAction(self)
        self.english_action.setCheckable(True)
        self.english_action.triggered.connect(lambda: self._set_language("en"))
        self.swedish_action = QAction(self)
        self.swedish_action.setCheckable(True)
        self.swedish_action.triggered.connect(lambda: self._set_language("sv"))
        self.language_action_group.addAction(self.english_action)
        self.language_action_group.addAction(self.swedish_action)
        self.language_menu.addAction(self.english_action)
        self.language_menu.addAction(self.swedish_action)

    def _setup_toolbar(self):
        self.toolbar = QToolBar("Formatting")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(self.toolbar.iconSize().expandedTo(self.toolbar.iconSize()))
        self.toolbar.setStyleSheet(self._toolbar_stylesheet())
        self.addToolBar(self.toolbar)

        self.toolbar_bold_action = QAction(self)
        self.toolbar_bold_action.triggered.connect(self.editor.format_bold)
        self.toolbar.addAction(self.toolbar_bold_action)

        self.toolbar_italic_action = QAction(self)
        self.toolbar_italic_action.triggered.connect(self.editor.format_italic)
        self.toolbar.addAction(self.toolbar_italic_action)

        self.toolbar_underline_action = QAction(self)
        self.toolbar_underline_action.triggered.connect(self.editor.format_underline)
        self.toolbar.addAction(self.toolbar_underline_action)

        self.toolbar_h1_action = QAction(self)
        self.toolbar_h1_action.triggered.connect(lambda: self._insert_line_prefix("# "))
        self.toolbar.addAction(self.toolbar_h1_action)

        self.toolbar_h2_action = QAction(self)
        self.toolbar_h2_action.triggered.connect(lambda: self._insert_line_prefix("## "))
        self.toolbar.addAction(self.toolbar_h2_action)

        self.toolbar_h3_action = QAction(self)
        self.toolbar_h3_action.triggered.connect(lambda: self._insert_line_prefix("### "))
        self.toolbar.addAction(self.toolbar_h3_action)

        self.toolbar_h4_action = QAction(self)
        self.toolbar_h4_action.triggered.connect(lambda: self._insert_line_prefix("#### "))
        self.toolbar.addAction(self.toolbar_h4_action)

        self.toolbar.addSeparator()

        self.toolbar_bullet_action = QAction(self)
        self.toolbar_bullet_action.triggered.connect(lambda: self._insert_line_prefix("- "))
        self.toolbar.addAction(self.toolbar_bullet_action)

        self.toolbar_numbered_action = QAction(self)
        self.toolbar_numbered_action.triggered.connect(lambda: self._insert_line_prefix("1. "))
        self.toolbar.addAction(self.toolbar_numbered_action)

        self.toolbar.addSeparator()

        self.toolbar_hr_action = QAction(self)
        self.toolbar_hr_action.triggered.connect(self._insert_horizontal_rule)
        self.toolbar.addAction(self.toolbar_hr_action)

        self.toolbar.addSeparator()

        self.toolbar_text_tool_action = QAction(self)
        self.toolbar_text_tool_action.triggered.connect(self.open_text_tool)
        self.toolbar.addAction(self.toolbar_text_tool_action)

        self.toolbar_diff_action = QAction(self)
        self.toolbar_diff_action.triggered.connect(self.open_diff_window)
        self.toolbar.addAction(self.toolbar_diff_action)

        self.toolbar.addSeparator()

        self.status_combo = QComboBox()
        self.status_combo.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.status_combo.setFixedWidth(120)
        for status in TESTLOG_STATUS_OPTIONS:
            self.status_combo.addItem(TESTLOG_STATUS_LABELS[status], status)
        self.status_combo.currentIndexChanged.connect(self._on_status_combo_changed)
        self.toolbar.addWidget(self.status_combo)
        self._set_status_combo(self.current_status)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setIconSize(QSize(32, 24))
        self.toggle_btn.setFixedSize(44, 32)
        self.toggle_btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.toggle_btn.setStyleSheet(self._preview_toggle_button_stylesheet())
        self.toggle_btn.clicked.connect(lambda checked=False: self.toggle_editor_preview())
        self.toolbar.addWidget(self.toggle_btn)

        self.editor_preview_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        self.editor_preview_shortcut.activated.connect(self.toggle_editor_preview)
        self.editor_preview_f11_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        self.editor_preview_f11_shortcut.activated.connect(self.toggle_editor_preview)
        self.increase_font_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        self.increase_font_shortcut.activated.connect(self._increase_editor_font_size)
        self.increase_font_equal_shortcut = QShortcut(QKeySequence("Ctrl+="), self)
        self.increase_font_equal_shortcut.activated.connect(self._increase_editor_font_size)
        self.decrease_font_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        self.decrease_font_shortcut.activated.connect(self._decrease_editor_font_size)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F"), self)
        self.search_shortcut.activated.connect(self.open_fulltext_search)
        self.recent_switcher_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.recent_switcher_shortcut.activated.connect(self.open_recent_switcher)

    def _set_status_combo(self, status):
        if not hasattr(self, "status_combo"):
            return
        normalized_status = normalize_testlog_status(status)
        combo_index = self.status_combo.findData(normalized_status)
        if combo_index < 0:
            combo_index = self.status_combo.findData(DEFAULT_TESTLOG_STATUS)
        self.status_combo.blockSignals(True)
        self.status_combo.setCurrentIndex(combo_index)
        self.status_combo.blockSignals(False)

    def _sync_status_from_editor(self):
        status = get_testlog_status(self.editor.toPlainText())
        if status == self.current_status:
            return
        self.current_status = status
        self._set_status_combo(status)

    def _replace_editor_text_preserving_cursor(self, text):
        cursor = self.editor.textCursor()
        cursor_position = min(cursor.position(), len(text))
        self.editor.setPlainText(text)
        cursor.setPosition(cursor_position)
        self.editor.setTextCursor(cursor)

    def _on_status_combo_changed(self):
        status = self.status_combo.currentData() or DEFAULT_TESTLOG_STATUS
        if status == self.current_status and get_testlog_status(self.editor.toPlainText()) == status:
            return

        self.current_status = status
        updated_text = set_testlog_status(self.editor.toPlainText(), status)
        if updated_text != self.editor.toPlainText():
            self._replace_editor_text_preserving_cursor(updated_text)
            self.editor.document().setModified(True)
            self.timer.start()
            self.autosave_timer.start()

    def _retranslate_ui(self):
        self.file_menu.setTitle(self._with_mnemonic(self._tr("File")))
        self.edit_menu.setTitle(self._with_mnemonic(self._tr("Edit")))
        self.transform_menu.setTitle(self._with_mnemonic(self._tr("Transform")))
        self.format_menu.setTitle(self._with_mnemonic(self._tr("Format")))
        self.insert_menu.setTitle(self._with_mnemonic(self._tr("Insert")))
        self.view_menu.setTitle(self._with_mnemonic(self._tr("View")))
        self.tools_menu.setTitle(self._with_mnemonic(self._tr("Tools")))
        self.language_menu.setTitle(self._with_mnemonic(self._tr("Language")))

        self.new_action.setText(self._tr("New"))
        self.open_action.setText(self._tr("Open..."))
        self.open_workspace_action.setText(self._tr("Open Workspace..."))
        self.save_action.setText(self._tr("Save"))
        self.save_as_action.setText(self._tr("Save As..."))
        self.export_md_action.setText(self._tr("Export as Markdown..."))
        self.export_txt_action.setText(self._tr("Export as Text..."))
        self.export_pdf_action.setText(self._tr("Export as PDF..."))
        self.quit_action.setText(self._tr("Quit"))

        self.undo_action.setText(self._tr("Undo"))
        self.redo_action.setText(self._tr("Redo"))
        self.copy_line_action.setText(self._tr("Copy Line"))
        self.cut_line_action.setText(self._tr("Cut Line"))
        self.duplicate_lines_action.setText(self._tr("Duplicate Line/Block"))
        self.move_lines_up_action.setText(self._tr("Move Line/Block Up"))
        self.move_lines_down_action.setText(self._tr("Move Line/Block Down"))
        self.base64_encode_menu_action.setText(self._tr("To Base64"))
        self.base64_decode_menu_action.setText(self._tr("From Base64"))
        self.url_encode_menu_action.setText(self._tr("To URL"))
        self.url_decode_menu_action.setText(self._tr("From URL"))
        self.format_json_menu_action.setText(self._tr("Format JSON"))
        self.guess_markdown_menu_action.setText(self._tr("Guess Markdown From Plain Text"))
        self.text_tool_action.setText(self._tr("Text Tool"))
        self.diff_action.setText(self._tr("Diff..."))
        self.send_to_diff_a_action.setText(self._tr("Send Current Text to Diff A"))
        self.send_to_diff_b_action.setText(self._tr("Send Current Text to Diff B"))

        self.bold_menu_action.setText(self._tr("Bold"))
        self.italic_menu_action.setText(self._tr("Italic"))
        self.underline_menu_action.setText(self._tr("Underline"))
        self.inline_code_menu_action.setText(self._tr("Inline Code"))
        self.code_block_menu_action.setText(self._tr("Code Block"))
        self.heading1_action.setText(self._tr("Heading 1"))
        self.heading2_action.setText(self._tr("Heading 2"))
        self.heading3_action.setText(self._tr("Heading 3"))
        self.heading4_action.setText(self._tr("Heading 4"))
        self.bullet_list_action.setText(self._tr("Bullet List"))
        self.numbered_list_action.setText(self._tr("Numbered List"))
        self.blockquote_action.setText(self._tr("Blockquote"))
        self.horizontal_rule_action.setText(self._tr("Horizontal Rule"))
        self.date_menu_action.setText(self._tr("Insert Date"))
        self.time_menu_action.setText(self._tr("Insert Time"))
        self.date_time_menu_action.setText(self._tr("Insert Date & Time"))
        self.link_menu_action.setText(self._tr("Insert Link..."))
        self.image_menu_action.setText(self._tr("Insert Image..."))
        self.font_size_menu.setTitle(self._tr("Font Size"))
        self.indent_style_menu.setTitle(self._tr("Indentation"))
        self.indent_style_actions["spaces2"].setText(self._tr("2 Spaces"))
        self.indent_style_actions["spaces4"].setText(self._tr("4 Spaces"))
        self.indent_style_actions["tabs"].setText(self._tr("Tabs"))
        self.action_split_view.setText(self._tr("Split View"))
        self.light_mode_action.setText(self._tr("Light Mode"))
        self.dark_mode_action.setText(self._tr("Dark Mode"))
        for size, action in self.font_size_actions.items():
            action.setChecked(size == self.editor_font_size)
        for style, action in self.indent_style_actions.items():
            action.setChecked(style == self.indent_style)
        self.light_mode_action.setChecked(self.theme_mode == "light")
        self.dark_mode_action.setChecked(self.theme_mode == "dark")

        self.english_action.setText(self._tr("English"))
        self.swedish_action.setText(self._tr("Swedish"))
        self.english_action.setChecked(self.current_language == "en")
        self.swedish_action.setChecked(self.current_language == "sv")

        self.toolbar.setWindowTitle(self._tr("Formatting"))
        self.toolbar_bold_action.setText("B")
        self.toolbar_bold_action.setToolTip(self._tr("Bold (Ctrl+B)"))
        self.toolbar_italic_action.setText("I")
        self.toolbar_italic_action.setToolTip(self._tr("Italic (Ctrl+I)"))
        self.toolbar_underline_action.setText("U")
        self.toolbar_underline_action.setToolTip(self._tr("Underline tooltip"))
        self.toolbar_h1_action.setText("H1")
        self.toolbar_h1_action.setToolTip(self._tr("Heading 1 (Ctrl+1)"))
        self.toolbar_h2_action.setText("H2")
        self.toolbar_h2_action.setToolTip(self._tr("Heading 2 (Ctrl+2)"))
        self.toolbar_h3_action.setText("H3")
        self.toolbar_h3_action.setToolTip(self._tr("Heading 3 (Ctrl+3)"))
        self.toolbar_h4_action.setText("H4")
        self.toolbar_h4_action.setToolTip(self._tr("Heading 4 (Ctrl+4)"))
        self.toolbar_bullet_action.setText("UL")
        self.toolbar_bullet_action.setToolTip(self._tr("Bullet List"))
        self.toolbar_numbered_action.setText("1.")
        self.toolbar_numbered_action.setToolTip(self._tr("Numbered List"))
        self.toolbar_hr_action.setText("─")
        self.toolbar_hr_action.setToolTip(self._tr("Horizontal Rule"))
        self.toolbar_text_tool_action.setText(self._tr("Text Tool"))
        self.toolbar_text_tool_action.setToolTip(self._tr("Text Tool"))
        self.toolbar_diff_action.setText(self._tr("Diff"))
        self.toolbar_diff_action.setToolTip(self._tr("Diff..."))
        for index in range(self.status_combo.count()):
            status = self.status_combo.itemData(index)
            self.status_combo.setItemText(index, self._tr(TESTLOG_STATUS_LABELS[status]))
        self.status_combo.setToolTip(self._tr("Status"))
        self.toggle_btn.setToolTip(self._tr("Toggle editor/preview (Ctrl+E or F11)"))

        self.btn_new_file.setText(self._tr("+ New File"))
        self.btn_new_folder.setText(self._tr("+ Folder"))
        self.btn_sort.setToolTip(self._tr("Sorting"))
        self.action_sort_name.setText(self._tr("Name (A-Z)"))
        self.action_sort_modified.setText(self._tr("Last Modified"))
        self.action_sort_created.setText(self._tr("Created"))
        self._update_sort_button()
        self.sidebar_search.setPlaceholderText(self._tr("Search Files..."))
        self.find_bar.retranslate_ui()
        self.editor.setPlaceholderText(self._tr("Write Markdown here..."))
        self._update_editor_counts()
        self.refresh_pinned()

        title_suffix = os.path.basename(self.current_file) if self.current_file else None
        self.setWindowTitle(self._window_title(title_suffix))
        if hasattr(self, "text_tool_dialog") and self.text_tool_dialog is not None:
            self.text_tool_dialog.retranslate_ui()
        if self.diff_window is not None:
            self.diff_window.retranslate_ui()

    def _setup_ui(self):
        # Yttre splitter: sidebar | höger
        self.outer_splitter = QSplitter(Qt.Horizontal)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(4, 4, 4, 0)
        sidebar_layout.setSpacing(4)

        self.sidebar_search = QLineEdit()
        self.sidebar_search.setPlaceholderText(self._tr("Search Files..."))
        self.sidebar_search.setClearButtonEnabled(True)
        self.sidebar_search.textChanged.connect(lambda text: self._schedule_sidebar_search(text))
        sidebar_layout.addWidget(self.sidebar_search)

        btn_row = QHBoxLayout()
        self.btn_new_file = QPushButton("+ Ny fil")
        self.btn_new_file.clicked.connect(self.new_file_in_workspace)
        self.btn_new_folder = QPushButton("+ Mapp")
        self.btn_new_folder.clicked.connect(self.new_folder_in_workspace)
        self.btn_sort = QToolButton()
        self.btn_sort.setToolTip(self._tr("Sorting"))
        self.btn_sort.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_sort.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        sort_menu = QMenu(self.btn_sort)
        self.action_sort_name = QAction("Namn (A-Ö)", self)
        self.action_sort_name.setCheckable(True)
        self.action_sort_modified = QAction("Senast ändrad", self)
        self.action_sort_modified.setCheckable(True)
        self.action_sort_created = QAction("Skapad", self)
        self.action_sort_created.setCheckable(True)

        self.sort_group = QActionGroup(self)
        self.sort_group.addAction(self.action_sort_name)
        self.sort_group.addAction(self.action_sort_modified)
        self.sort_group.addAction(self.action_sort_created)
        self.sort_group.setExclusive(True)

        self.action_sort_name.setChecked(True)
        sort_menu.addAction(self.action_sort_name)
        sort_menu.addAction(self.action_sort_modified)
        sort_menu.addAction(self.action_sort_created)
        self.btn_sort.setMenu(sort_menu)

        self.action_sort_name.triggered.connect(lambda checked=False: self.set_sort(SortMode.NAME))
        self.action_sort_modified.triggered.connect(lambda checked=False: self.set_sort(SortMode.MODIFIED))
        self.action_sort_created.triggered.connect(lambda checked=False: self.set_sort(SortMode.CREATED))

        btn_row.addWidget(self.btn_new_file)
        btn_row.addWidget(self.btn_new_folder)
        btn_row.addWidget(self.btn_sort)
        sidebar_layout.addLayout(btn_row)

        folder_icon = icon_from_svg(FOLDER_ICON_SVG, size=20)
        folder_pinned_icon = icon_from_svg(FOLDER_PINNED_ICON_SVG, size=20)
        testlog_icon = icon_from_svg(TESTLOG_ICON_SVG, size=20)
        testlog_pinned_icon = icon_from_svg(TESTLOG_PINNED_ICON_SVG, size=20)
        file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        self.fs_model = WorkspaceFileSystemModel(
            self.pinned_paths,
            folder_icon=folder_icon,
            folder_pinned_icon=folder_pinned_icon,
            testlog_icon=testlog_icon,
            testlog_pinned_icon=testlog_pinned_icon,
            file_icon=file_icon,
        )
        self.fs_proxy_model = WorkspaceSortProxyModel(self.fs_model, self.pinned_paths, self)
        self.fs_model.setNameFilters(["*.testlog"])
        self.fs_model.setNameFilterDisables(True)  # Visar mappar, gråar ut andra filer
        self.fs_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

        self.tree = QTreeView()
        self.tree.setModel(self.fs_proxy_model)
        self.tree.setItemDelegate(WorkspaceTreeItemDelegate(self.tree))
        self.tree.setHeaderHidden(True)
        self.tree.setSortingEnabled(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Dölj kolumner utom namn
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.clicked.connect(self.tree_item_clicked)
        self.tree.doubleClicked.connect(self.tree_item_double_clicked)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.delete_tree_item_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.tree)
        self.delete_tree_item_shortcut.activated.connect(self.delete_selected_tree_item)
        sidebar_layout.addWidget(self.tree)

        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(350)

        # --- Inre splitter: editor | preview ---
        self.inner_splitter = QSplitter(Qt.Horizontal)

        self.editor = Editor(
            on_image_paste=self.handle_image_paste,
            translate=self._tr,
            link_base_path=self._editor_link_base_path,
            indent_text=INDENT_STYLE_TEXT[self.indent_style],
        )
        self.editor.setPlaceholderText("Skriv Markdown här...")
        self._apply_editor_font()
        self.editor_highlighter = MarkdownHighlighter(self.editor.document(), theme_mode=self.theme_mode)
        self._setup_find_bar()

        self.preview = QWebEngineView()
        self.preview.setPage(PreviewPage(self.preview))
        self._configure_web_view_security(self.preview, allow_javascript=True)
        self.preview.page().linkHovered.connect(self._show_preview_link_hover)
        self.preview_channel = QWebChannel(self.preview.page())
        self.preview_bridge = PreviewBridge(
            self._copy_preview_text,
            self.toggle_checkbox_from_preview,
            self.preview,
        )
        self.preview_channel.registerObject("previewBridge", self.preview_bridge)
        self.preview.page().setWebChannel(self.preview_channel)
        self.preview.loadFinished.connect(self._on_preview_loaded)
        self.preview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preview.customContextMenuRequested.connect(self._show_preview_context_menu)
        self.preview_copy_action = QAction(self.preview)
        self.preview_copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.preview_copy_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.preview_copy_action.triggered.connect(
            lambda: self.preview.triggerPageAction(QWebEnginePage.WebAction.Copy)
        )
        self.preview.addAction(self.preview_copy_action)
        self._load_preview_shell(force=True)

        self.inner_splitter.addWidget(self.editor_panel)
        self.inner_splitter.addWidget(self.preview)
        self.inner_splitter.setSizes([550, 550])

        self.outer_splitter.addWidget(sidebar)
        self.outer_splitter.addWidget(self.inner_splitter)
        self.outer_splitter.setSizes([220, 1100])

        self.setCentralWidget(self.outer_splitter)
        self.editor_count_label = QLabel()
        self.statusBar().addPermanentWidget(self.editor_count_label)

        outer_splitter_state = self.settings.value("outer_splitter")
        if outer_splitter_state:
            self.outer_splitter.restoreState(outer_splitter_state)

        inner_splitter_state = self.settings.value("inner_splitter")
        if inner_splitter_state:
            self.inner_splitter.restoreState(inner_splitter_state)

        self.timer = QTimer()
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.update_preview)

        self.autosave_timer = QTimer()
        self.autosave_timer.setInterval(2000)
        self.autosave_timer.timeout.connect(self.autosave)

        self.editor.textChanged.connect(self.timer.start)
        self.editor.textChanged.connect(self.autosave_timer.start)
        self.editor.textChanged.connect(self._update_editor_counts)
        self.editor.textChanged.connect(self._sync_status_from_editor)
        self.editor.cursorPositionChanged.connect(self._update_editor_counts)
        self.editor.verticalScrollBar().valueChanged.connect(self._sync_preview_scroll)

        self.sidebar_search_timer = QTimer(self)
        self.sidebar_search_timer.setSingleShot(True)
        self.sidebar_search_timer.setInterval(180)
        self.sidebar_search_timer.timeout.connect(lambda: self._apply_sidebar_search())
        self._update_editor_counts()

    def _setup_find_bar(self):
        self.editor_panel = QWidget()
        editor_layout = QVBoxLayout(self.editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(4)
        editor_layout.addWidget(self.editor)

        self.find_bar = DocumentFindBar(
            self.editor,
            translate=self._tr,
            action_parent=self,
            shortcut_parent=self.editor_panel,
            apply_highlights=lambda editor, selections: editor.setExtraSelections(selections),
            clear_highlights=lambda editor: editor.setExtraSelections([]),
            on_match_state_changed=self._apply_editor_stylesheet,
            parent=self.editor_panel,
        )
        self.find_input = self.find_bar.find_input
        editor_layout.addWidget(self.find_bar)

    def _configure_focus_navigation(self):
        self.menuBar().setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.sidebar_search.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.btn_new_file.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_new_folder.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.btn_sort.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.editor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.preview.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        toolbar_widgets = [
            self.toolbar.widgetForAction(self.toolbar_bold_action),
            self.toolbar.widgetForAction(self.toolbar_italic_action),
            self.toolbar.widgetForAction(self.toolbar_underline_action),
            self.toolbar.widgetForAction(self.toolbar_h1_action),
            self.toolbar.widgetForAction(self.toolbar_h2_action),
            self.toolbar.widgetForAction(self.toolbar_h3_action),
            self.toolbar.widgetForAction(self.toolbar_h4_action),
            self.toolbar.widgetForAction(self.toolbar_bullet_action),
            self.toolbar.widgetForAction(self.toolbar_numbered_action),
            self.toolbar.widgetForAction(self.toolbar_hr_action),
            self.toolbar.widgetForAction(self.toolbar_text_tool_action),
            self.toolbar.widgetForAction(self.toolbar_diff_action),
            self.status_combo,
            self.toggle_btn,
        ]
        focus_chain = [self.menuBar()] + [widget for widget in toolbar_widgets if widget is not None]
        for widget in focus_chain:
            widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        focus_chain.extend([self.sidebar_search, self.btn_new_file, self.btn_new_folder, self.btn_sort, self.tree, self.editor, self.preview])
        for current_widget, next_widget in zip(focus_chain, focus_chain[1:]):
            self.setTabOrder(current_widget, next_widget)

    def set_sort(self, mode):
        self.sort_mode = mode
        if mode == SortMode.NAME:
            sort_column = 0
            sort_order = Qt.SortOrder.AscendingOrder
            self.action_sort_name.setChecked(True)
        elif mode == SortMode.MODIFIED:
            sort_column = 3
            sort_order = Qt.SortOrder.AscendingOrder
            self.action_sort_modified.setChecked(True)
        else:
            sort_column = 0
            sort_order = Qt.SortOrder.AscendingOrder
            self.action_sort_created.setChecked(True)

        self.fs_proxy_model.set_sort_mode(mode.value)
        self.tree.sortByColumn(sort_column, sort_order)
        self.settings.setValue("sort_mode", mode.value)
        self._update_sort_button()

    def _update_sort_button(self):
        if self.sort_mode == SortMode.MODIFIED:
            self.btn_sort.setText("Ny-Gl")
            return
        if self.sort_mode == SortMode.CREATED:
            self.btn_sort.setText("Skap")
            return
        self.btn_sort.setText("A-Z")

    def _schedule_sidebar_search(self, text):
        self.sidebar_search_timer.start()

    def _apply_sidebar_search(self):
        text = self.sidebar_search.text()
        has_search = bool(text)
        if has_search and not getattr(self, "_tree_expanded_paths_before_search", None):
            self._tree_expanded_paths_before_search = self._expanded_tree_paths()
        self.fs_proxy_model.set_search(text)
        self._set_tree_workspace_root()
        if has_search:
            self.tree.expandAll()
        elif getattr(self, "_tree_expanded_paths_before_search", None) is not None:
            self._restore_expanded_tree_paths(self._tree_expanded_paths_before_search)
            self._tree_expanded_paths_before_search = None
        self.tree.viewport().update()

    def _expanded_tree_paths(self):
        expanded_paths = set()

        def walk(parent_index):
            for row in range(self.fs_proxy_model.rowCount(parent_index)):
                index = self.fs_proxy_model.index(row, 0, parent_index)
                if not index.isValid():
                    continue
                source_index = self.fs_proxy_model.mapToSource(index)
                if not source_index.isValid():
                    continue
                if self.tree.isExpanded(index):
                    expanded_paths.add(self.fs_model.filePath(source_index))
                    walk(index)

        walk(self.tree.rootIndex())
        return expanded_paths

    def _restore_expanded_tree_paths(self, expanded_paths):
        def walk(parent_index):
            for row in range(self.fs_proxy_model.rowCount(parent_index)):
                index = self.fs_proxy_model.index(row, 0, parent_index)
                if not index.isValid():
                    continue
                source_index = self.fs_proxy_model.mapToSource(index)
                if not source_index.isValid():
                    continue
                path = self.fs_model.filePath(source_index)
                if path in expanded_paths:
                    self.tree.expand(index)
                    walk(index)
                else:
                    self.tree.collapse(index)

        walk(self.tree.rootIndex())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F10:
            menubar = self.menuBar()
            menubar.setFocus(Qt.FocusReason.ShortcutFocusReason)
            menubar.setActiveAction(self.file_menu.menuAction())
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.modal_overlay is not None and self.modal_overlay.isVisible():
            self.modal_overlay.setGeometry(self.rect())

    def closeEvent(self, event):
        if not self._flush_pending_changes():
            event.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("outer_splitter", self.outer_splitter.saveState())
        if self.view_mode == ViewMode.SPLIT:
            self.settings.setValue("inner_splitter", self.inner_splitter.saveState())
            self.settings.setValue("inner_splitter_sizes", self.inner_splitter.saveState())
        self.settings.setValue("view_mode", self.view_mode.value)
        super().closeEvent(event)

    def toggle_editor_preview(self):
        if self.view_mode != ViewMode.SINGLE:
            return
        if self.editor_panel.isVisible():
            self.editor_panel.setVisible(False)
            self.preview.setVisible(True)
            self.update_preview()
        else:
            self.editor_panel.setVisible(True)
            self.preview.setVisible(False)
            self.editor.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._update_toggle_icon()

    def set_split_mode(self, enabled):
        if enabled:
            self.view_mode = ViewMode.SPLIT
            self.editor_panel.setVisible(True)
            self.preview.setVisible(True)
            sizes = self.settings.value("inner_splitter_sizes")
            if sizes:
                self.inner_splitter.restoreState(sizes)
            else:
                total = self.inner_splitter.width()
                half = max(1, total // 2)
                self.inner_splitter.setSizes([half, half])
            self.toggle_btn.setVisible(False)
            self.update_preview()
        else:
            if self.view_mode == ViewMode.SPLIT:
                self.settings.setValue("inner_splitter_sizes", self.inner_splitter.saveState())
            self.view_mode = ViewMode.SINGLE
            self.editor_panel.setVisible(True)
            self.preview.setVisible(False)
            self.toggle_btn.setVisible(True)
            self._update_toggle_icon()
        if self.action_split_view.isChecked() != enabled:
            self.action_split_view.setChecked(enabled)
        self.settings.setValue("view_mode", self.view_mode.value)

    def _update_toggle_icon(self):
        if self.editor_panel.isVisible():
            self.toggle_btn.setIcon(icon_from_svg(EDITOR_ON_ICON_SVG, size=32))
            return
        self.toggle_btn.setIcon(icon_from_svg(EDITOR_OFF_ICON_SVG, size=32))

    def _editor_selected_or_all_text(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            return cursor.selectedText().replace("\u2029", "\n"), True
        return self.editor.toPlainText(), False

    def _replace_editor_selected_or_all_text(self, text, replace_selection):
        cursor = self.editor.textCursor()
        if replace_selection and cursor.hasSelection():
            cursor.insertText(text)
            self.editor.setTextCursor(cursor)
        else:
            self.editor.setPlainText(text)

    def open_find_bar(self):
        self.find_bar.open_bar()

    def close_find_bar(self):
        self.find_bar.close_bar()

    def open_fulltext_search(self):
        if not self.workspace_dir or not os.path.isdir(self.workspace_dir):
            self.statusBar().showMessage(self._tr("Select workspace first"), 3000)
            return

        if self.fulltext_search_dialog is None:
            self.fulltext_search_dialog = FullTextSearchDialog(self)
            self.fulltext_search_dialog.apply_theme(self._theme_palette(), self.theme_mode)
            self.fulltext_search_dialog.resultActivated.connect(self._open_fulltext_search_result)

        self.fulltext_search_dialog.open_for_workspace(
            self.workspace_dir,
            self.fulltext_index,
            indexing_active=self.fulltext_indexing,
            progress=self.fulltext_index_progress,
        )

    def open_recent_switcher(self):
        if not self.workspace_dir or not os.path.isdir(self.workspace_dir):
            self.statusBar().showMessage(self._tr("Select workspace first"), 3000)
            return

        if self.recent_files_switcher is None:
            self.recent_files_switcher = RecentFilesSwitcher(self)
        self.recent_files_switcher.apply_theme(self._theme_palette(), self.theme_mode)

        self.recent_files_switcher.open_for_workspace(self.workspace_dir)

    def _open_find_bar_with_term(self, term):
        self.find_bar.open_bar(term)
        QTimer.singleShot(0, self.editor.setFocus)

    def _start_fulltext_indexing(self):
        if not self.workspace_dir or not os.path.isdir(self.workspace_dir):
            self.fulltext_index = {}
            self.fulltext_indexing = False
            self.fulltext_index_progress = (0, 0)
            return

        self.fulltext_index_generation += 1
        generation = self.fulltext_index_generation
        self.fulltext_indexing = True
        self.fulltext_index_progress = (0, 0)
        self.fulltext_index_overrides = {}

        indexer = Indexer(
            self.workspace_dir,
            on_progress=lambda current, total: self.fulltext_index_signals.progress.emit(generation, current, total),
            on_complete=lambda index: self.fulltext_index_signals.complete.emit(generation, index),
        )
        indexer.start()

        if self.fulltext_search_dialog is not None:
            self.fulltext_search_dialog.update_progress(*self.fulltext_index_progress)

    @Slot(int, int, int)
    def _on_fulltext_index_progress(self, generation, current, total):
        if generation != self.fulltext_index_generation:
            return
        self.fulltext_index_progress = (current, total)
        if self.fulltext_search_dialog is not None:
            self.fulltext_search_dialog.update_progress(current, total)

    @Slot(int, dict)
    def _on_fulltext_index_complete(self, generation, index):
        if generation != self.fulltext_index_generation:
            return

        merged_index = dict(index)
        for path, note_text in self.fulltext_index_overrides.items():
            if note_text is None:
                merged_index.pop(path, None)
            else:
                merged_index[path] = note_text

        self.fulltext_index = merged_index
        self.fulltext_indexing = False
        self.fulltext_index_progress = (self.fulltext_index_progress[1], self.fulltext_index_progress[1])
        if self.fulltext_search_dialog is not None:
            self.fulltext_search_dialog.update_index(self.fulltext_index)
            self.fulltext_search_dialog.mark_index_complete()

    def _record_fulltext_index_override(self, path, note_text):
        if self.fulltext_indexing:
            self.fulltext_index_overrides[path] = note_text

    def _update_fulltext_index_for_file(self, path):
        if not path or not path.endswith(".testlog"):
            return
        if not self.workspace_dir:
            return

        workspace_abs = os.path.abspath(self.workspace_dir)
        try:
            common_path = os.path.commonpath([os.path.abspath(path), workspace_abs])
        except ValueError:
            return
        if common_path != workspace_abs:
            return

        note_text = read_testlog_note_text(path)
        if note_text is None:
            self.fulltext_index.pop(path, None)
        else:
            self.fulltext_index[path] = note_text
        self._record_fulltext_index_override(path, note_text)

        if self.fulltext_search_dialog is not None:
            self.fulltext_search_dialog.update_index(self.fulltext_index)

    def _remove_fulltext_index_entries_for_path(self, path):
        normalized_path = os.path.abspath(path)
        remaining_index = {}
        for indexed_path, text in self.fulltext_index.items():
            indexed_abs = os.path.abspath(indexed_path)
            if indexed_abs == normalized_path or indexed_abs.startswith(normalized_path + os.sep):
                self._record_fulltext_index_override(indexed_path, None)
                continue
            remaining_index[indexed_path] = text
        self.fulltext_index = remaining_index

        if self.fulltext_search_dialog is not None:
            self.fulltext_search_dialog.update_index(self.fulltext_index)

    def _open_fulltext_search_result(self, path, query):
        if self.current_file and os.path.abspath(path) == os.path.abspath(self.current_file):
            self._open_find_bar_with_term(query)
            return

        if not self._flush_pending_changes():
            return

        self.open_testlog(path)
        self._open_find_bar_with_term(query)

    def _transform_editor_base64_encode(self):
        text, replace_selection = self._editor_selected_or_all_text()
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        self._replace_editor_selected_or_all_text(encoded, replace_selection)

    def _transform_editor_base64_decode(self):
        text, replace_selection = self._editor_selected_or_all_text()
        try:
            decoded = base64.b64decode(text.strip(), validate=True).decode("utf-8")
        except Exception:
            QMessageBox.warning(self, self._tr("Transform"), self._tr("Invalid Base64"))
            return
        self._replace_editor_selected_or_all_text(decoded, replace_selection)

    def _transform_editor_url_encode(self):
        text, replace_selection = self._editor_selected_or_all_text()
        self._replace_editor_selected_or_all_text(url_quote(text), replace_selection)

    def _transform_editor_url_decode(self):
        text, replace_selection = self._editor_selected_or_all_text()
        self._replace_editor_selected_or_all_text(url_unquote(text), replace_selection)

    def _transform_editor_format_json(self):
        text, replace_selection = self._editor_selected_or_all_text()
        formatted, valid, error = format_json_best_effort(text)
        self._replace_editor_selected_or_all_text(
            formatted,
            replace_selection,
        )
        if not valid:
            self.statusBar().showMessage(
                self._tr("Best-effort JSON formatting applied: {error}").format(error=error),
                5000,
            )

    def _transform_editor_guess_markdown(self):
        text, replace_selection = self._editor_selected_or_all_text()
        guessed = guess_markdown_from_plain_text(text)
        self._replace_editor_selected_or_all_text(guessed, replace_selection)

    def _insert_line_prefix(self, prefix):
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        if cursor.hasSelection():
            cursor.setPosition(start)
            first_block = cursor.block().blockNumber()
            cursor.setPosition(end)
            if cursor.positionInBlock() == 0 and end > start:
                last_block = max(first_block, cursor.block().blockNumber() - 1)
            else:
                last_block = cursor.block().blockNumber()
        else:
            first_block = cursor.block().blockNumber()
            last_block = first_block

        doc = self.editor.document()
        all_prefixed = True
        for block_number in range(first_block, last_block + 1):
            if not doc.findBlockByNumber(block_number).text().startswith(prefix):
                all_prefixed = False
                break

        for block_number in range(first_block, last_block + 1):
            block = doc.findBlockByNumber(block_number)
            line_cursor = self.editor.textCursor()
            line_cursor.setPosition(block.position())

            if all_prefixed:
                for _ in range(len(prefix)):
                    line_cursor.deleteChar()
            else:
                line_cursor.insertText(prefix)

        cursor.endEditBlock()
        self.editor.setFocus()

    def _insert_horizontal_rule(self):
        cursor = self.editor.textCursor()
        cursor.insertText("\n---\n")
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def insert_link(self):
        selected_text = self.editor.textCursor().selectedText().replace("\u2029", "\n")
        initial_text = selected_text
        initial_url = ""
        if self._looks_like_url(selected_text):
            initial_text = ""
            initial_url = selected_text.strip()

        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("Insert Link..."))
        dialog.resize(460, dialog.sizeHint().height())
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        text_input = QLineEdit(dialog)
        text_input.setText(initial_text)
        url_input = QLineEdit(dialog)
        url_input.setText(initial_url)

        form_layout.addRow(self._tr("Text:"), text_input)
        form_layout.addRow(self._tr("URL:"), url_input)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        url = url_input.text().strip()
        text = text_input.text().strip()
        if not url:
            return
        if not text:
            text = url

        self.editor.insert_markdown_text(f"[{text}]({url})")
        self.editor.setFocus()

    def insert_image(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("Insert Image..."))
        dialog.resize(520, dialog.sizeHint().height())
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        alt_input = QLineEdit(dialog)
        selected_text = self.editor.textCursor().selectedText().replace("\u2029", "\n").strip()
        if selected_text and not self._looks_like_url(selected_text):
            alt_input.setText(selected_text)

        source_input = QLineEdit(dialog)
        browse_button = QPushButton(self._tr("Browse..."), dialog)
        copy_checkbox = QCheckBox(self._tr("Copy image into note"), dialog)
        copy_checkbox.setChecked(True)

        source_row = QHBoxLayout()
        source_row.setContentsMargins(0, 0, 0, 0)
        source_row.addWidget(source_input, 1)
        source_row.addWidget(browse_button)

        form_layout.addRow(self._tr("Alt text:"), alt_input)
        form_layout.addRow(self._tr("Path or URL:"), source_row)
        form_layout.addRow("", copy_checkbox)
        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        def choose_image_file():
            path, _ = QFileDialog.getOpenFileName(
                self,
                self._tr("Select image"),
                "",
                self._tr("Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg)"),
            )
            if not path:
                return
            source_input.setText(path)
            if not alt_input.text().strip():
                alt_input.setText(Path(path).stem.replace("-", " ").replace("_", " "))
            copy_checkbox.setChecked(True)

        browse_button.clicked.connect(choose_image_file)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        source_value = source_input.text().strip()
        if not source_value:
            return

        alt_text = alt_input.text().strip()
        markdown_source = source_value
        if self._should_copy_inserted_image(source_value, copy_checkbox.isChecked()):
            markdown_source = self._copy_image_into_note(source_value)
            if markdown_source is None:
                return

        self.editor.insert_markdown_text(f"![{alt_text}]({markdown_source})")
        self.editor.setFocus()

    def _looks_like_url(self, text):
        candidate = text.strip()
        return bool(candidate) and re.match(r"^(https?|ftp|file)://\S+$", candidate) is not None

    def _should_copy_inserted_image(self, source_value, copy_requested):
        if not copy_requested:
            return False
        if self._looks_like_url(source_value):
            return False
        return os.path.exists(source_value)

    def _copy_image_into_note(self, source_path):
        source_abs = os.path.abspath(source_path)
        images_abs = os.path.abspath(self.images_dir)
        if source_abs.startswith(images_abs + os.sep):
            return f"images/{url_quote(os.path.basename(source_abs))}"

        base_name = os.path.basename(source_abs)
        candidate_name = base_name
        stem = Path(base_name).stem
        suffix = Path(base_name).suffix
        counter = 2
        destination = os.path.join(self.images_dir, candidate_name)
        while os.path.exists(destination):
            candidate_name = f"{stem}-{counter}{suffix}"
            destination = os.path.join(self.images_dir, candidate_name)
            counter += 1

        try:
            shutil.copy2(source_abs, destination)
        except OSError:
            QMessageBox.warning(
                self,
                self._tr("Insert Image..."),
                self._tr("Could not copy image into note"),
            )
            return None
        return f"images/{url_quote(candidate_name)}"

    def open_workspace(self):
        path = QFileDialog.getExistingDirectory(self, self._tr("Select workspace"))
        if not path:
            return
        self._set_workspace(path)

    def open_text_tool(self):
        if not hasattr(self, "text_tool_dialog") or self.text_tool_dialog is None:
            self.text_tool_dialog = TextToolDialog(self._tr, self)
        self.text_tool_dialog.show()
        self.text_tool_dialog.raise_()
        self.text_tool_dialog.activateWindow()

    def open_diff_window(self):
        if self.diff_window is None:
            self.diff_window = DiffWindow(self._tr, self._theme_palette(), self.editor.font(), self)
        self.diff_window.show()
        self.diff_window.raise_()
        self.diff_window.activateWindow()

    def send_editor_text_to_diff(self, pane_name):
        self.open_diff_window()
        self.diff_window.set_pane_text(pane_name, self.editor.toPlainText())

    def refresh_pinned(self):
        valid_paths = [path for path in self.pinned_files if os.path.exists(path)]
        if valid_paths != self.pinned_files:
            self.pinned_files = valid_paths
            self._save_pinned_files()

        self.pinned_paths.clear()
        self.pinned_paths.update(self.pinned_files)
        self.fs_proxy_model.invalidate()
        self.set_sort(self.sort_mode)
        self.tree.viewport().update()

    def show_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return

        source_index = self.fs_proxy_model.mapToSource(index)
        path = self.fs_model.filePath(source_index)
        is_file = path.endswith(".testlog") and os.path.isfile(path)
        is_dir = os.path.isdir(path)
        if not is_file and not is_dir:
            return

        menu = QMenu(self)

        rename_action = menu.addAction(self._tr("Rename"))
        delete_action = menu.addAction(self._tr("Delete"))
        move_action = menu.addAction(self._tr("Move To..."))
        if is_file:
            status_menu = menu.addMenu(self._tr("Status"))
            status_actions = {}
            current_status = get_testlog_status(self.editor.toPlainText()) if self.current_file and os.path.abspath(path) == os.path.abspath(self.current_file) else read_testlog_status_from_archive(path)
            for status in TESTLOG_STATUS_OPTIONS:
                action = status_menu.addAction(self._tr(TESTLOG_STATUS_LABELS[status]))
                action.setCheckable(True)
                action.setChecked(status == current_status)
                status_actions[action] = status
            menu.addSeparator()
            pin_action = menu.addAction(self._tr("Unpin") if path in self.pinned_paths else self._tr("Pin to Top"))
            menu.addSeparator()
            archive_action = menu.addAction(self._tr("Archive"))
        else:
            status_actions = {}
            pin_action = None
            archive_action = None

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == rename_action:
            self.rename_item(path)
        elif chosen == delete_action:
            self.delete_item(path)
        elif chosen == move_action:
            self.move_item(path)
        elif chosen in status_actions:
            self.set_file_status(path, status_actions[chosen])
        elif chosen == pin_action:
            self.toggle_pin(path)
        elif chosen == archive_action:
            self.archive_item(path)

    def delete_selected_tree_item(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            return

        source_index = self.fs_proxy_model.mapToSource(index)
        path = self.fs_model.filePath(source_index)
        is_file = path.endswith(".testlog") and os.path.isfile(path)
        is_dir = os.path.isdir(path)
        if is_file or is_dir:
            self.delete_item(path)

    def set_file_status(self, path, status):
        normalized_status = normalize_testlog_status(status)
        if not path.endswith(".testlog") or not os.path.isfile(path):
            return

        if self.current_file and os.path.abspath(path) == os.path.abspath(self.current_file):
            self.current_status = normalized_status
            self._set_status_combo(normalized_status)
            updated_text = set_testlog_status(self.editor.toPlainText(), normalized_status)
            if updated_text != self.editor.toPlainText():
                self._replace_editor_text_preserving_cursor(updated_text)
            self.save_file()
            return

        self._write_status_to_testlog(path, normalized_status)
        self._update_fulltext_index_for_file(path)
        self.fs_model.refresh_status(path)
        self._refresh_sidebar_sort()

    def _write_status_to_testlog(self, path, status):
        entries = []
        note_content = ""
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if info.filename == "note.md":
                    note_content = zf.read(info.filename).decode("utf-8")
                    continue
                entries.append((info, zf.read(info.filename)))

        note_content = set_testlog_status(note_content, status)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("note.md", note_content)
            for info, content in entries:
                zf.writestr(info, content)

    def rename_item(self, path):
        current_name = Path(path).name if os.path.isdir(path) else Path(path).stem
        dialog = QInputDialog(self)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setWindowTitle(self._tr("Rename"))
        dialog.setLabelText(self._tr("Filename (without .testlog):"))
        dialog.setTextValue(current_name)
        dialog.resize(460, dialog.sizeHint().height())
        QTimer.singleShot(0, lambda: self._position_rename_dialog_cursor(dialog, current_name))

        if dialog.exec() != QInputDialog.DialogCode.Accepted:
            return

        new_name = dialog.textValue()
        if not new_name.strip():
            return

        new_path = os.path.join(
            os.path.dirname(path),
            new_name.strip() if os.path.isdir(path) else new_name.strip() + ".testlog",
        )
        if new_path == path:
            return

        current_abs = os.path.abspath(self.current_file) if self.current_file else None
        path_abs = os.path.abspath(path)

        if not os.path.isdir(path) and current_abs == path_abs:
            self.autosave_timer.stop()
            self._write_testlog(new_path)
            if os.path.exists(path):
                os.remove(path)
        else:
            os.rename(path, new_path)

        self._update_tracked_paths(path, new_path)

        self.refresh_pinned()
        if current_abs == path_abs:
            self.current_file = new_path
            self.setWindowTitle(self._window_title(os.path.basename(new_path)))
        self._select_file_in_tree(new_path, retry_attempts=6)
        self._start_fulltext_indexing()

    def _position_rename_dialog_cursor(self, dialog, current_name):
        line_edit = dialog.findChild(QLineEdit)
        if line_edit is None:
            return
        line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        line_edit.deselect()
        line_edit.setCursorPosition(len(current_name))

    def delete_item(self, path):
        deleted_index = self.fs_proxy_model.mapFromSource(self.fs_model.index(path))
        replacement_path = self._replacement_file_path_after_delete(deleted_index, path)
        filename = os.path.basename(path)
        answer = QMessageBox.question(
            self,
            self._tr("Confirm Delete"),
            self._tr(
                "Delete Folder {filename}? This cannot be undone."
                if os.path.isdir(path)
                else "Delete {filename}? This cannot be undone."
            ).format(filename=filename),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

        self._remove_tracked_paths(path)
        self._remove_fulltext_index_entries_for_path(path)
        self.refresh_pinned()
        if self.current_file is None:
            if replacement_path and os.path.isfile(replacement_path):
                self.open_testlog(replacement_path)
            else:
                self.editor.clear()
                self.tree.clearSelection()
                self.setWindowTitle(self._window_title())
        self._start_fulltext_indexing()

    def _replacement_file_path_after_delete(self, deleted_index, deleted_path):
        if not deleted_index.isValid():
            return None

        for neighbor_getter in (self.tree.indexBelow, self.tree.indexAbove):
            neighbor_index = neighbor_getter(deleted_index)
            while neighbor_index.isValid():
                source_index = self.fs_proxy_model.mapToSource(neighbor_index)
                candidate_path = self.fs_model.filePath(source_index)
                if candidate_path != deleted_path and candidate_path.endswith(".testlog") and os.path.isfile(candidate_path):
                    return candidate_path
                neighbor_index = neighbor_getter(neighbor_index)
        return None

    def move_item(self, path):
        destination = QFileDialog.getExistingDirectory(
            self,
            self._tr("Move Item"),
            self._selected_directory_for_new_items(),
        )
        if not destination:
            return

        new_path = os.path.join(destination, os.path.basename(path))
        if os.path.abspath(new_path) == os.path.abspath(path):
            return

        os.rename(path, new_path)
        self._update_tracked_paths(path, new_path)
        self.refresh_pinned()
        self._select_file_in_tree(new_path)
        self._start_fulltext_indexing()

    def archive_item(self, path):
        if not self.workspace_dir or not path.endswith(".testlog") or not os.path.isfile(path):
            return

        if self.current_file and os.path.abspath(path) == os.path.abspath(self.current_file):
            if not self._flush_pending_changes():
                return

        archive_dir = os.path.join(self.workspace_dir, self._archive_folder_name())
        os.makedirs(archive_dir, exist_ok=True)

        new_path = os.path.join(archive_dir, os.path.basename(path))
        if os.path.abspath(new_path) == os.path.abspath(path):
            return

        new_path = self._available_path(new_path)
        os.rename(path, new_path)
        self._update_tracked_paths(path, new_path)
        self.refresh_pinned()
        self._select_file_in_tree(new_path, retry_attempts=6)
        self._start_fulltext_indexing()

    def _archive_folder_name(self):
        return "Arkiv" if self.current_language == "sv" else "Archive"

    def _available_path(self, path):
        if not os.path.exists(path):
            return path

        directory = os.path.dirname(path)
        stem, extension = os.path.splitext(os.path.basename(path))
        counter = 2
        while True:
            candidate = os.path.join(directory, f"{stem} {counter}{extension}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    def toggle_pin(self, path):
        if path in self.pinned_files:
            self.pinned_files = [p for p in self.pinned_files if p != path]
        else:
            self.pinned_files.append(path)
        self._save_pinned_files()
        self.refresh_pinned()

    def _selected_directory_for_new_items(self):
        if not hasattr(self, "tree"):
            return self.workspace_dir or ""

        index = self.tree.currentIndex()
        if not index.isValid():
            return self.workspace_dir or ""

        source_index = self.fs_proxy_model.mapToSource(index)
        path = self.fs_model.filePath(source_index)
        if os.path.isdir(path):
            return path
        return os.path.dirname(path) or self.workspace_dir or ""

    def _update_tracked_paths(self, old_path, new_path):
        old_abs = os.path.abspath(old_path)
        new_abs = os.path.abspath(new_path)

        updated_pins = []
        changed = False
        for pinned in self.pinned_files:
            pinned_abs = os.path.abspath(pinned)
            if pinned_abs == old_abs or pinned_abs.startswith(old_abs + os.sep):
                suffix = pinned_abs[len(old_abs):]
                updated_pins.append(new_abs + suffix)
                changed = True
            else:
                updated_pins.append(pinned)
        if changed:
            self.pinned_files = updated_pins
            self._save_pinned_files()

        if self.current_file:
            current_abs = os.path.abspath(self.current_file)
            if current_abs == old_abs or current_abs.startswith(old_abs + os.sep):
                suffix = current_abs[len(old_abs):]
                self.current_file = new_abs + suffix
                self.setWindowTitle(self._window_title(os.path.basename(self.current_file)))

    def _remove_tracked_paths(self, deleted_path):
        deleted_abs = os.path.abspath(deleted_path)
        new_pins = [
            p for p in self.pinned_files
            if not (os.path.abspath(p) == deleted_abs or os.path.abspath(p).startswith(deleted_abs + os.sep))
        ]
        if new_pins != self.pinned_files:
            self.pinned_files = new_pins
            self._save_pinned_files()

        if self.current_file:
            current_abs = os.path.abspath(self.current_file)
            if current_abs == deleted_abs or current_abs.startswith(deleted_abs + os.sep):
                self.current_file = None

    def new_file_in_workspace(self):
        if not self.workspace_dir:
            QFileDialog.getExistingDirectory(self, self._tr("Select workspace first"))
            return
        if not self._flush_pending_changes():
            return
        dialog = QInputDialog(self)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setWindowTitle(self._tr("New file"))
        dialog.setLabelText(self._tr("Filename (without .testlog):"))
        dialog.resize(460, dialog.sizeHint().height())

        if dialog.exec() != QInputDialog.DialogCode.Accepted:
            return

        name = dialog.textValue()
        if not name.strip():
            return
        target_dir = self._selected_directory_for_new_items()
        path = os.path.join(target_dir, name.strip() + ".testlog")
        self.current_file = path
        self._new_session()
        self.current_status = DEFAULT_TESTLOG_STATUS
        self._set_status_combo(self.current_status)
        self.editor.setPlainText(set_testlog_status(f"# {name.strip()}\n", self.current_status))
        self.save_file()
        self._select_file_in_tree(path)
        self.tree.setFocus()
        self.setWindowTitle(self._window_title(f"{name.strip()}.testlog"))

    def new_folder_in_workspace(self):
        if not self.workspace_dir:
            return
        dialog = QInputDialog(self)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setWindowTitle(self._tr("New folder"))
        dialog.setLabelText(self._tr("Folder name:"))
        dialog.resize(460, dialog.sizeHint().height())

        if dialog.exec() != QInputDialog.DialogCode.Accepted:
            return

        name = dialog.textValue()
        if not name.strip():
            return
        target_dir = self._selected_directory_for_new_items()
        new_path = os.path.join(target_dir, name.strip())
        os.makedirs(new_path, exist_ok=True)
        self._select_file_in_tree(new_path)
        self.tree.setFocus()

    def tree_item_clicked(self, index):
        source_index = self.fs_proxy_model.mapToSource(index)
        path = self.fs_model.filePath(source_index)
        if path.endswith(".testlog"):
            if self.current_file and os.path.abspath(path) == os.path.abspath(self.current_file):
                return
            if not self._flush_pending_changes():
                return
            self.open_testlog(path)

    def tree_item_double_clicked(self, index):
        source_index = self.fs_proxy_model.mapToSource(index)
        path = self.fs_model.filePath(source_index)
        if path.endswith(".testlog") and os.path.isfile(path):
            self.rename_item(path)

    def _open_most_recent_testlog(self):
        if not self.workspace_dir:
            return

        latest_path = None
        latest_mtime = -1.0

        for root, _, files in os.walk(self.workspace_dir):
            for name in files:
                if not name.endswith(".testlog"):
                    continue

                path = os.path.join(root, name)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue

                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_path = path

        if latest_path:
            self.open_testlog(latest_path)

    def handle_image_paste(self, image: QImage):
        filename = f"screenshot-{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(self.images_dir, filename)
        image.save(filepath, "PNG")
        cursor = self.editor.textCursor()
        cursor.insertText(f"\n![{filename}](images/{filename})\n")

    def update_preview(self):
        self.timer.stop()
        source_max = self.editor.verticalScrollBar().maximum()
        self._pending_preview_scroll_ratio = 0.0 if source_max <= 0 else self.editor.verticalScrollBar().value() / source_max
        self._pending_preview_body_html = self._build_preview_body_html(interactive=True)
        self._load_preview_shell()
        self._apply_preview_content()

    def toggle_checkbox_from_preview(self, index, checked):
        text = self.editor.toPlainText()
        lines = text.split("\n")
        checkbox_pattern = re.compile(r'^(\s*(?:[-+*]|\d+[.)])\s+\[)( |x|X)(\].*)$')
        editor_view_state = self.editor._capture_view_state()
        cursor = self.editor.textCursor()
        cursor_position = cursor.position()
        anchor_position = cursor.anchor()
        self._pending_preview_scroll_ratio = self._scroll_ratio(self.editor.verticalScrollBar())

        checkbox_count = 0
        for line_index, line in enumerate(lines):
            match = checkbox_pattern.match(line)
            if not match:
                continue

            if checkbox_count == index:
                marker = "x" if checked else " "
                lines[line_index] = f"{match.group(1)}{marker}{match.group(3)}"
                cursor.beginEditBlock()
                cursor.select(QTextCursor.SelectionType.Document)
                cursor.insertText("\n".join(lines))
                cursor.setPosition(anchor_position)
                cursor.setPosition(cursor_position, QTextCursor.MoveMode.KeepAnchor)
                cursor.endEditBlock()
                self.editor.setTextCursor(cursor)
                self.editor._restore_view_state(editor_view_state)
                return

            checkbox_count += 1

    def _update_editor_counts(self):
        text = self.editor.toPlainText()
        text_without_whitespace = "".join(ch for ch in text if not ch.isspace())

        selected_text = self.editor.textCursor().selectedText().replace("\u2029", "\n")
        selected_without_whitespace = "".join(ch for ch in selected_text if not ch.isspace())

        self.editor_count_label.setText(
            self._tr(
                "Editor Count: {with_ws} | No ws: {without_ws} | Selected: {sel_with_ws} | Selected no ws: {sel_without_ws}"
            ).format(
                with_ws=len(text),
                without_ws=len(text_without_whitespace),
                sel_with_ws=len(selected_text),
                sel_without_ws=len(selected_without_whitespace),
            )
        )

    def _sync_preview_scroll(self, value):
        source_max = self.editor.verticalScrollBar().maximum()
        self._pending_preview_scroll_ratio = 0.0 if source_max <= 0 else value / source_max
        if not self.editor.should_sync_preview_scroll():
            return
        self._set_preview_scroll_ratio(self._pending_preview_scroll_ratio)

    def _scroll_ratio(self, scrollbar):
        maximum = scrollbar.maximum()
        if maximum <= 0:
            return 0.0
        return scrollbar.value() / maximum

    def _on_preview_loaded(self, ok):
        if not ok:
            return
        self._preview_loaded = True
        self._apply_preview_content()
        self._set_preview_scroll_ratio(self._pending_preview_scroll_ratio)

    def _set_preview_scroll_ratio(self, ratio):
        clamped_ratio = max(0.0, min(1.0, ratio))
        self.preview.page().runJavaScript(
            "window.setPreviewScrollRatio(%f);" % clamped_ratio
        )

    def _editor_has_unsaved_changes(self):
        return self.editor.document().isModified()

    def _flush_pending_changes(self):
        if not self._editor_has_unsaved_changes():
            return True

        self.autosave_timer.stop()

        if self.current_file:
            return self.save_file()

        if not self.editor.toPlainText().strip():
            return True

        answer = QMessageBox.question(
            self,
            self._tr("Unsaved Changes"),
            self._tr("Save changes before leaving this file?"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return self.save_file()

    def autosave(self):
        self.autosave_timer.stop()
        if not self.current_file or not self._editor_has_unsaved_changes():
            return
        self.save_file()
        self.statusBar().showMessage(self._tr("Autosaved"), 2000)

    def new_file(self):
        if not self._flush_pending_changes():
            return
        self.autosave_timer.stop()
        self.current_status = DEFAULT_TESTLOG_STATUS
        self._set_status_combo(self.current_status)
        self.editor.setPlainText(set_testlog_status("", self.current_status))
        self.current_file = None
        self._new_session()
        self.editor.document().setModified(False)
        self.update_preview()
        self.setWindowTitle(self._window_title())

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self._tr("Open testlog"), "", self._tr("TestLog Files (*.testlog)")
        )
        if path:
            if not self._flush_pending_changes():
                return
            self.open_testlog(path)

    def open_testlog(self, path):
        self.autosave_timer.stop()
        self.close_find_bar()
        shutil.rmtree(self.session_dir, ignore_errors=True)
        self._new_session()

        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(self.session_dir)

        note_path = os.path.join(self.session_dir, "note.md")
        self.current_status = DEFAULT_TESTLOG_STATUS
        self._set_status_combo(self.current_status)
        self.editor.clear()
        if os.path.exists(note_path):
            with open(note_path, "r", encoding="utf-8") as f:
                note_content = f.read()
                self.current_status = get_testlog_status(note_content)
                note_content = set_testlog_status(note_content, self.current_status)
                self._set_status_combo(self.current_status)
                self.editor.setPlainText(note_content)

        self.current_file = path
        self.editor.document().setModified(False)
        self.autosave_timer.stop()
        self.update_preview()
        self.setWindowTitle(self._window_title(os.path.basename(path)))
        self._select_file_in_tree(path)
        self._add_to_recent(path)

    def _select_file_in_tree(self, path, retry_attempts=0):
        source_index = self.fs_model.index(path)
        if not source_index.isValid():
            if retry_attempts > 0:
                QTimer.singleShot(
                    100,
                    lambda path=path, retry_attempts=retry_attempts - 1: self._select_file_in_tree(path, retry_attempts),
                )
            return

        index = self.fs_proxy_model.mapFromSource(source_index)
        if not index.isValid():
            if self.sidebar_search.text():
                self.sidebar_search.clear()
                index = self.fs_proxy_model.mapFromSource(source_index)
            if not index.isValid():
                if retry_attempts > 0:
                    QTimer.singleShot(
                        100,
                        lambda path=path, retry_attempts=retry_attempts - 1: self._select_file_in_tree(path, retry_attempts),
                    )
                return

        parent = index.parent()
        while parent.isValid():
            self.tree.expand(parent)
            parent = parent.parent()

        self.tree.setCurrentIndex(index)
        self.tree.selectionModel().select(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.tree.scrollTo(index)

    def save_file(self):
        if self.current_file:
            return self._write_testlog(self.current_file)
        else:
            return self.save_file_as()

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self._tr("Save testlog"), self.workspace_dir or "", self._tr("TestLog Files (*.testlog)")
        )
        if not path:
            return False
        if not path.endswith(".testlog"):
            path += ".testlog"
        previous_path = self.current_file
        self._write_testlog(path)
        self.current_file = path
        if previous_path and os.path.abspath(previous_path) != os.path.abspath(path):
            if os.path.exists(previous_path):
                self._update_fulltext_index_for_file(previous_path)
            else:
                self._remove_fulltext_index_entries_for_path(previous_path)
        self.setWindowTitle(self._window_title(os.path.basename(path)))
        return True

    def _write_testlog(self, path):
        note_content = set_testlog_status(self.editor.toPlainText(), self.current_status)
        note_path = os.path.join(self.session_dir, "note.md")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(note_content)

        # Find all image filenames referenced in the note
        referenced = collect_referenced_image_filenames(note_content)

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(note_path, "note.md")
            if os.path.exists(self.images_dir):
                for img in os.listdir(self.images_dir):
                    if img in referenced:
                        img_path = os.path.join(self.images_dir, img)
                        zf.write(img_path, f"images/{img}")
        self.editor.document().setModified(False)
        self.autosave_timer.stop()
        self._update_fulltext_index_for_file(path)
        self.fs_model.refresh_status(path)
        self._refresh_sidebar_sort()
        return True

    def _refresh_sidebar_sort(self):
        self.fs_proxy_model.invalidate()
        if self.sort_mode == SortMode.MODIFIED:
            sort_column = 3
            sort_order = Qt.SortOrder.AscendingOrder
        elif self.sort_mode == SortMode.CREATED:
            sort_column = 0
            sort_order = Qt.SortOrder.AscendingOrder
        else:
            sort_column = 0
            sort_order = Qt.SortOrder.AscendingOrder
        self.tree.sortByColumn(sort_column, sort_order)

    def _suggest_filename_from_heading(self):
        """Extract first heading from editor to use as filename."""
        return suggest_filename_from_heading(self.editor.toPlainText())

    def _default_export_path(self, extension):
        if self.current_file:
            filename = Path(self.current_file).with_suffix(f".{extension}").name
        else:
            filename = self._suggest_filename_from_heading() + f".{extension}"
        return os.path.join(self.workspace_dir or "", filename)

    def export_text_copy(self, extension):
        extension = extension.lower().lstrip(".")
        if extension == "md":
            title = self._tr("Export as Markdown")
            file_filter = self._tr("Markdown Files (*.md)")
            success_message = self._tr("Markdown exported")
        elif extension == "txt":
            title = self._tr("Export as Text")
            file_filter = self._tr("Text Files (*.txt)")
            success_message = self._tr("Text exported")
        else:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, title, self._default_export_path(extension), file_filter
        )
        if not path:
            return
        if not path.lower().endswith(f".{extension}"):
            path += f".{extension}"

        with open(path, "w", encoding="utf-8") as f:
            f.write(strip_testlog_front_matter(self.editor.toPlainText()))
        self.statusBar().showMessage(success_message, 3000)

    def _embed_images_as_base64(self, html):
        def replace_src(match):
            path = self._resolve_preview_image_path(match.group(1))
            if not path:
                return match.group(0)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                ext = os.path.splitext(path)[1].lower().strip(".")
                mime = "image/png" if ext == "png" else f"image/{ext}"
                return f'src="data:{mime};base64,{data}"'
            return match.group(0)

        return re.sub(r'src="([^"]+)"', replace_src, html)

    def _resolve_preview_image_path(self, src):
        return resolve_preview_image_path(src, self.session_dir)

    def _build_preview_body_html(self, interactive=False, theme_mode=None):
        md = strip_testlog_front_matter(self.editor.toPlainText())
        rendered = self.md_parser.render(md)
        rendered = self._linkify_preview_bare_urls(rendered)
        rendered = self._style_headings(rendered, theme_mode=theme_mode)
        rendered = self._style_code_blocks(rendered, interactive=interactive)
        return self._sanitize_preview_html(rendered)

    def _linkify_preview_bare_urls(self, html):
        linkifier = PreviewBareUrlLinkifier()
        linkifier.feed(html)
        linkifier.close()
        return linkifier.result()

    def _build_preview_html(self, interactive=False, theme_mode=None):
        body_html = self._build_preview_body_html(interactive=interactive, theme_mode=theme_mode)
        html = PREVIEW_STYLE + self._preview_theme_assets(theme_mode=theme_mode)
        if interactive:
            html += self._preview_interaction_assets(theme_mode=theme_mode)
        return html + body_html

    def _build_preview_shell_html(self, theme_mode=None):
        body_html = self._pending_preview_body_html or ""
        return (
            PREVIEW_STYLE
            + self._preview_theme_assets(theme_mode=theme_mode)
            + self._preview_interaction_assets(theme_mode=theme_mode)
            + "<div id=\"preview-content\"></div>"
            + f"<script>window.renderPreviewContent({json.dumps(body_html)});</script>"
        )

    def _current_preview_base_url(self):
        return QUrl.fromLocalFile(os.path.join(self.session_dir, ""))

    def _load_preview_shell(self, force=False):
        base_url = self._current_preview_base_url()
        shell_key = (base_url.toString(), self.theme_mode, self.current_language)
        if not force and self._preview_loaded and self._preview_base_url == base_url and self._preview_shell_key == shell_key:
            return
        self._preview_loaded = False
        self._preview_base_url = base_url
        self._preview_shell_key = shell_key
        self.preview.setHtml(self._build_preview_shell_html(theme_mode=self.theme_mode), base_url)

    def _apply_preview_content(self):
        if not self._preview_loaded:
            return
        content_json = json.dumps(self._pending_preview_body_html or "")
        self.preview.page().runJavaScript(
            f"window.renderPreviewContent({content_json});"
            f"window.setPreviewScrollRatio({self._pending_preview_scroll_ratio:.12f});"
        )

    def _pdf_typography_assets(self):
        return """
<style>
  body {
    font-size: 15px;
    line-height: 1.28;
  }

  p, li, td, th, blockquote {
    font-size: 15px;
    line-height: 1.28;
  }

  table {
    font-size: 0.95em;
  }
</style>
"""

    def _preview_theme_assets(self, theme_mode=None):
        palette = self._theme_palette(theme_mode=theme_mode)
        heading_colors = self._preview_heading_colors(theme_mode=theme_mode)
        return f"""
<style>
  meta[http-equiv="Content-Security-Policy"] {{
    display: none;
  }}
  html, body {{
    background: {palette["panel_bg"]};
  }}
  body, p, li, td, th, blockquote {{
    color: {palette["text"]};
  }}
  h1 {{
    color: {heading_colors[1]};
  }}
  h2 {{
    color: {heading_colors[2]};
  }}
  h3 {{
    color: {heading_colors[3]};
  }}
  h4 {{
    color: {heading_colors[4]};
  }}
  code, .code-wrapper {{
    background: {palette["code_bg"]} !important;
    color: {palette["code_text"]} !important;
    border-color: {palette["code_border"]} !important;
  }}
  th {{
    background: {palette["table_header_bg"]};
  }}
  tr:nth-child(even) {{
    background: {palette["table_alt_bg"]};
  }}
  td, th {{
    border-color: {palette["panel_border"]};
  }}
  blockquote {{
    color: {palette["muted_text"]};
    border-left-color: {palette["blockquote_border"]};
  }}
  hr {{
    border-top-color: {palette["hr"]};
  }}
  a {{
    color: {palette["link"]};
    text-decoration: underline;
  }}
  {self._preview_scrollbar_css(theme_mode=theme_mode)}
</style>
"""

    def _preview_interaction_assets(self, theme_mode=None):
        palette = self._theme_palette(theme_mode=theme_mode)
        copy_label = self._tr("Copy")
        copied_label = self._tr("Copied")
        return f"""
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: file:; style-src 'unsafe-inline'; script-src 'unsafe-inline' qrc:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
<style>
  .code-wrapper {{
    position: relative;
  }}
  .copy-btn {{
    position: absolute;
    top: 8px;
    right: 8px;
    padding: 3px 10px;
    font-size: 0.75em;
    background: {palette["copy_button_bg"]};
    color: {palette["text"]};
    border: 1px solid {palette["copy_button_border"]};
    border-radius: 4px;
    cursor: pointer;
    opacity: 0.7;
  }}
  .copy-btn:hover {{
    opacity: 1;
  }}
  input[type="checkbox"] {{
    cursor: pointer;
  }}
</style>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  window.previewBridge = null;

  function syncImageAttributes(target, source) {{
    Array.from(target.attributes).forEach(function(attr) {{
      if (!source.hasAttribute(attr.name)) {{
        target.removeAttribute(attr.name);
      }}
    }});

    Array.from(source.attributes).forEach(function(attr) {{
      target.setAttribute(attr.name, attr.value);
    }});
  }}

  function reuseExistingImages(fragment, container) {{
    const imagesBySrc = new Map();
    container.querySelectorAll('img').forEach(function(img) {{
      const src = img.getAttribute('src') || '';
      if (!imagesBySrc.has(src)) {{
        imagesBySrc.set(src, []);
      }}
      imagesBySrc.get(src).push(img);
    }});

    fragment.querySelectorAll('img').forEach(function(img) {{
      const src = img.getAttribute('src') || '';
      const matches = imagesBySrc.get(src);
      if (!matches || matches.length === 0) {{
        return;
      }}

      const existing = matches.shift();
      syncImageAttributes(existing, img);
      img.replaceWith(existing);
    }});
  }}

  function bindCopyButtons() {{
    document.querySelectorAll('.copy-btn').forEach(function(btn) {{
      if (btn.dataset.bound === '1') return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', function() {{
        const targetId = btn.getAttribute('data-copy-target');
        const pre = document.getElementById(targetId);
        if (!pre || !window.previewBridge) return;
        window.previewBridge.copyText(pre.innerText);
        btn.textContent = {copied_label!r};
        setTimeout(function() {{
          btn.textContent = {copy_label!r};
        }}, 1200);
      }});
    }});
  }}

  function bindCheckboxes() {{
    document.querySelectorAll('input[type="checkbox"]').forEach(function(cb, index) {{
      cb.removeAttribute('disabled');
      if (cb.dataset.bound === '1') return;
      cb.dataset.bound = '1';
      cb.addEventListener('change', function() {{
        if (!window.previewBridge) return;
        window.previewBridge.toggleCheckbox(index, cb.checked);
      }});
    }});
  }}

  function bindLinks() {{
    document.querySelectorAll('a[href]').forEach(function(link) {{
      if (link.dataset.boundLinkCopy === '1') return;
      link.dataset.boundLinkCopy = '1';
      link.addEventListener('click', function(event) {{
        if (link.protocol === 'file:') {{
          event.preventDefault();
          event.stopPropagation();
          if (event.altKey && window.previewBridge) {{
            window.previewBridge.copyText(link.href);
          }}
          return;
        }}
        if (!event.altKey || !window.previewBridge) return;
        event.preventDefault();
        event.stopPropagation();
        window.previewBridge.copyText(link.href);
      }});
    }});
  }}

  window.setPreviewScrollRatio = function(ratio) {{
    const scrollMax = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    window.scrollTo(0, scrollMax * ratio);
  }};

  window.renderPreviewContent = function(html) {{
    const container = document.getElementById('preview-content');
    if (!container) return;
    const template = document.createElement('template');
    template.innerHTML = html;
    reuseExistingImages(template.content, container);
    container.replaceChildren(...Array.from(template.content.childNodes));
    bindCopyButtons();
    bindCheckboxes();
    bindLinks();
  }};

  document.addEventListener('DOMContentLoaded', function() {{
    new QWebChannel(qt.webChannelTransport, function(channel) {{
      window.previewBridge = channel.objects.previewBridge;
      bindCopyButtons();
      bindCheckboxes();
      bindLinks();
    }});
  }});
</script>
"""

    def _show_preview_context_menu(self, pos):
        request = self.preview.lastContextMenuRequest()
        link_url = request.linkUrl() if request is not None else QUrl()
        has_link = link_url.isValid() and not link_url.isEmpty()
        is_image = (
            request is not None
            and request.mediaType() == QWebEngineContextMenuRequest.MediaType.MediaTypeImage
        )

        menu = QMenu(self)
        open_link_action = None
        copy_link_action = None
        copy_image_action = None
        if has_link:
            open_link_action = menu.addAction(self._tr("Open Link"))
            copy_link_action = menu.addAction(self._tr("Copy Link"))
            open_link_action.setEnabled(link_url.scheme().lower() != "file")
            menu.addSeparator()
        if is_image:
            copy_image_action = menu.addAction(self._tr("Copy Image"))
            menu.addSeparator()
        copy_text_action = menu.addAction(self._tr("Copy"))
        chosen = menu.exec(self.preview.mapToGlobal(pos))

        if chosen == open_link_action:
            QDesktopServices.openUrl(link_url)
        elif chosen == copy_link_action:
            QApplication.clipboard().setText(link_url.toString())
        elif chosen == copy_image_action:
            self.preview.triggerPageAction(QWebEnginePage.WebAction.CopyImageToClipboard)
        elif chosen == copy_text_action:
            self.preview.triggerPageAction(QWebEnginePage.WebAction.Copy)

    def _copy_preview_text(self, text):
        QApplication.clipboard().setText(text)

    def _show_preview_link_hover(self, url):
        if url:
            self.statusBar().showMessage(url)
        else:
            self.statusBar().clearMessage()

    def _preview_heading_colors(self, theme_mode=None):
        dark = (theme_mode or self.theme_mode) == "dark"
        return {
            1: "#93c5fd" if dark else "#1d4ed8",
            2: "#7dd3fc" if dark else "#2563eb",
            3: "#5eead4" if dark else "#0f766e",
            4: "#c4b5fd" if dark else "#7c3aed",
        }

    def _style_headings(self, html, theme_mode=None):
        heading_colors = self._preview_heading_colors(theme_mode=theme_mode)
        heading_styles = {
            "h1": "font-size: 24px; font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif; "
                  f"font-weight: 700; color: {heading_colors[1]}; margin-top: 1.2em; margin-bottom: 0.3em;",
            "h2": "font-size: 20px; font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif; "
                  f"font-weight: 700; color: {heading_colors[2]}; margin-top: 1.1em; margin-bottom: 0.25em;",
            "h3": "font-size: 18px; font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif; "
                  f"font-weight: 700; color: {heading_colors[3]}; margin-top: 1em; margin-bottom: 0.2em;",
            "h4": "font-size: 17px; font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif; "
                  f"font-weight: 600; color: {heading_colors[4]}; margin-top: 0.9em; margin-bottom: 0.2em;",
        }

        for tag, style in heading_styles.items():
            html = re.sub(
                rf"<{tag}>(.*?)</{tag}>",
                rf'<p style="{style}">\1</p>',
                html,
                flags=re.DOTALL,
            )
        return html

    def _style_code_blocks(self, html, interactive=False):
        """Wrap fenced code blocks in Qt-friendly markup with reliable padding."""
        def replace_code_block(match):
            code_content = match.group(1)
            pre_id = f"code-block-{uuid.uuid4().hex}"
            button_html = ""
            wrapper_style = (
                'margin: 1.5em 0; border: 1px solid #6b7280; '
                'background: #4b5563; border-radius: 4px; padding: 14px 18px;'
            )
            if interactive:
                button_html = (
                    f'<button class="copy-btn" data-copy-target="{pre_id}" type="button">'
                    f'{self._tr("Copy")}</button>'
                )
            return (
                f'<div class="code-wrapper" style="{wrapper_style}">'
                f'{button_html}'
                f'<pre id="{pre_id}" style="margin: 0; white-space: pre-wrap; '
                'font-family: \'Courier New\', Courier, monospace; '
                'font-size: 0.88em; line-height: 1.45; color: #f8fafc;">'
                f'{code_content}'
                '</pre>'
                '</div>'
            )

        return re.sub(
            r'<pre><code(?: class="[^"]*")?>(.*?)</code></pre>',
            replace_code_block,
            html,
            flags=re.DOTALL,
        )

    def export_pdf(self):
        """Export current document to PDF."""
        suggested_name = self._suggest_filename_from_heading()
        default_path = os.path.join(self.workspace_dir or "", suggested_name + ".pdf")
        path, _ = QFileDialog.getSaveFileName(
            self, self._tr("Export as PDF"), default_path, self._tr("PDF Files (*.pdf)")
        )
        if not path:
            return
        if not path.endswith(".pdf"):
            path += ".pdf"

        html = self._build_preview_html(theme_mode="light") + self._pdf_typography_assets()
        html = self._embed_images_as_base64(html)

        self._pdf_path = path
        self._web_view = QWebEngineView()
        self._configure_web_view_security(self._web_view)
        self._web_view.loadFinished.connect(self._on_page_loaded)
        self._web_view.setHtml(html, QUrl("about:blank"))

    def _on_page_loaded(self, ok):
        if not ok:
            self.statusBar().showMessage(self._tr("PDF export failed"), 3000)
            self._web_view = None
            return

        self._web_view.page().pdfPrintingFinished.connect(self._on_pdf_done)
        page_layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(15, 15, 15, 15))
        self._web_view.page().printToPdf(self._pdf_path, page_layout)

    def _on_pdf_done(self, path, success):
        if success:
            self.statusBar().showMessage(self._tr("PDF exported"), 3000)
        else:
            self.statusBar().showMessage(self._tr("PDF export failed"), 3000)
        self._web_view = None


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("testlog.editor")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setWindowIcon(multi_icon_from_svg(APP_ICON_SVG))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
