import sys
import os
import uuid
import zipfile
import shutil
import re
import base64
from urllib.parse import quote
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter,
    QTextEdit, QFileDialog, QTreeView,
    QFileSystemModel, QWidget, QVBoxLayout,
    QPushButton, QHBoxLayout, QInputDialog,
    QToolBar, QDialog, QStatusBar, QLabel,
    QListWidget, QListWidgetItem, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QDir, QMarginsF, QUrl, QSettings, QDate
from PySide6.QtGui import QImage, QAction, QActionGroup, QPageLayout, QPageSize, QFont
from PySide6.QtWebEngineWidgets import QWebEngineView
from markdown_it import MarkdownIt
from styles import PREVIEW_STYLE

TRANSLATIONS = {
    "sv": {
        "File": "Arkiv",
        "Edit": "Redigera",
        "Format": "Format",
        "Language": "Språk",
        "New": "Ny",
        "Open...": "Öppna...",
        "Open Workspace...": "Öppna arbetsyta...",
        "Save": "Spara",
        "Save As...": "Spara som...",
        "Export as PDF...": "Exportera som PDF...",
        "Quit": "Avsluta",
        "Undo": "Ångra",
        "Redo": "Gör om",
        "Copy Line": "Kopiera rad",
        "Cut Line": "Klipp ut rad",
        "Duplicate Line/Block": "Duplicera rad/block",
        "Move Line/Block Up": "Flytta rad/block upp",
        "Move Line/Block Down": "Flytta rad/block ned",
        "Bold": "Fetstil",
        "Italic": "Kursiv",
        "Underline": "Understruken",
        "Inline Code": "Inline-kod",
        "Code Block": "Kodblock",
        "Heading 1": "Rubrik 1",
        "Heading 2": "Rubrik 2",
        "Heading 3": "Rubrik 3",
        "Heading 4": "Rubrik 4",
        "Bullet List": "Lista",
        "Numbered List": "Numrerad lista",
        "Blockquote": "Blockquote",
        "Horizontal Rule": "Horisontell linje",
        "Insert Date": "Infoga datum",
        "Date": "Datum",
        "Formatting": "Formatering",
        "+ New File": "+ Ny fil",
        "+ Folder": "+ Mapp",
        "Write Markdown here...": "Skriv Markdown här...",
        "Workspace opened: {path}": "Arbetsyta öppnad: {path}",
        "Select workspace": "Välj arbetsyta",
        "Select workspace first": "Välj arbetsyta först",
        "New file": "Ny fil",
        "Filename (without .testlog):": "Filnamn (utan .testlog):",
        "New folder": "Ny mapp",
        "Folder name:": "Mappnamn:",
        "Open testlog": "Öppna testlog",
        "TestLog Files (*.testlog)": "TestLog Files (*.testlog)",
        "Save testlog": "Spara testlog",
        "PDF Files (*.pdf)": "PDF Files (*.pdf)",
        "Export as PDF": "Exportera som PDF",
        "PDF export failed": "PDF export misslyckades",
        "PDF exported": "PDF exporterad",
        "Autosaved": "Autosparad",
        "Bold (Ctrl+B)": "Fetstil (Ctrl+B)",
        "Italic (Ctrl+I)": "Kursiv (Ctrl+I)",
        "Underline tooltip": "Understruken",
        "Inline code (`)": "Inline-kod (`)",
        "Code block (Ctrl+Shift+K)": "Kodblock (Ctrl+Shift+K)",
        "Heading 1 (Ctrl+1)": "Rubrik 1 (Ctrl+1)",
        "Heading 2 (Ctrl+2)": "Rubrik 2 (Ctrl+2)",
        "Heading 3 (Ctrl+3)": "Rubrik 3 (Ctrl+3)",
        "Heading 4 (Ctrl+4)": "Rubrik 4 (Ctrl+4)",
        "Insert date (Ctrl+Alt+D)": "Infoga datum (Ctrl+Alt+D)",
        "TestLog Editor": "TestLog Editor",
        "English": "Engelska",
        "Swedish": "Svenska",
        "Text Tool": "Textverktyg",
        "Paste text here...": "Klistra in text här...",
        "Characters: {with_ws} | Without whitespace: {without_ws}": "Tecken: {with_ws} | Utan blanksteg: {without_ws}",
        "Editor Count: {with_ws} | No ws: {without_ws} | Selected: {sel_with_ws} | Selected no ws: {sel_without_ws}":
            "Editor: {with_ws} | Utan blanksteg: {without_ws} | Markerat: {sel_with_ws} | Markerat utan blanksteg: {sel_without_ws}",
        "Generate Lorem": "Generera Lorem",
        "Copy All": "Kopiera allt",
        "Clear": "Rensa",
        "Pinned Files": "Fästa filer",
        "Rename": "Byt namn",
        "Delete": "Ta bort",
        "Pin to Top": "Fäst högst upp",
        "Unpin": "Ta bort fästning",
        "Move To...": "Flytta till...",
        "Delete Folder {filename}? This cannot be undone.": "Ta bort mappen {filename}? Detta går inte att ångra.",
        "Delete {filename}? This cannot be undone.": "Ta bort {filename}? Detta går inte att ångra.",
        "Confirm Delete": "Bekräfta borttagning",
        "Move Item": "Flytta objekt",
    }
}


