import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from main import format_editor_counts
from translations import TRANSLATIONS


def english(text):
    return text


def swedish(text):
    return TRANSLATIONS["sv"].get(text, text)


def test_counts_without_selection_show_totals_only():
    assert format_editor_counts(english, "en", 1284, 1051, 0, 0) == "1,284 characters · 1,051 without spaces"


def test_counts_with_selection_add_both_selected_numbers():
    assert format_editor_counts(english, "en", 1284, 1051, 12, 10) == (
        "1,284 characters · 1,051 without spaces · 12 selected (10 without spaces)"
    )


def test_swedish_counts_group_thousands_with_a_non_breaking_space():
    assert format_editor_counts(swedish, "sv", 12345, 9876, 1500, 1200) == (
        "12 345 tecken · 9 876 utan blanksteg · 1 500 markerade (1 200 utan blanksteg)"
    )
