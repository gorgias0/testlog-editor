import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from main import Editor


def _app():
    return QApplication.instance() or QApplication(sys.argv)


def _editor_with_cursor_at_end(text, height=120):
    _app()
    editor = Editor(lambda image: None)
    editor.resize(500, height)
    editor.setPlainText(text)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    return editor


def _press_smart_enter(editor):
    editor._handle_smart_enter()
    QApplication.processEvents()
    QApplication.processEvents()


def _select_text(editor, selected_text):
    text = editor.toPlainText()
    start = text.index(selected_text)
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + len(selected_text), QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def test_smart_enter_preserves_space_and_tab_indentation():
    editor = _editor_with_cursor_at_end("  indented")

    _press_smart_enter(editor)

    assert editor.toPlainText() == "  indented\n  "

    editor = _editor_with_cursor_at_end("\tindented")

    _press_smart_enter(editor)

    assert editor.toPlainText() == "\tindented\n\t"


def test_smart_enter_clears_whitespace_only_line_before_newline():
    editor = _editor_with_cursor_at_end("    ")

    _press_smart_enter(editor)

    assert editor.toPlainText() == "\n"


def test_smart_enter_adds_new_empty_line_for_plain_text():
    editor = _editor_with_cursor_at_end("plain text")

    _press_smart_enter(editor)

    assert editor.toPlainText() == "plain text\n"


def test_smart_enter_adds_new_empty_line_when_current_line_is_empty():
    editor = _editor_with_cursor_at_end("")

    _press_smart_enter(editor)

    assert editor.toPlainText() == "\n"


def test_smart_enter_continues_double_indented_numbered_list_and_scrolls_to_cursor():
    body = "\n".join(f"line {i}" for i in range(80))
    nested_list = "1. sdfdsf\n  2. fdsfds\n    3. fdfdsfds"
    editor = _editor_with_cursor_at_end(f"{body}\n{nested_list}")
    editor.show()
    editor.ensureCursorVisible()
    QApplication.processEvents()
    before_scroll = editor.verticalScrollBar().value()

    _press_smart_enter(editor)

    expected = f"{body}\n{nested_list}\n    4. "
    assert editor.toPlainText() == expected
    assert editor.textCursor().position() == len(expected)
    assert editor.verticalScrollBar().value() >= before_scroll


def test_tab_indents_single_selected_line():
    editor = _editor_with_cursor_at_end("alpha\nbeta\ngamma")
    _select_text(editor, "beta")

    editor._handle_tab()

    assert editor.toPlainText() == "alpha\n  beta\ngamma"


def test_tab_indents_numbered_list_line_at_line_start_without_selection():
    editor = _editor_with_cursor_at_end("1. item")

    editor._handle_tab()

    assert editor.toPlainText() == "  1. item"


def test_tab_indents_multi_line_selection_by_line_type():
    editor = _editor_with_cursor_at_end("alpha\n- bullet\n2. item\nplain")
    _select_text(editor, "- bullet\n2. item\nplain")

    editor._handle_tab()

    assert editor.toPlainText() == "alpha\n  - bullet\n  1. item\n  plain"


def test_tab_uses_configured_two_space_default_for_ordered_list():
    editor = _editor_with_cursor_at_end("1. parent\n2. child")
    _select_text(editor, "2. child")

    editor._handle_tab()

    assert editor.toPlainText() == "1. parent\n  1. child"


def test_tab_indents_ordered_sibling_selection_with_nested_numbering():
    editor = _editor_with_cursor_at_end("1. fdsf\n2. sds\n3. dssdas")
    _select_text(editor, "2. sds\n3. dssdas")

    editor._handle_tab()

    assert editor.toPlainText() == "1. fdsf\n  1. sds\n  2. dssdas"


def test_move_lines_down_renumbers_ordered_list():
    editor = _editor_with_cursor_at_end("1. first\n2. second\n3. third")
    _select_text(editor, "2. second")

    editor.move_lines_down()

    assert editor.toPlainText() == "1. first\n2. third\n3. second"


def test_move_lines_up_renumbers_nested_ordered_list():
    editor = _editor_with_cursor_at_end("1. outer\n  1. nested one\n  2. nested two\n2. tail")
    _select_text(editor, "  2. nested two")

    editor.move_lines_up()

    assert editor.toPlainText() == "1. outer\n  1. nested two\n  2. nested one\n2. tail"


def test_tab_indents_and_normalizes_ordered_marker_without_space():
    editor = _editor_with_cursor_at_end("1. fdsf\n2. sds\n3.dssdas")
    _select_text(editor, "2. sds\n3.dssdas")

    editor._handle_tab()

    assert editor.toPlainText() == "1. fdsf\n  1. sds\n  2. dssdas"


def test_shift_tab_unindents_multi_line_selection():
    editor = _editor_with_cursor_at_end("\talpha\n  beta\n  - bullet\n   1. item\nplain")
    _select_text(editor, "\talpha\n  beta\n  - bullet\n   1. item\nplain")

    editor._handle_shift_tab()

    assert editor.toPlainText() == "alpha\nbeta\n- bullet\n1. item\nplain"


def test_shift_tab_unindents_nested_list_one_level_without_selection():
    editor = _editor_with_cursor_at_end("   1. item")

    editor._handle_shift_tab()

    assert editor.toPlainText() == "1. item"


def test_shift_tab_unindents_legacy_two_space_numbered_list_one_level():
    editor = _editor_with_cursor_at_end("    3. item")

    editor._handle_shift_tab()

    assert editor.toPlainText() == "  3. item"


def test_backtab_key_unindents_selection():
    editor = _editor_with_cursor_at_end("  alpha\n  beta")
    _select_text(editor, "  alpha\n  beta")
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Backtab,
        Qt.KeyboardModifier.ShiftModifier,
    )

    editor.keyPressEvent(event)

    assert editor.toPlainText() == "alpha\nbeta"


def test_tab_can_use_four_spaces_or_tabs():
    editor = _editor_with_cursor_at_end("alpha")
    editor.set_indent_text("    ")

    editor._handle_tab()

    assert editor.toPlainText() == "alpha    "

    editor = _editor_with_cursor_at_end("alpha")
    editor.set_indent_text("\t")

    editor._handle_tab()

    assert editor.toPlainText() == "alpha\t"