class WorkspaceFileSystemModel(QFileSystemModel):
    def __init__(self, pinned_paths=None, parent=None):
        super().__init__(parent)
        self.pinned_paths = pinned_paths if pinned_paths is not None else set()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and index.column() == 0:
            path = self.filePath(index)
            if path.endswith(".testlog"):
                name = Path(path).stem
                if path in self.pinned_paths:
                    return f"📌 {name}"
                return name
        return super().data(index, role)


class Editor(QTextEdit):
    def __init__(self, on_image_paste):
        super().__init__()
        self.on_image_paste = on_image_paste

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = QImage(source.imageData())
            self.on_image_paste(image)
        else:
            super().insertFromMimeData(source)

    def keyPressEvent(self, event):
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
        elif event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
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

    def _handle_smart_enter(self):
        cursor = self.textCursor()
        block = cursor.block()
        line_text = block.text()
        doc = self.document()
        is_last_line = block.blockNumber() == doc.blockCount() - 1

        # Check for bullet list
        if re.match(r'^-\s+', line_text):
            if line_text.strip() == '-':
                # Empty list item, exit list mode
                cursor.movePosition(cursor.MoveOperation.StartOfLine)
                cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                self.setTextCursor(cursor)
                if not is_last_line:
                    cursor.insertText('\n')
            else:
                # Continue list
                cursor.movePosition(cursor.MoveOperation.EndOfLine)
                self.setTextCursor(cursor)
                cursor.insertText('\n- ')
            return

        # Check for numbered list
        match = re.match(r'^(\d+)\.\s+', line_text)
        if match:
            num = int(match.group(1))
            if line_text.strip() == f'{num}.':
                # Empty numbered item, exit list mode
                cursor.movePosition(cursor.MoveOperation.StartOfLine)
                cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                self.setTextCursor(cursor)
                if not is_last_line:
                    cursor.insertText('\n')
            else:
                # Continue numbered list
                cursor.movePosition(cursor.MoveOperation.EndOfLine)
                self.setTextCursor(cursor)
                cursor.insertText(f'\n{num + 1}. ')
            return

        # Default behavior - use super with a synthetic Return key event
        from PySide6.QtGui import QKeyEvent
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        super().keyPressEvent(event)

    def _handle_tab(self):
        cursor = self.textCursor()
        block = cursor.block()
        line_text = block.text()

        if line_text.startswith('- '):
            # Indent list item
            cursor.movePosition(cursor.MoveOperation.StartOfLine)
            self.setTextCursor(cursor)
            cursor.insertText('  ')
        else:
            # Default tab
            cursor.insertText('    ')

    def _handle_shift_tab(self):
        cursor = self.textCursor()
        block = cursor.block()
        line_text = block.text()

        # Remove up to 2 spaces from start of line
        cursor.movePosition(cursor.MoveOperation.StartOfLine)
        self.setTextCursor(cursor)
        spaces_to_remove = 0
        if line_text.startswith('  '):
            spaces_to_remove = 2
        elif line_text.startswith(' '):
            spaces_to_remove = 1

        for _ in range(spaces_to_remove):
            cursor.deleteChar()

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
        self.setTextCursor(cursor)

    def copy_line(self):
        line_text, _ = self._selected_line_range()
        QApplication.clipboard().setText(line_text)

    def cut_line(self):
        line_text, (start_pos, end_pos) = self._selected_line_range()
        QApplication.clipboard().setText(line_text)

        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(start_pos)
        cursor.setPosition(end_pos, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def move_lines_up(self):
        self._move_selected_lines(-1)

    def move_lines_down(self):
        self._move_selected_lines(1)

    def duplicate_lines_down(self):
        text, (_, end_pos) = self._selected_line_range()
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
        text, (start_pos, end_pos) = self._selected_line_range()
        doc = self.document()

        start_block = doc.findBlock(start_pos)
        end_lookup_pos = max(start_pos, end_pos - 1)
        end_block = doc.findBlock(end_lookup_pos)

        if direction < 0:
            previous_block = start_block.previous()
            if not previous_block.isValid():
                return
            swap_start = previous_block.position()
            before_text = previous_block.text()
            moved_text = before_text + "\n" + text
            insert_text = text + "\n" + before_text
            selection_start = swap_start
        else:
            next_block = end_block.next()
            if not next_block.isValid():
                return
            swap_end = next_block.position() + len(next_block.text())
            if next_block.blockNumber() < doc.blockCount() - 1:
                swap_end += 1
            after_text = next_block.text()
            moved_text = text + "\n" + after_text
            insert_text = after_text + "\n" + text
            selection_start = start_pos + len(after_text) + 1

        cursor = self.textCursor()
        cursor.beginEditBlock()

        if direction < 0:
            cursor.setPosition(swap_start)
            cursor.setPosition(end_pos, cursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(start_pos)
            cursor.setPosition(swap_end, cursor.MoveMode.KeepAnchor)

        if cursor.selectedText().replace("\u2029", "\n") != moved_text:
            cursor.endEditBlock()
            return

        cursor.removeSelectedText()
        cursor.insertText(insert_text)

        new_cursor = self.textCursor()
        new_cursor.setPosition(selection_start)
        new_cursor.setPosition(selection_start + len(text), new_cursor.MoveMode.KeepAnchor)
        self.setTextCursor(new_cursor)

        cursor.endEditBlock()


class TextToolDialog(QDialog):
    def __init__(self, translate, parent=None):
        super().__init__(parent)
        self._tr = translate
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        self.text_area = QTextEdit()
        self.status_bar = QStatusBar()
        self.generate_lorem_action = QAction(self)
        self.generate_lorem_action.triggered.connect(self._generate_lorem_text)
        self.copy_all_action = QAction(self)
        self.copy_all_action.triggered.connect(self._copy_all_text)
        self.clear_action = QAction(self)
        self.clear_action.triggered.connect(self.text_area.clear)

        self.toolbar.addAction(self.generate_lorem_action)
        self.toolbar.addAction(self.copy_all_action)
        self.toolbar.addAction(self.clear_action)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.text_area)
        layout.addWidget(self.status_bar)

        self.text_area.textChanged.connect(self._update_counts)
        self.retranslate_ui()
        self._update_counts()

    def retranslate_ui(self):
        self.setWindowTitle(self._tr("Text Tool"))
        self.text_area.setPlaceholderText(self._tr("Paste text here..."))
        self.generate_lorem_action.setText(self._tr("Generate Lorem"))
        self.copy_all_action.setText(self._tr("Copy All"))
        self.clear_action.setText(self._tr("Clear"))
        self._update_counts()

    def _update_counts(self):
        text = self.text_area.toPlainText()
        without_whitespace = "".join(ch for ch in text if not ch.isspace())
        self.status_bar.showMessage(
            self._tr("Characters: {with_ws} | Without whitespace: {without_ws}").format(
                with_ws=len(text),
                without_ws=len(without_whitespace),
            )
        )

    def _generate_lorem_text(self):
        paragraphs = [
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer posuere erat a ante venenatis dapibus posuere velit aliquet.",
            "Praesent commodo cursus magna, vel scelerisque nisl consectetur et. Donec sed odio dui.",
            "Nullam id dolor id nibh ultricies vehicula ut id elit. Cras mattis consectetur purus sit amet fermentum.",
            "Aenean lacinia bibendum nulla sed consectetur. Maecenas faucibus mollis interdum.",
            "Vestibulum id ligula porta felis euismod semper. Sed posuere consectetur est at lobortis.",
            "Etiam porta sem malesuada magna mollis euismod. Curabitur blandit tempus porttitor.",
            "Morbi leo risus, porta ac consectetur ac, vestibulum at eros. Sed posuere consectetur est at lobortis.",
            "Donec ullamcorper nulla non metus auctor fringilla. Nulla vitae elit libero, a pharetra augue.",
            "Vivamus sagittis lacus vel augue laoreet rutrum faucibus dolor auctor. Integer posuere erat a ante venenatis dapibus.",
            "Cras justo odio, dapibus ac facilisis in, egestas eget quam. Donec ullamcorper nulla non metus auctor fringilla.",
        ]
        self.text_area.setPlainText("START\n\n" + "\n\n".join(paragraphs) + "\n\nEND")

    def _copy_all_text(self):
        QApplication.clipboard().setText(self.text_area.toPlainText())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("TestLog Editor", "TestLog Editor")
        self.current_language = self.settings.value("language", self._default_language(), type=str)
        self.setWindowTitle("TestLog Editor")
        self.resize(1400, 800)

        self.current_file = None
        self.workspace_dir = None
        self.text_tool_dialog = None
        self.pinned_files = self._load_pinned_files()
        self.pinned_paths = set(self.pinned_files)
        self._syncing_scrollbars = False
        self.md_parser = MarkdownIt().enable("table")
        self._new_session()

        self._setup_ui()
        self.refresh_pinned()
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self._setup_menu()
        self._setup_toolbar()
        self._retranslate_ui()
        self._load_last_workspace()

    def _default_language(self):
        return "sv" if os.environ.get("LANG", "").lower().startswith("sv") else "en"

    def _tr(self, text):
        return TRANSLATIONS.get(self.current_language, {}).get(text, text)

    def _window_title(self, filename=None):
        base = self._tr("TestLog Editor")
        if filename:
            return f"{base} - {filename}"
        return base

    def _set_language(self, language_code):
        if language_code == self.current_language:
            return
        self.current_language = language_code
        self.settings.setValue("language", language_code)
        self._retranslate_ui()

    def _new_session(self):
        self.session_dir = f"/tmp/testlog_{uuid.uuid4().hex[:8]}"
        self.images_dir = os.path.join(self.session_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

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

    def _set_workspace(self, path):
        self.workspace_dir = path
        self.fs_model.setRootPath(path)
        root_index = self.fs_model.index(path)
        if root_index.isValid():
            self.tree.setRootIndex(root_index)
            self.tree.update()
            self.setWindowTitle(self._window_title(os.path.basename(path)))
            self.statusBar().showMessage(self._tr("Workspace opened: {path}").format(path=path), 3000)
            self.settings.setValue("last_workspace", path)
            self._open_most_recent_testlog()

    def _setup_menu(self):
        menubar = self.menuBar()
        self.file_menu = menubar.addMenu("")
        self.edit_menu = menubar.addMenu("")
        self.format_menu = menubar.addMenu("")
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
        self.copy_line_action.setShortcut("Ctrl+C")
        self.copy_line_action.triggered.connect(self.editor.copy_line)
        self.cut_line_action = QAction(self)
        self.cut_line_action.setShortcut("Ctrl+X")
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
        self.bullet_list_action.triggered.connect(lambda: self._insert_line_prefix("- "))
        self.numbered_list_action = QAction(self)
        self.numbered_list_action.triggered.connect(lambda: self._insert_line_prefix("1. "))
        self.blockquote_action = QAction(self)
        self.blockquote_action.triggered.connect(lambda: self._insert_line_prefix("> "))
        self.horizontal_rule_action = QAction(self)
        self.horizontal_rule_action.triggered.connect(self._insert_horizontal_rule)
        self.date_menu_action = QAction(self)
        self.date_menu_action.setShortcut("Ctrl+Alt+D")
        self.date_menu_action.triggered.connect(self.editor.insert_current_date)

        self.open_workspace_action = QAction(self)
        self.open_workspace_action.triggered.connect(self.open_workspace)

        self.save_action = QAction(self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_file)

        self.save_as_action = QAction(self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_file_as)

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
        self.format_menu.addSeparator()
        self.format_menu.addAction(self.date_menu_action)

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
        self.toolbar.setStyleSheet(
            "QToolBar { spacing: 4px; padding: 4px; }"
            "QToolButton { min-width: 34px; min-height: 30px; font-size: 13px; padding: 4px 8px; }"
            "QToolBar::separator { background: #b8b8b8; width: 1px; margin: 4px 8px; }"
        )
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

        self.toolbar.addSeparator()

        self.toolbar_inline_code_action = QAction(self)
        self.toolbar_inline_code_action.triggered.connect(self.editor.format_inline_code)
        self.toolbar.addAction(self.toolbar_inline_code_action)

        self.toolbar_code_block_action = QAction(self)
        self.toolbar_code_block_action.triggered.connect(self.editor.format_code_block)
        self.toolbar.addAction(self.toolbar_code_block_action)

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

        self.toolbar_quote_action = QAction(self)
        self.toolbar_quote_action.triggered.connect(lambda: self._insert_line_prefix("> "))
        self.toolbar.addAction(self.toolbar_quote_action)

        self.toolbar.addSeparator()

        self.toolbar_hr_action = QAction(self)
        self.toolbar_hr_action.triggered.connect(self._insert_horizontal_rule)
        self.toolbar.addAction(self.toolbar_hr_action)

        self.toolbar.addSeparator()

        self.toolbar_date_action = QAction(self)
        self.toolbar_date_action.triggered.connect(self.editor.insert_current_date)
        self.toolbar.addAction(self.toolbar_date_action)

    def _retranslate_ui(self):
        self.file_menu.setTitle(self._tr("File"))
        self.edit_menu.setTitle(self._tr("Edit"))
        self.format_menu.setTitle(self._tr("Format"))
        self.language_menu.setTitle(self._tr("Language"))

        self.new_action.setText(self._tr("New"))
        self.open_action.setText(self._tr("Open..."))
        self.open_workspace_action.setText(self._tr("Open Workspace..."))
        self.save_action.setText(self._tr("Save"))
        self.save_as_action.setText(self._tr("Save As..."))
        self.export_pdf_action.setText(self._tr("Export as PDF..."))
        self.quit_action.setText(self._tr("Quit"))

        self.undo_action.setText(self._tr("Undo"))
        self.redo_action.setText(self._tr("Redo"))
        self.copy_line_action.setText(self._tr("Copy Line"))
        self.cut_line_action.setText(self._tr("Cut Line"))
        self.duplicate_lines_action.setText(self._tr("Duplicate Line/Block"))
        self.move_lines_up_action.setText(self._tr("Move Line/Block Up"))
        self.move_lines_down_action.setText(self._tr("Move Line/Block Down"))

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

        self.english_action.setText(self._tr("English"))
        self.swedish_action.setText(self._tr("Swedish"))
        self.english_action.setChecked(self.current_language == "en")
        self.swedish_action.setChecked(self.current_language == "sv")

        self.toolbar.setWindowTitle(self._tr("Formatting"))
        self.toolbar_bold_action.setText("B")
        self.toolbar_bold_action.setToolTip(self._tr("Bold (Ctrl+B)"))
        self.toolbar_italic_action.setText("I")
        self.toolbar_italic_action.setToolTip(self._tr("Italic (Ctrl+I)"))
        self.toolbar_underline_action.setText("UL")
        self.toolbar_underline_action.setToolTip(self._tr("Underline tooltip"))
        self.toolbar_inline_code_action.setText("****")
        self.toolbar_inline_code_action.setToolTip(self._tr("Inline code (`)"))
        self.toolbar_code_block_action.setText("```")
        self.toolbar_code_block_action.setToolTip(self._tr("Code block (Ctrl+Shift+K)"))
        self.toolbar_h1_action.setText("H1")
        self.toolbar_h1_action.setToolTip(self._tr("Heading 1 (Ctrl+1)"))
        self.toolbar_h2_action.setText("H2")
        self.toolbar_h2_action.setToolTip(self._tr("Heading 2 (Ctrl+2)"))
        self.toolbar_h3_action.setText("H3")
        self.toolbar_h3_action.setToolTip(self._tr("Heading 3 (Ctrl+3)"))
        self.toolbar_h4_action.setText("H4")
        self.toolbar_h4_action.setToolTip(self._tr("Heading 4 (Ctrl+4)"))
        self.toolbar_bullet_action.setText("-")
        self.toolbar_bullet_action.setToolTip(self._tr("Bullet List"))
        self.toolbar_numbered_action.setText("1.")
        self.toolbar_numbered_action.setToolTip(self._tr("Numbered List"))
        self.toolbar_quote_action.setText('"')
        self.toolbar_quote_action.setToolTip(self._tr("Blockquote"))
        self.toolbar_hr_action.setText("─")
        self.toolbar_hr_action.setToolTip(self._tr("Horizontal Rule"))
        self.toolbar_date_action.setText(self._tr("Date"))
        self.toolbar_date_action.setToolTip(self._tr("Insert date (Ctrl+Alt+D)"))

        self.btn_new_file.setText(self._tr("+ New File"))
        self.btn_new_folder.setText(self._tr("+ Folder"))
        self.btn_text_tool.setText(self._tr("Text Tool"))
        self.pinned_label.setText(self._tr("Pinned Files"))
        self.editor.setPlaceholderText(self._tr("Write Markdown here..."))
        self._update_editor_counts()
        self.refresh_pinned()

        title_suffix = os.path.basename(self.current_file) if self.current_file else None
        self.setWindowTitle(self._window_title(title_suffix))
        if hasattr(self, "text_tool_dialog") and self.text_tool_dialog is not None:
            self.text_tool_dialog.retranslate_ui()

    def _setup_ui(self):
        # Yttre splitter: sidebar | höger
        self.outer_splitter = QSplitter(Qt.Horizontal)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        sidebar_layout.setSpacing(4)

        btn_row = QHBoxLayout()
        self.btn_new_file = QPushButton("+ Ny fil")
        self.btn_new_file.clicked.connect(self.new_file_in_workspace)
        self.btn_new_folder = QPushButton("+ Mapp")
        self.btn_new_folder.clicked.connect(self.new_folder_in_workspace)
        btn_row.addWidget(self.btn_new_file)
        btn_row.addWidget(self.btn_new_folder)
        sidebar_layout.addLayout(btn_row)

        self.pinned_section = QWidget()
        pinned_layout = QVBoxLayout(self.pinned_section)
        pinned_layout.setContentsMargins(0, 0, 0, 0)
        pinned_layout.setSpacing(4)
        self.pinned_label = QLabel()
        self.pinned_list = QListWidget()
        self.pinned_list.setMaximumHeight(110)
        self.pinned_list.itemClicked.connect(self.pinned_item_clicked)
        pinned_layout.addWidget(self.pinned_label)
        pinned_layout.addWidget(self.pinned_list)
        sidebar_layout.addWidget(self.pinned_section)

        self.fs_model = WorkspaceFileSystemModel(self.pinned_paths)
        self.fs_model.setNameFilters(["*.testlog"])
        self.fs_model.setNameFilterDisables(True)  # Visar mappar, gråar ut andra filer
        self.fs_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setHeaderHidden(True)
        self.tree.setSortingEnabled(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Dölj kolumner utom namn
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.sortByColumn(3, Qt.SortOrder.DescendingOrder)
        self.tree.clicked.connect(self.tree_item_clicked)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        sidebar_layout.addWidget(self.tree)

        self.btn_text_tool = QPushButton("Text Tool")
        self.btn_text_tool.clicked.connect(self.open_text_tool)
        sidebar_layout.addWidget(self.btn_text_tool)

        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(350)

        # --- Inre splitter: editor | preview ---
        self.inner_splitter = QSplitter(Qt.Horizontal)

        self.editor = Editor(on_image_paste=self.handle_image_paste)
        self.editor.setPlaceholderText("Skriv Markdown här...")
        self.editor.setFontFamily("Monospace")
        self.editor.setFontPointSize(12)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.document().setDocumentMargin(8)
        self.preview.setFont(QFont("Source Sans 3", 17))

        self.inner_splitter.addWidget(self.editor)
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
        self.autosave_timer.setInterval(3000)
        self.autosave_timer.timeout.connect(self.autosave)

        self.editor.textChanged.connect(self.timer.start)
        self.editor.textChanged.connect(self.autosave_timer.start)
        self.editor.textChanged.connect(self._update_editor_counts)
        self.editor.cursorPositionChanged.connect(self._update_editor_counts)
        self.editor.verticalScrollBar().valueChanged.connect(self._sync_preview_scroll)
        self.preview.verticalScrollBar().valueChanged.connect(self._sync_editor_scroll)
        self._update_editor_counts()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("outer_splitter", self.outer_splitter.saveState())
        self.settings.setValue("inner_splitter", self.inner_splitter.saveState())
        super().closeEvent(event)

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

    def refresh_pinned(self):
        valid_paths = [path for path in self.pinned_files if os.path.exists(path)]
        if valid_paths != self.pinned_files:
            self.pinned_files = valid_paths
            self._save_pinned_files()

        self.pinned_paths.clear()
        self.pinned_paths.update(self.pinned_files)

        self.pinned_list.clear()
        for path in self.pinned_files:
            item = QListWidgetItem(Path(path).stem)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.pinned_list.addItem(item)

        has_pins = bool(self.pinned_files)
        self.pinned_section.setVisible(has_pins)
        self.fs_model.layoutChanged.emit()

    def pinned_item_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self.open_testlog(path)

    def show_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return

        path = self.fs_model.filePath(index)
        is_file = path.endswith(".testlog") and os.path.isfile(path)
        is_dir = os.path.isdir(path)
        if not is_file and not is_dir:
            return

        menu = QMenu(self)

        rename_action = menu.addAction(self._tr("Rename"))
        delete_action = menu.addAction(self._tr("Delete"))
        move_action = menu.addAction(self._tr("Move To..."))
        if is_file:
            menu.addSeparator()
            pin_action = menu.addAction(self._tr("Unpin") if path in self.pinned_paths else self._tr("Pin to Top"))
        else:
            pin_action = None

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == rename_action:
            self.rename_item(path)
        elif chosen == delete_action:
            self.delete_item(path)
        elif chosen == move_action:
            self.move_item(path)
        elif chosen == pin_action:
            self.toggle_pin(path)

    def rename_item(self, path):
        current_name = Path(path).name if os.path.isdir(path) else Path(path).stem
        new_name, ok = QInputDialog.getText(
            self,
            self._tr("Rename"),
            self._tr("Filename (without .testlog):"),
            text=current_name,
        )
        if not ok or not new_name.strip():
            return

        new_path = os.path.join(
            os.path.dirname(path),
            new_name.strip() if os.path.isdir(path) else new_name.strip() + ".testlog",
        )
        if new_path == path:
            return

        os.rename(path, new_path)

        self._update_tracked_paths(path, new_path)

        self.refresh_pinned()
        self._select_file_in_tree(new_path)

    def delete_item(self, path):
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
        if self.current_file is None:
            self.editor.clear()
            self.setWindowTitle(self._window_title())

        self.refresh_pinned()

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

        path = self.fs_model.filePath(index)
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
        name, ok = QInputDialog.getText(self, self._tr("New file"), self._tr("Filename (without .testlog):"))
        if not ok or not name.strip():
            return
        target_dir = self._selected_directory_for_new_items()
        path = os.path.join(target_dir, name.strip() + ".testlog")
        self.current_file = path
        self._new_session()
        self.editor.setPlainText(f"# {name.strip()}\n")
        self.save_file()
        self.setWindowTitle(self._window_title(f"{name.strip()}.testlog"))

    def new_folder_in_workspace(self):
        if not self.workspace_dir:
            return
        name, ok = QInputDialog.getText(self, self._tr("New folder"), self._tr("Folder name:"))
        if not ok or not name.strip():
            return
        target_dir = self._selected_directory_for_new_items()
        os.makedirs(os.path.join(target_dir, name.strip()), exist_ok=True)

    def tree_item_clicked(self, index):
        path = self.fs_model.filePath(index)
        if path.endswith(".testlog"):
            self.open_testlog(path)

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
        editor_ratio = self._scroll_ratio(self.editor.verticalScrollBar())
        html = self._build_preview_html()
        self.preview.setHtml(html)
        self._set_scroll_ratio(self.preview.verticalScrollBar(), editor_ratio)

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
        if self._syncing_scrollbars:
            return
        self._sync_scrollbars(self.editor.verticalScrollBar(), self.preview.verticalScrollBar(), value)

    def _sync_editor_scroll(self, value):
        if self._syncing_scrollbars:
            return
        self._sync_scrollbars(self.preview.verticalScrollBar(), self.editor.verticalScrollBar(), value)

    def _sync_scrollbars(self, source_bar, target_bar, value):
        source_max = source_bar.maximum()
        ratio = 0.0 if source_max <= 0 else value / source_max

        self._syncing_scrollbars = True
        try:
            self._set_scroll_ratio(target_bar, ratio)
        finally:
            self._syncing_scrollbars = False

    def _scroll_ratio(self, scrollbar):
        maximum = scrollbar.maximum()
        if maximum <= 0:
            return 0.0
        return scrollbar.value() / maximum

    def _set_scroll_ratio(self, scrollbar, ratio):
        maximum = scrollbar.maximum()
        if maximum <= 0:
            scrollbar.setValue(0)
            return
        scrollbar.setValue(round(maximum * max(0.0, min(1.0, ratio))))

    def autosave(self):
        self.autosave_timer.stop()
        if not self.current_file:
            return
        self.save_file()
        self.statusBar().showMessage(self._tr("Autosaved"), 2000)

    def new_file(self):
        self.editor.clear()
        self.current_file = None
        self._new_session()
        self.setWindowTitle(self._window_title())

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self._tr("Open testlog"), "", self._tr("TestLog Files (*.testlog)")
        )
        if path:
            self.open_testlog(path)

    def open_testlog(self, path):
        shutil.rmtree(self.session_dir, ignore_errors=True)
        self._new_session()

        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(self.session_dir)

        note_path = os.path.join(self.session_dir, "note.md")
        if os.path.exists(note_path):
            with open(note_path, "r", encoding="utf-8") as f:
                self.editor.setPlainText(f.read())

        self.current_file = path
        self.setWindowTitle(self._window_title(os.path.basename(path)))
        self._select_file_in_tree(path)

    def _select_file_in_tree(self, path):
        index = self.fs_model.index(path)
        if not index.isValid():
            return

        self.tree.setCurrentIndex(index)
        self.tree.scrollTo(index)

    def save_file(self):
        if self.current_file:
            self._write_testlog(self.current_file)
        else:
            self.save_file_as()

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self._tr("Save testlog"), self.workspace_dir or "", self._tr("TestLog Files (*.testlog)")
        )
        if not path:
            return
        if not path.endswith(".testlog"):
            path += ".testlog"
        self.current_file = path
        self._write_testlog(path)
        self.setWindowTitle(self._window_title(os.path.basename(path)))

    def _write_testlog(self, path):
        note_content = self.editor.toPlainText()
        note_path = os.path.join(self.session_dir, "note.md")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(note_content)

        # Find all image filenames referenced in the note
        referenced = set(re.findall(r'!\[.*?\]\(images/([^)]+)\)', note_content))

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(note_path, "note.md")
            if os.path.exists(self.images_dir):
                for img in os.listdir(self.images_dir):
                    if img in referenced:
                        img_path = os.path.join(self.images_dir, img)
                        zf.write(img_path, f"images/{img}")

    def _suggest_filename_from_heading(self):
        """Extract first heading from editor to use as filename."""
        text = self.editor.toPlainText()
        match = re.search(r'^#+\s+(.+)$', text, re.MULTILINE)
        if match:
            heading = match.group(1).strip()
            # Remove special characters for filename
            filename = re.sub(r'[^\w\s-]', '', heading)[:100]
            return filename.strip() or "export"
        return "export"

    def _embed_images_as_base64(self, html):
        def replace_src(match):
            path = match.group(1)
            if path.startswith("file://"):
                path = path[7:]
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                ext = os.path.splitext(path)[1].lower().strip(".")
                mime = "image/png" if ext == "png" else f"image/{ext}"
                return f'src="data:{mime};base64,{data}"'
            return match.group(0)

        return re.sub(r'src="([^"]+)"', replace_src, html)

    def _build_preview_html(self):
        md = self.editor.toPlainText()
        md_for_preview = md.replace("](images/", f"]({self.images_dir}/")
        rendered = self.md_parser.render(md_for_preview)
        rendered = self._style_headings(rendered)
        rendered = self._style_code_blocks(rendered)
        return PREVIEW_STYLE + rendered

    def _style_headings(self, html):
        heading_styles = {
            "h1": "font-size: 24px; font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif; "
                  "font-weight: 700; color: #2563eb; margin-top: 1.2em; margin-bottom: 0.3em;",
            "h2": "font-size: 20px; font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif; "
                  "font-weight: 700; color: #2563eb; margin-top: 1.1em; margin-bottom: 0.25em;",
            "h3": "font-size: 18px; font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif; "
                  "font-weight: 700; color: #2563eb; margin-top: 1em; margin-bottom: 0.2em;",
            "h4": "font-size: 17px; font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif; "
                  "font-weight: 600; color: #2563eb; margin-top: 0.9em; margin-bottom: 0.2em;",
        }

        for tag, style in heading_styles.items():
            html = re.sub(
                rf"<{tag}>(.*?)</{tag}>",
                rf'<p style="{style}">\1</p>',
                html,
                flags=re.DOTALL,
            )
        return html

    def _style_code_blocks(self, html):
        """Wrap fenced code blocks in Qt-friendly markup with reliable padding."""
        def replace_code_block(match):
            code_content = match.group(1)
            return (
                '<table width="100%" cellspacing="0" cellpadding="0" '
                'bgcolor="#e0e0e0" '
                'style="margin: 1.5em 0; border: 1px solid #ccc;">'
                '<tr><td bgcolor="#e0e0e0" style="padding: 14px 18px; color: #1a1a1a;">'
                '<pre style="margin: 0; white-space: pre-wrap; '
                'font-family: \'Courier New\', Courier, monospace; '
                'font-size: 0.88em; line-height: 1.45; color: #1a1a1a;">'
                f'{code_content}'
                '</pre>'
                '</td></tr></table>'
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

        html = self._build_preview_html()
        html = self._embed_images_as_base64(html)

        self._pdf_path = path
        self._web_view = QWebEngineView()
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

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
