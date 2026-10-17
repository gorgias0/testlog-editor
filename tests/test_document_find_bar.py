import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QTextEdit

from document_find_bar import DocumentFindBar


def _bar_with_text(text):
    QApplication.instance() or QApplication(sys.argv)
    editor = QTextEdit()
    editor.setPlainText(text)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)
    bar = DocumentFindBar(editor)
    return editor, bar


def _search(bar, term):
    bar.find_input.setText(term)
    bar._run_pending_search()


def test_matches_follow_edits_made_while_the_bar_is_open():
    editor, bar = _bar_with_text("foo foo foo")
    bar.open_bar()
    _search(bar, "foo")
    assert bar.counter_label.text() == "1 / 3"

    cursor = QTextCursor(editor.document())
    cursor.setPosition(4)
    cursor.setPosition(7, QTextCursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(" foo foo")

    bar.find_next()
    bar.find_next()

    assert bar.counter_label.text().endswith("/ 4")
    assert editor.textCursor().selectedText() == "foo"
    assert all(match.selectedText() == "foo" for match in bar.matches)


def test_extending_the_term_stays_on_the_current_match():
    editor, bar = _bar_with_text("foo bar foo")
    bar.open_bar()

    _search(bar, "f")
    assert bar.counter_label.text() == "1 / 2"
    _search(bar, "fo")

    assert bar.counter_label.text() == "1 / 2"
    assert editor.textCursor().selectionStart() == 0
