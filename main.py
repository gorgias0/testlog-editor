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
    QToolBar
)
from PySide6.QtCore import Qt, QTimer, QDir, QMarginsF, QUrl, QSettings
from PySide6.QtGui import QImage, QAction, QPageLayout, QPageSize
from PySide6.QtWebEngineWidgets import QWebEngineView
from markdown_it import MarkdownIt
from styles import PREVIEW_STYLE


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
        elif event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._handle_tab()
            return
        elif event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            self._handle_shift_tab()
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("TestLog Editor", "TestLog Editor")
        self.setWindowTitle("TestLog Editor")
        self.resize(1400, 800)

        self.current_file = None
        self.workspace_dir = None
        self.md_parser = MarkdownIt().enable("table")
        self._new_session()

        self._setup_ui()
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self._setup_menu()
        self._load_last_workspace()

    def _new_session(self):
        self.session_dir = f"/tmp/testlog_{uuid.uuid4().hex[:8]}"
        self.images_dir = os.path.join(self.session_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

    def _load_last_workspace(self):
        path = self.settings.value("last_workspace", "", type=str)
        if path and os.path.isdir(path):
            self._set_workspace(path)

    def _set_workspace(self, path):
        self.workspace_dir = path
        self.fs_model.setRootPath(path)
        root_index = self.fs_model.index(path)
        if root_index.isValid():
            self.tree.setRootIndex(root_index)
            self.tree.update()
            self.setWindowTitle(f"TestLog Editor – {os.path.basename(path)}")
            self.statusBar().showMessage(f"Arbetsyta öppnad: {path}", 3000)
            self.settings.setValue("last_workspace", path)

    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Arkiv")

        new_action = QAction("Ny", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)

        open_action = QAction("Öppna...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)

        edit_menu = menubar.addMenu("Redigera")
        undo_action = QAction("Ångra", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.editor.undo)
        redo_action = QAction("Gör om", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self.editor.redo)

        edit_menu.addAction(undo_action)
        edit_menu.addAction(redo_action)

        open_workspace = QAction("Öppna arbetsyta...", self)
        open_workspace.triggered.connect(self.open_workspace)

        save_action = QAction("Spara", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)

        save_as_action = QAction("Spara som...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_file_as)

        export_pdf_action = QAction("Exportera som PDF...", self)
        export_pdf_action.triggered.connect(self.export_pdf)

        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addAction(open_workspace)
        file_menu.addSeparator()
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addAction(export_pdf_action)

        toolbar = QToolBar("Formatering")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        bold_action = QAction("B", self)
        bold_action.setToolTip("Fetstil (Ctrl+B)")
        bold_action.triggered.connect(self.editor.format_bold)
        toolbar.addAction(bold_action)

        italic_action = QAction("I", self)
        italic_action.setToolTip("Kursiv (Ctrl+I)")
        italic_action.triggered.connect(self.editor.format_italic)
        toolbar.addAction(italic_action)

        inline_code_action = QAction("****", self)
        inline_code_action.setToolTip("Inline-kod (`)")
        inline_code_action.triggered.connect(self.editor.format_inline_code)
        toolbar.addAction(inline_code_action)

        code_block_action = QAction("```", self)
        code_block_action.setToolTip("Kodblock (Ctrl+Shift+K)")
        code_block_action.triggered.connect(self.editor.format_code_block)
        toolbar.addAction(code_block_action)

        toolbar.addSeparator()

        h1_action = QAction("H1", self)
        h1_action.setToolTip("Rubrik 1")
        h1_action.triggered.connect(lambda: self._insert_line_prefix("# "))
        toolbar.addAction(h1_action)

        h2_action = QAction("H2", self)
        h2_action.setToolTip("Rubrik 2")
        h2_action.triggered.connect(lambda: self._insert_line_prefix("## "))
        toolbar.addAction(h2_action)

        h3_action = QAction("H3", self)
        h3_action.setToolTip("Rubrik 3")
        h3_action.triggered.connect(lambda: self._insert_line_prefix("### "))
        toolbar.addAction(h3_action)

        toolbar.addSeparator()

        bullet_action = QAction("-", self)
        bullet_action.setToolTip("Lista")
        bullet_action.triggered.connect(lambda: self._insert_line_prefix("- "))
        toolbar.addAction(bullet_action)

        numbered_action = QAction("1.", self)
        numbered_action.setToolTip("Numrerad lista")
        numbered_action.triggered.connect(lambda: self._insert_line_prefix("1. "))
        toolbar.addAction(numbered_action)

        quote_action = QAction('"', self)
        quote_action.setToolTip("Blockquote")
        quote_action.triggered.connect(lambda: self._insert_line_prefix("> "))
        toolbar.addAction(quote_action)

        hr_action = QAction("─", self)
        hr_action.setToolTip("Horisontell linje")
        hr_action.triggered.connect(self._insert_horizontal_rule)
        toolbar.addAction(hr_action)

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

        self.fs_model = QFileSystemModel()
        self.fs_model.setNameFilters(["*.testlog"])
        self.fs_model.setNameFilterDisables(True)  # Visar mappar, gråar ut andra filer
        self.fs_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setHeaderHidden(True)
        # Dölj kolumner utom namn
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.clicked.connect(self.tree_item_clicked)
        sidebar_layout.addWidget(self.tree)

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

        self.inner_splitter.addWidget(self.editor)
        self.inner_splitter.addWidget(self.preview)
        self.inner_splitter.setSizes([550, 550])

        self.outer_splitter.addWidget(sidebar)
        self.outer_splitter.addWidget(self.inner_splitter)
        self.outer_splitter.setSizes([220, 1100])

        self.setCentralWidget(self.outer_splitter)

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
        self.autosave_timer.setInterval(5000)
        self.autosave_timer.timeout.connect(self.autosave)

        self.editor.textChanged.connect(self.timer.start)
        self.editor.textChanged.connect(self.autosave_timer.start)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("outer_splitter", self.outer_splitter.saveState())
        self.settings.setValue("inner_splitter", self.inner_splitter.saveState())
        super().closeEvent(event)

    def _insert_line_prefix(self, prefix):
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(cursor.MoveOperation.StartOfLine)
        line_text = cursor.block().text()

        if line_text.startswith(prefix):
            for _ in range(len(prefix)):
                cursor.deleteChar()
        else:
            cursor.insertText(prefix)

        cursor.endEditBlock()
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _insert_horizontal_rule(self):
        cursor = self.editor.textCursor()
        cursor.insertText("\n---\n")
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def open_workspace(self):
        path = QFileDialog.getExistingDirectory(self, "Välj arbetsyta")
        if not path:
            return
        print(f"Vald sökväg: {path}")
        self._set_workspace(path)

    def new_file_in_workspace(self):
        if not self.workspace_dir:
            QFileDialog.getExistingDirectory(self, "Välj arbetsyta först")
            return
        name, ok = QInputDialog.getText(self, "Ny fil", "Filnamn (utan .testlog):")
        if not ok or not name.strip():
            return
        path = os.path.join(self.workspace_dir, name.strip() + ".testlog")
        self.current_file = path
        self._new_session()
        self.editor.clear()
        self.save_file()
        self.setWindowTitle(f"TestLog Editor – {name.strip()}.testlog")

    def new_folder_in_workspace(self):
        if not self.workspace_dir:
            return
        name, ok = QInputDialog.getText(self, "Ny mapp", "Mappnamn:")
        if not ok or not name.strip():
            return
        os.makedirs(os.path.join(self.workspace_dir, name.strip()), exist_ok=True)

    def tree_item_clicked(self, index):
        path = self.fs_model.filePath(index)
        if path.endswith(".testlog"):
            self.open_testlog(path)

    def handle_image_paste(self, image: QImage):
        filename = f"screenshot-{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(self.images_dir, filename)
        image.save(filepath, "PNG")
        cursor = self.editor.textCursor()
        cursor.insertText(f"\n![{filename}](images/{filename})\n")

    def update_preview(self):
        self.timer.stop()
        html = self._build_preview_html()
        self.preview.setHtml(html)

    def autosave(self):
        self.autosave_timer.stop()
        if not self.current_file:
            return
        self.save_file()
        self.statusBar().showMessage("Autosaved", 2000)

    def new_file(self):
        self.editor.clear()
        self.current_file = None
        self._new_session()
        self.setWindowTitle("TestLog Editor")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Öppna testlog", "", "TestLog Files (*.testlog)"
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
        self.setWindowTitle(f"TestLog Editor – {os.path.basename(path)}")

    def save_file(self):
        if self.current_file:
            self._write_testlog(self.current_file)
        else:
            self.save_file_as()

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Spara testlog", self.workspace_dir or "", "TestLog Files (*.testlog)"
        )
        if not path:
            return
        if not path.endswith(".testlog"):
            path += ".testlog"
        self.current_file = path
        self._write_testlog(path)
        self.setWindowTitle(f"TestLog Editor – {os.path.basename(path)}")

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
        rendered = self._style_code_blocks(rendered)
        return PREVIEW_STYLE + rendered

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
            self, "Exportera som PDF", default_path, "PDF Files (*.pdf)"
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
            self.statusBar().showMessage("PDF export misslyckades", 3000)
            self._web_view = None
            return

        self._web_view.page().pdfPrintingFinished.connect(self._on_pdf_done)
        page_layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(15, 15, 15, 15))
        self._web_view.page().printToPdf(self._pdf_path, page_layout)

    def _on_pdf_done(self, path, success):
        if success:
            self.statusBar().showMessage("PDF exporterad", 3000)
        else:
            self.statusBar().showMessage("PDF-export misslyckades", 3000)
        self._web_view = None


if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
