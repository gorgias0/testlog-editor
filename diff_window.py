from PySide6.QtCore import Qt, QTimer, QRect, QSize
from PySide6.QtGui import QColor, QTextCursor, QTextFormat, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QMessageBox,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from diff_utils import collect_change_blocks, compute_line_diff_states
from html_tools import pretty_print_html
from json_tools import format_json_best_effort


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class DiffTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._diff_selections = []
        self._gutter_bg = QColor("#eef2f7")
        self._gutter_fg = QColor("#7b8794")
        self._current_line_color = QColor("#eef6ff")
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_line_number_area_width(0)
        self._highlight_current_line()

    def line_number_area_width(self):
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        contents_rect = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(contents_rect.left(), contents_rect.top(), self.line_number_area_width(), contents_rect.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self._gutter_bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(self._gutter_fg)
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    str(block_number + 1),
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self):
        selection = QTextEdit.ExtraSelection()
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        selection.format.setBackground(self._current_line_color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        self.setExtraSelections([selection] + self._diff_selections)

    def set_diff_selections(self, selections):
        self._diff_selections = selections
        self._highlight_current_line()

    def set_chrome_colors(self, gutter_bg, gutter_fg, current_line_color):
        self._gutter_bg = QColor(gutter_bg)
        self._gutter_fg = QColor(gutter_fg)
        self._current_line_color = QColor(current_line_color)
        self.line_number_area.update()
        self.viewport().update()


class DiffWindow(QDialog):
    def __init__(self, translate, palette, editor_font, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self._tr = translate
        self._syncing_scroll = False
        self._change_blocks = []
        self._current_change_index = -1
        self.setWindowTitle(self._tr("Diff"))
        self.resize(1100, 700)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.previous_change_button = QPushButton(self._tr("Previous"))
        self.previous_change_button.clicked.connect(self.go_to_previous_change)
        top_row.addWidget(self.previous_change_button)
        self.next_change_button = QPushButton(self._tr("Next"))
        self.next_change_button.clicked.connect(self.go_to_next_change)
        top_row.addWidget(self.next_change_button)
        self.transform_button = QToolButton(self)
        self.transform_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.transform_menu = QMenu(self.transform_button)
        self.format_json_a_action = self.transform_menu.addAction("")
        self.format_json_a_action.triggered.connect(lambda: self.format_json_pane("a"))
        self.format_json_b_action = self.transform_menu.addAction("")
        self.format_json_b_action.triggered.connect(lambda: self.format_json_pane("b"))
        self.transform_menu.addSeparator()
        self.format_html_a_action = self.transform_menu.addAction("")
        self.format_html_a_action.triggered.connect(lambda: self.format_html_pane("a"))
        self.format_html_b_action = self.transform_menu.addAction("")
        self.format_html_b_action.triggered.connect(lambda: self.format_html_pane("b"))
        self.transform_button.setMenu(self.transform_menu)
        top_row.addWidget(self.transform_button)
        self.save_button = QToolButton(self)
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.save_menu = QMenu(self.save_button)
        self.save_a_action = self.save_menu.addAction("")
        self.save_a_action.triggered.connect(lambda: self.save_pane_as("a"))
        self.save_b_action = self.save_menu.addAction("")
        self.save_b_action.triggered.connect(lambda: self.save_pane_as("b"))
        self.save_both_action = self.save_menu.addAction("")
        self.save_both_action.triggered.connect(self.save_both_as)
        self.save_button.setMenu(self.save_menu)
        top_row.addWidget(self.save_button)
        self.change_counter_label = QLabel("")
        top_row.addWidget(self.change_counter_label)
        self.ignore_whitespace_checkbox = QCheckBox(self._tr("Ignore Whitespace"))
        self.ignore_whitespace_checkbox.toggled.connect(self._schedule_diff_update)
        top_row.addWidget(self.ignore_whitespace_checkbox)
        self.ignore_blank_lines_checkbox = QCheckBox(self._tr("Ignore Blank Lines"))
        self.ignore_blank_lines_checkbox.toggled.connect(self._schedule_diff_update)
        top_row.addWidget(self.ignore_blank_lines_checkbox)
        top_row.addStretch(1)
        self.clear_button = QPushButton(self._tr("Clear"))
        self.clear_button.clicked.connect(self.clear_texts)
        top_row.addWidget(self.clear_button)
        root_layout.addLayout(top_row)

        labels_row = QHBoxLayout()
        self.label_a = QLabel(self._tr("Text A"))
        self.label_b = QLabel(self._tr("Text B"))
        labels_row.addWidget(self.label_a)
        labels_row.addStretch(1)
        labels_row.addWidget(self.label_b)
        root_layout.addLayout(labels_row)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.pane_a = DiffTextEdit()
        self.pane_b = DiffTextEdit()
        self.pane_a.setFont(editor_font)
        self.pane_b.setFont(editor_font)
        self.splitter.addWidget(self.pane_a)
        self.splitter.addWidget(self.pane_b)
        self.splitter.setSizes([550, 550])
        root_layout.addWidget(self.splitter, 1)

        self.diff_timer = QTimer(self)
        self.diff_timer.setSingleShot(True)
        self.diff_timer.setInterval(300)
        self.diff_timer.timeout.connect(self.update_diff)

        self.pane_a.textChanged.connect(self._schedule_diff_update)
        self.pane_b.textChanged.connect(self._schedule_diff_update)
        self.pane_a.verticalScrollBar().valueChanged.connect(self.sync_scroll_a)
        self.pane_b.verticalScrollBar().valueChanged.connect(self.sync_scroll_b)

        self.apply_theme(palette)
        self.retranslate_ui()
        self.update_diff()

    def apply_theme(self, palette):
        self.setStyleSheet(
            f"""
            QDialog, QWidget {{
                background: {palette["window_bg"]};
                color: {palette["text"]};
            }}
            QLabel {{
                color: {palette["muted_text"]};
                font-weight: 600;
            }}
            QPushButton, QToolButton {{
                background: {palette["chrome_bg"]};
                color: {palette["text"]};
                border: 1px solid {palette["panel_border"]};
                padding: 4px 10px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background: {palette["chrome_hover"]};
            }}
            QPlainTextEdit {{
                background: {palette["panel_bg"]};
                color: {palette["text"]};
                border: 1px solid {palette["panel_border"]};
                selection-background-color: #bfdbfe;
            }}
            """
        )
        for editor in (self.pane_a, self.pane_b):
            editor.set_chrome_colors(
                palette["chrome_bg"],
                palette["muted_text"],
                "#313843" if palette["window_bg"] == "#1f232a" else "#eef6ff",
            )
            editor.line_number_area.update()
            editor.viewport().update()

    def retranslate_ui(self):
        self.setWindowTitle(self._tr("Diff"))
        self.previous_change_button.setText(self._tr("Previous"))
        self.next_change_button.setText(self._tr("Next"))
        self.transform_button.setText(self._tr("Transform"))
        self.transform_button.setToolTip(self._tr("Transform"))
        self.save_button.setText(self._tr("Save"))
        self.save_button.setToolTip(self._tr("Save"))
        self.format_json_a_action.setText(self._tr("Format JSON A"))
        self.format_json_b_action.setText(self._tr("Format JSON B"))
        self.format_html_a_action.setText(self._tr("Format HTML A"))
        self.format_html_b_action.setText(self._tr("Format HTML B"))
        self.save_a_action.setText(self._tr("Save Text A As..."))
        self.save_b_action.setText(self._tr("Save Text B As..."))
        self.save_both_action.setText(self._tr("Save Both As..."))
        self.ignore_whitespace_checkbox.setText(self._tr("Ignore Whitespace"))
        self.ignore_blank_lines_checkbox.setText(self._tr("Ignore Blank Lines"))
        self.clear_button.setText(self._tr("Clear"))
        self.label_a.setText(self._tr("Text A"))
        self.label_b.setText(self._tr("Text B"))
        self._update_change_counter()

    def apply_editor_font(self, font):
        self.pane_a.setFont(font)
        self.pane_b.setFont(font)

    def clear_texts(self):
        self.pane_a.clear()
        self.pane_b.clear()
        self.update_diff()

    def format_json_pane(self, pane_name):
        editor = self.pane_a if pane_name == "a" else self.pane_b
        formatted, valid, error = format_json_best_effort(editor.toPlainText())
        editor.setPlainText(formatted)
        if not valid:
            QMessageBox.warning(
                self,
                self._tr("Format JSON"),
                self._tr("Best-effort JSON formatting applied: {error}").format(error=error),
            )

        editor.setFocus()
        self.update_diff()

    def format_html_pane(self, pane_name):
        editor = self.pane_a if pane_name == "a" else self.pane_b
        editor.setPlainText(pretty_print_html(editor.toPlainText()))
        editor.setFocus()
        self.update_diff()

    def _text_save_filters(self):
        return ";;".join([
            self._tr("Text Files (*.txt)"),
            self._tr("JSON Files (*.json)"),
            self._tr("HTML Files (*.html *.htm)"),
            self._tr("Markdown Files (*.md)"),
            self._tr("XML Files (*.xml)"),
            self._tr("CSV Files (*.csv)"),
            self._tr("All Files (*)"),
        ])

    def _combined_save_filters(self):
        return ";;".join([
            self._tr("Text Files (*.txt)"),
            self._tr("Markdown Files (*.md)"),
            self._tr("All Files (*)"),
        ])

    def _extensions_for_save_filter(self, selected_filter):
        filter_extensions = {
            self._tr("JSON Files (*.json)"): (".json",),
            self._tr("HTML Files (*.html *.htm)"): (".html", ".htm"),
            self._tr("Markdown Files (*.md)"): (".md",),
            self._tr("XML Files (*.xml)"): (".xml",),
            self._tr("CSV Files (*.csv)"): (".csv",),
            self._tr("Text Files (*.txt)"): (".txt",),
        }
        return filter_extensions.get(selected_filter, ())

    def _save_text_to_path(self, path, selected_filter, text):
        extensions = self._extensions_for_save_filter(selected_filter)
        if extensions and not path.lower().endswith(extensions):
            path += extensions[0]

        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def save_pane_as(self, pane_name):
        label = "A" if pane_name == "a" else "B"
        editor = self.pane_a if pane_name == "a" else self.pane_b
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            self._tr("Save Text {label} As").format(label=label),
            f"diff-{label.lower()}.txt",
            self._text_save_filters(),
        )
        if not path:
            return

        self._save_text_to_path(path, selected_filter, editor.toPlainText())

    def save_both_as(self):
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            self._tr("Save Both As"),
            "diff.txt",
            self._combined_save_filters(),
        )
        if not path:
            return

        text = "\n".join([
            f"--- {self._tr('Text A')} ---",
            self.pane_a.toPlainText(),
            "",
            f"--- {self._tr('Text B')} ---",
            self.pane_b.toPlainText(),
        ])
        self._save_text_to_path(path, selected_filter, text)

    def _schedule_diff_update(self):
        self.diff_timer.start()

    def _update_change_counter(self):
        total_changes = len(self._change_blocks)
        if total_changes == 0:
            self.change_counter_label.setText(self._tr("No Changes"))
            return
        current_index = self._current_change_index + 1 if self._current_change_index >= 0 else 0
        self.change_counter_label.setText(
            self._tr("Change {current} of {total}").format(
                current=current_index,
                total=total_changes,
            )
        )

    def sync_scroll_a(self, value):
        if not self._syncing_scroll:
            self._syncing_scroll = True
            self.pane_b.verticalScrollBar().setValue(value)
            self._syncing_scroll = False

    def sync_scroll_b(self, value):
        if not self._syncing_scroll:
            self._syncing_scroll = True
            self.pane_a.verticalScrollBar().setValue(value)
            self._syncing_scroll = False

    def _line_selections(self, editor, line_states, color_by_state):
        selections = []
        for line_number, state in enumerate(line_states):
            colors = color_by_state.get(state)
            if colors is None:
                continue
            background_color, foreground_color = colors
            block = editor.document().findBlockByNumber(line_number)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(block)
            selection.cursor.clearSelection()
            selection.format.setBackground(QColor(background_color))
            selection.format.setForeground(QColor(foreground_color))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selections.append(selection)
        return selections

    def _ignore_whitespace_enabled(self):
        return self.ignore_whitespace_checkbox.isChecked()

    def _ignore_blank_lines_enabled(self):
        return self.ignore_blank_lines_checkbox.isChecked()

    def _change_anchor(self, start, end, line_count):
        if line_count <= 0:
            return None
        if start < line_count:
            return start
        if end > 0:
            return min(end - 1, line_count - 1)
        return line_count - 1

    def _scroll_to_line(self, editor, line_number):
        if line_number is None:
            return
        block = editor.document().findBlockByNumber(line_number)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        editor.setTextCursor(cursor)
        editor.centerCursor()

    def _go_to_change(self, index):
        if not self._change_blocks:
            return
        self._current_change_index = index % len(self._change_blocks)
        self._update_change_counter()
        change = self._change_blocks[self._current_change_index]
        self._scroll_to_line(
            self.pane_a,
            self._change_anchor(change["a_start"], change["a_end"], self.pane_a.document().blockCount()),
        )
        self._scroll_to_line(
            self.pane_b,
            self._change_anchor(change["b_start"], change["b_end"], self.pane_b.document().blockCount()),
        )

    def go_to_next_change(self):
        if not self._change_blocks:
            return
        self._go_to_change(self._current_change_index + 1)

    def go_to_previous_change(self):
        if not self._change_blocks:
            return
        if self._current_change_index < 0:
            self._go_to_change(len(self._change_blocks) - 1)
            return
        self._go_to_change(self._current_change_index - 1)

    def set_pane_text(self, pane_name, text):
        if pane_name == "a":
            self.pane_a.setPlainText(text)
            self.pane_a.setFocus()
        else:
            self.pane_b.setPlainText(text)
            self.pane_b.setFocus()
        self.update_diff()

    def update_diff(self):
        lines_a = self.pane_a.toPlainText().splitlines(keepends=False)
        lines_b = self.pane_b.toPlainText().splitlines(keepends=False)
        ignore_whitespace = self._ignore_whitespace_enabled()
        ignore_blank_lines = self._ignore_blank_lines_enabled()
        line_states_a, line_states_b = compute_line_diff_states(
            lines_a,
            lines_b,
            ignore_whitespace=ignore_whitespace,
            ignore_blank_lines=ignore_blank_lines,
        )
        self._change_blocks = collect_change_blocks(
            lines_a,
            lines_b,
            ignore_whitespace=ignore_whitespace,
            ignore_blank_lines=ignore_blank_lines,
        )
        if not self._change_blocks:
            self._current_change_index = -1
        elif self._current_change_index >= len(self._change_blocks):
            self._current_change_index = 0
        self.pane_a.set_diff_selections(
            self._line_selections(
                self.pane_a,
                line_states_a,
                {
                    "replace": ("#fff3cd", "#4a3b00"),
                    "delete": ("#ffd7d7", "#5f1d1d"),
                },
            )
        )
        self.pane_b.set_diff_selections(
            self._line_selections(
                self.pane_b,
                line_states_b,
                {
                    "replace": ("#fff3cd", "#4a3b00"),
                    "insert": ("#d4edda", "#0f5132"),
                },
            )
        )
        self.previous_change_button.setEnabled(bool(self._change_blocks))
        self.next_change_button.setEnabled(bool(self._change_blocks))
        self._update_change_counter()
