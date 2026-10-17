import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTime
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


def test_insert_current_time_uses_hours_and_minutes():
    editor = _editor_with_cursor_at_end("- ")
    before = QTime.currentTime()

    editor.insert_current_time()

    inserted = editor.toPlainText()[2:]
    assert re.fullmatch(r"\d{2}:\d{2}", inserted)
    # Allow the minute to roll over between reading the clock and inserting.
    after = QTime.currentTime()
    assert inserted in {before.toString("HH:mm"), after.toString("HH:mm")}


def test_move_last_line_up_keeps_lines_separate():
    editor = _editor_with_cursor_at_end("a\nb\nc")

    editor.move_lines_up()

    assert editor.toPlainText() == "a\nc\nb"


def test_move_last_ordered_item_up_renumbers_without_joining():
    editor = _editor_with_cursor_at_end("1. a\n2. b")

    editor.move_lines_up()

    assert editor.toPlainText() == "1. b\n2. a"


def test_move_lines_leaves_numbers_elsewhere_alone():
    editor = _editor_with_cursor_at_end("x\n3.14 roughly\n2026.10.17 release\n\n- y\n- z")

    editor.move_lines_up()

    assert editor.toPlainText() == "x\n3.14 roughly\n2026.10.17 release\n\n- z\n- y"


def test_move_lines_only_renumbers_the_touched_list():
    editor = _editor_with_cursor_at_end("1. a\n2. b\n\ntext\n\n7. other\n9. odd")
    _select_text(editor, "2. b")

    editor.move_lines_up()

    assert editor.toPlainText() == "1. b\n2. a\n\ntext\n\n7. other\n9. odd"


def test_move_lines_keeps_list_start_number_and_spacing():
    editor = _editor_with_cursor_at_end("5. five\n6.  six")

    editor.move_lines_up()

    assert editor.toPlainText() == "5.  six\n6. five"


def test_move_lines_does_not_renumber_inside_code_fence():
    editor = _editor_with_cursor_at_end("```\n2. code\n```\n1. a\n2. b")

    editor.move_lines_up()

    assert editor.toPlainText() == "```\n2. code\n```\n1. b\n2. a"


def test_tab_on_line_starting_with_decimal_or_date_only_indents():
    for text in ("3.14 is pi", "2026.10.17 release"):
        editor = _editor_with_cursor_at_end(text)
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        editor.setTextCursor(cursor)

        editor._handle_tab()

        assert editor.toPlainText() == f"  {text}"


def _set_cursor(editor, python_index):
    from main import utf16_length

    cursor = editor.textCursor()
    cursor.setPosition(utf16_length(editor.toPlainText()[:python_index]))
    editor.setTextCursor(cursor)


def _type_backticks(editor, count=3):
    for _ in range(count):
        editor._handle_backtick()


def test_smart_enter_replaces_selection_on_list_line():
    editor = _editor_with_cursor_at_end("- abc")
    _select_text(editor, "b")

    _press_smart_enter(editor)

    assert editor.toPlainText() == "- a\n- c"


def test_smart_enter_replaces_selection_across_list_lines():
    editor = _editor_with_cursor_at_end("- abc\n- def")
    _select_text(editor, "c\n- d")

    _press_smart_enter(editor)

    assert editor.toPlainText() == "- ab\n- ef"


def test_smart_enter_splits_correctly_after_emoji():
    editor = _editor_with_cursor_at_end("- 😀ab")
    _set_cursor(editor, len("- 😀a"))

    _press_smart_enter(editor)

    assert editor.toPlainText() == "- 😀a\n- b"


def test_smart_enter_on_whitespace_only_line_keeps_the_line():
    editor = _editor_with_cursor_at_end("abc\n    ")

    _press_smart_enter(editor)

    assert editor.toPlainText() == "abc\n\n"


def test_link_lookup_after_emoji_does_not_return_next_line_link():
    editor = _editor_with_cursor_at_end("😀" * 20 + " x\n[l](http://z)")
    from main import utf16_length

    position = utf16_length("😀" * 20 + " ")

    assert editor._link_at_position(position) is None
    assert editor._link_at_position(utf16_length("😀" * 20 + " x\n[l](h")) == "http://z"


def test_typing_closing_fence_closes_the_code_block():
    editor = _editor_with_cursor_at_end("```\ncode\n")

    _type_backticks(editor)

    assert editor.toPlainText() == "```\ncode\n```"


def test_new_code_block_takes_language_and_enter_moves_into_body():
    editor = _editor_with_cursor_at_end("")

    _type_backticks(editor)
    editor.insertPlainText("py")
    _press_smart_enter(editor)
    editor.insertPlainText("x")

    assert editor.toPlainText() == "```py\nx\n```"


def test_code_block_auto_expands_after_emoji():
    editor = _editor_with_cursor_at_end("😀 ")

    _type_backticks(editor)

    assert editor.toPlainText() == "😀 ```\n\n```"


def test_highlighter_closes_fence_only_on_matching_fence():
    from PySide6.QtGui import QTextDocument

    from main import MarkdownHighlighter

    _app()
    document = QTextDocument()
    document.setPlainText("````md\n```\n# not heading\n````\n# heading\n~~~\n```\n~~~\nend")
    MarkdownHighlighter(document).rehighlight()

    in_code = [document.findBlockByNumber(i).userState() >= 1 for i in range(document.blockCount())]
    assert in_code == [True, True, True, False, False, True, True, False, False]


def test_highlighter_stays_fast_on_long_lines_with_unmatched_markers():
    import time

    from PySide6.QtGui import QTextDocument

    from main import MarkdownHighlighter

    _app()
    document = QTextDocument()
    highlighter = MarkdownHighlighter(document)
    started = time.perf_counter()
    document.setPlainText("**a " * 10000 + "\n" + "*a " * 14000)
    highlighter.rehighlight()

    assert time.perf_counter() - started < 1.5
