from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut, QTextCursor, QTextDocument
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QWidget


class DocumentFindBar(QWidget):
    def __init__(
        self,
        editor,
        translate=lambda text: text,
        action_parent=None,
        shortcut_parent=None,
        editor_provider=None,
        apply_highlights=None,
        clear_highlights=None,
        on_match_state_changed=None,
        parent=None,
    ):
        super().__init__(parent)
        self._tr = translate
        self._editor = editor
        self._active_editor = editor
        self._editor_provider = editor_provider
        self._apply_highlights_callback = apply_highlights
        self._clear_highlights_callback = clear_highlights
        self._on_match_state_changed = on_match_state_changed
        self._connected_editors = set()

        self.matches = []
        self.current_index = -1
        self.pending_term = ""
        self.search_generation = 0
        self.search_running = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText(self._tr("Search Document..."))
        self.prev_button = QPushButton("∧")
        self.next_button = QPushButton("∨")
        self.counter_label = QLabel("")
        self.close_button = QPushButton("✕")

        layout.addWidget(self.find_input, 1)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.counter_label)
        layout.addWidget(self.close_button)

        self.setVisible(False)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._run_pending_search)

        self.find_input.textChanged.connect(self._schedule_results)
        self.prev_button.clicked.connect(lambda checked=False: self.find_previous())
        self.next_button.clicked.connect(lambda checked=False: self.find_next())
        self.close_button.clicked.connect(lambda checked=False: self.close_bar())
        self.find_input.installEventFilter(self)

        self._install_shortcuts(action_parent or parent, shortcut_parent or parent)
        self._connect_editor_cursor(self._active_editor)

    def _install_shortcuts(self, action_parent, shortcut_parent):
        if action_parent is not None:
            self.find_action = QAction(action_parent)
            self.find_action.setShortcut(QKeySequence.Find)
            self.find_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.find_action.triggered.connect(lambda checked=False: self.open_bar())
            action_parent.addAction(self.find_action)

            self.find_next_action = QAction(action_parent)
            self.find_next_action.setShortcut("Ctrl+G")
            self.find_next_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.find_next_action.triggered.connect(lambda checked=False: self.find_next())
            action_parent.addAction(self.find_next_action)

        if shortcut_parent is not None:
            self.page_down_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageDown), shortcut_parent)
            self.page_down_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.page_down_shortcut.activated.connect(self._find_next_via_page_key)
            self.page_down_shortcut.setEnabled(False)

            self.page_up_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageUp), shortcut_parent)
            self.page_up_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.page_up_shortcut.activated.connect(self._find_previous_via_page_key)
            self.page_up_shortcut.setEnabled(False)

            self.close_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), shortcut_parent)
            self.close_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.close_shortcut.activated.connect(self.close_bar)
            self.close_shortcut.setEnabled(False)

    def _connect_editor_cursor(self, editor):
        if editor is not None and editor not in self._connected_editors:
            editor.cursorPositionChanged.connect(self.sync_current_match_from_cursor)
            self._connected_editors.add(editor)

    def _current_editor(self):
        editor = self._editor_provider() if self._editor_provider is not None else self._editor
        if editor is None:
            editor = self._active_editor
        if editor is not self._active_editor:
            self._clear_editor_highlights(self._active_editor)
            self._active_editor = editor
            self._connect_editor_cursor(editor)
            self._schedule_results(self.find_input.text())
        return editor

    def retranslate_ui(self):
        self.find_input.setPlaceholderText(self._tr("Search Document..."))
        if not self.matches and self.pending_term:
            self.counter_label.setText(self._tr("No Matches"))

    def open_bar(self, term=None):
        editor = self._current_editor()
        selected_text = ""
        if editor is not None:
            selected_text = editor.textCursor().selectedText().replace("\u2029", "\n")

        self.setVisible(True)
        if hasattr(self, "page_down_shortcut"):
            self.page_down_shortcut.setEnabled(True)
        if hasattr(self, "page_up_shortcut"):
            self.page_up_shortcut.setEnabled(True)
        if hasattr(self, "close_shortcut"):
            self.close_shortcut.setEnabled(True)
        if term is not None:
            self.find_input.setText(term)
        elif selected_text:
            self.find_input.setText(selected_text)
        self.find_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.find_input.selectAll()
        if term is not None:
            self._schedule_results(term)
        elif not selected_text:
            self._schedule_results(self.find_input.text())
        self._notify_match_state_changed()

    def close_bar(self):
        if not self.isVisible():
            return
        editor = self._active_editor
        self.setVisible(False)
        if hasattr(self, "page_down_shortcut"):
            self.page_down_shortcut.setEnabled(False)
        if hasattr(self, "page_up_shortcut"):
            self.page_up_shortcut.setEnabled(False)
        if hasattr(self, "close_shortcut"):
            self.close_shortcut.setEnabled(False)
        self.find_input.clear()
        self.matches = []
        self.current_index = -1
        self.pending_term = ""
        self.search_timer.stop()
        self.counter_label.setText("")
        self._clear_editor_highlights(editor)
        self._notify_match_state_changed()
        if editor is not None:
            editor.setFocus()

    def _schedule_results(self, term):
        term_changed = term != self.pending_term
        self.pending_term = term
        self.search_generation += 1
        if term_changed or not term:
            self._clear_active_match_state(self._active_editor)
        self.search_timer.start()

    def _run_pending_search(self):
        if self.search_running:
            self.search_timer.start()
            return

        self.search_running = True
        generation = self.search_generation
        term = self.pending_term
        editor = self._current_editor()
        self.matches = self._collect_matches(editor, term)
        if not self.matches:
            self.current_index = -1
            self.counter_label.setText(self._tr("No Matches") if term else "")
            self._clear_editor_highlights(editor)
            self.search_running = False
            self._notify_match_state_changed()
            if generation != self.search_generation:
                self.search_timer.start()
            return

        self.current_index = self._best_match_index(editor)
        self._apply_find_highlights(editor)
        self._focus_match(self.current_index)
        self.search_running = False
        self._notify_match_state_changed()
        if generation != self.search_generation:
            self.search_timer.start()

    def _collect_matches(self, editor, term):
        if editor is None or not term:
            return []

        doc = editor.document()
        matches = []
        cursor = QTextCursor(doc)
        while True:
            cursor = doc.find(term, cursor, QTextDocument.FindFlag(0))
            if cursor.isNull():
                break
            matches.append(QTextCursor(cursor))
        return matches

    def _best_match_index(self, editor):
        if editor is None:
            return 0
        cursor_pos = editor.textCursor().selectionStart()
        for index, match in enumerate(self.matches):
            if match.selectionStart() >= cursor_pos:
                return index
        return 0

    def _find_selections(self):
        selections = []
        for index, match in enumerate(self.matches):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(match)
            color = QColor("#A57538") if index == self.current_index else QColor("#3080AA")
            selection.format.setBackground(color)
            selections.append(selection)
        return selections

    def _apply_find_highlights(self, editor):
        selections = self._find_selections()
        if self._apply_highlights_callback is not None:
            self._apply_highlights_callback(editor, selections)
        elif editor is not None:
            editor.setExtraSelections(selections)
        if self.matches:
            self.counter_label.setText(f"{self.current_index + 1} / {len(self.matches)}")

    def _clear_editor_highlights(self, editor):
        if self._clear_highlights_callback is not None:
            self._clear_highlights_callback(editor)
        elif editor is not None:
            editor.setExtraSelections([])

    def _clear_editor_selection(self, editor):
        if editor is None:
            return
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            return
        cursor.clearSelection()
        editor.setTextCursor(cursor)

    def _clear_active_match_state(self, editor):
        if not self.matches and self.current_index < 0:
            return
        self.matches = []
        self.current_index = -1
        self.counter_label.setText("")
        self._clear_editor_highlights(editor)
        self._clear_editor_selection(editor)
        self._notify_match_state_changed()

    def _focus_match(self, index):
        editor = self._current_editor()
        if editor is None or not self.matches:
            return
        self.current_index = index % len(self.matches)
        cursor = QTextCursor(self.matches[self.current_index])
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()
        self._apply_find_highlights(editor)
        self._notify_match_state_changed()

    def find_next(self):
        if not self.isVisible():
            self.open_bar()
            return
        if self.matches:
            self._focus_match(self.current_index + 1)

    def find_previous(self):
        if self.matches:
            self._focus_match(self.current_index - 1)

    def _find_next_via_page_key(self):
        if self.isVisible() and len(self.matches) > 1:
            self.find_next()

    def _find_previous_via_page_key(self):
        if self.isVisible() and len(self.matches) > 1:
            self.find_previous()

    def sync_current_match_from_cursor(self):
        if not self.isVisible() or not self.matches:
            return
        editor = self._current_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        position = cursor.selectionStart()
        for index, match in enumerate(self.matches):
            if match.selectionStart() == position and match.selectionEnd() == cursor.selectionEnd():
                if self.current_index != index:
                    self.current_index = index
                    self._apply_find_highlights(editor)
                    self._notify_match_state_changed()
                return

    def has_active_match(self):
        return self.isVisible() and bool(self.matches) and self.current_index >= 0

    def eventFilter(self, obj, event):
        if obj is self.find_input and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                    self.find_previous()
                else:
                    self.find_next()
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.close_bar()
                return True
        return super().eventFilter(obj, event)

    def _notify_match_state_changed(self):
        if self._on_match_state_changed is not None:
            self._on_match_state_changed()
