import zipfile

import pytest

from testlog_utils import (
    DEFAULT_TESTLOG_STATUS,
    collect_referenced_image_filenames,
    format_testlog_tags,
    get_testlog_tags,
    normalize_testlog_tags,
    read_testlog_header_from_archive,
    set_testlog_tags,
    get_testlog_status,
    guess_markdown_from_plain_text,
    is_valid_item_name,
    normalize_testlog_status,
    resolve_preview_image_path,
    set_testlog_status,
    strip_testlog_front_matter,
    suggest_filename_from_heading,
)


def test_collect_referenced_image_filenames_returns_only_embedded_image_names():
    note = """
    # Report

    ![first](images/first.png)
    Some text
    ![second image](images/second-shot.jpg)
    ![outside](../images/ignored.png)
    """

    assert collect_referenced_image_filenames(note) == {"first.png", "second-shot.jpg"}


def test_suggest_filename_from_heading_sanitizes_heading_text():
    text = "# Sprint: Build/Test? <Done>\n\nBody"

    assert suggest_filename_from_heading(text) == "Sprint BuildTest Done"


def test_suggest_filename_from_heading_falls_back_when_heading_missing():
    assert suggest_filename_from_heading("plain text only") == "export"


def test_get_testlog_status_reads_front_matter_status():
    assert get_testlog_status("---\nstatus: doing\n---\n\n# Note") == "doing"


def test_get_testlog_status_defaults_when_missing_or_unknown():
    assert get_testlog_status("# Note") == DEFAULT_TESTLOG_STATUS
    assert get_testlog_status("---\nstatus: blocked\n---\n\n# Note") == DEFAULT_TESTLOG_STATUS


def test_normalize_testlog_status_accepts_known_statuses_case_insensitively():
    assert normalize_testlog_status("Done") == "done"
    assert normalize_testlog_status("nope") == DEFAULT_TESTLOG_STATUS


def test_set_testlog_status_adds_front_matter_when_missing():
    assert set_testlog_status("# Note\n", "done") == "---\nstatus: done\n---\n\n# Note\n"


def test_set_testlog_status_updates_existing_front_matter_and_preserves_body():
    text = "---\ntitle: Sample\nstatus: todo\n---\n\n# Note\n"

    assert set_testlog_status(text, "doing") == "---\ntitle: Sample\nstatus: doing\n---\n\n# Note\n"


def test_strip_testlog_front_matter_returns_renderable_body():
    text = "---\nstatus: done\n---\n\n# Note\n"

    assert strip_testlog_front_matter(text) == "# Note\n"


def test_guess_markdown_from_plain_text_converts_bullets_and_checkboxes():
    plain_text = "• First item\n☐ Open task\n☑ Done task\n1) Step one"

    assert guess_markdown_from_plain_text(plain_text) == (
        "- First item\n"
        "- [ ] Open task\n"
        "- [x] Done task\n"
        "1. Step one"
    )


def test_guess_markdown_from_plain_text_wraps_indented_blocks_in_fences():
    plain_text = "Before\n\n    alpha()\n    beta()\n\nAfter"

    assert guess_markdown_from_plain_text(plain_text) == (
        "Before\n\n```\nalpha()\nbeta()\n```\n\nAfter"
    )


def test_resolve_preview_image_path_keeps_relative_paths_in_session():
    resolved = resolve_preview_image_path("images/screenshot-123.png", "/tmp/testlog_abc")

    assert resolved == "/tmp/testlog_abc/images/screenshot-123.png"


def test_resolve_preview_image_path_decodes_file_urls():
    resolved = resolve_preview_image_path("file:///tmp/testlog_abc/images/shot%201.png", "/unused")

    assert resolved == "/tmp/testlog_abc/images/shot 1.png"


def test_resolve_preview_image_path_preserves_windows_drive_paths_from_file_urls():
    resolved = resolve_preview_image_path("file:///C:/Users/Daniel/Pictures/shot.png", "/unused")

    assert resolved == "C:/Users/Daniel/Pictures/shot.png"


def test_resolve_preview_image_path_ignores_remote_and_data_sources():
    assert resolve_preview_image_path("https://example.com/image.png", "/tmp/testlog_abc") is None
    assert resolve_preview_image_path("data:image/png;base64,abc", "/tmp/testlog_abc") is None


@pytest.mark.parametrize(
    "value, expected",
    [
        ("TD, meet", ["td", "meet"]),
        ("#td #Meet td", ["td", "meet"]),
        ("td,,  meet ", ["td", "meet"]),
        (["TD", "x y"], ["td", "x", "y"]),
        ("td bad!tag meet", ["td", "meet"]),
        ("möte, ärende-1, a_b", ["möte", "ärende-1", "a_b"]),
        ("", []),
        (None, []),
        ("#", []),
    ],
)
def test_normalize_testlog_tags(value, expected):
    assert normalize_testlog_tags(value) == expected


def test_format_testlog_tags():
    assert format_testlog_tags(["td", "meet"]) == "td, meet"


def test_get_testlog_tags_reads_header_line():
    assert get_testlog_tags("---\nstatus: doing\nTags: TD, Meet\n---\n# Note\n") == ["td", "meet"]


def test_get_testlog_tags_without_header_or_line():
    assert get_testlog_tags("# Note\ntags: td\n") == []
    assert get_testlog_tags("---\nstatus: todo\n---\n# Note\n") == []


def test_set_testlog_tags_adds_line_after_status_and_keeps_body():
    text = "---\nstatus: doing\n---\n# Note\nbody\n"

    updated = set_testlog_tags(text, "TD, meet")

    assert updated == "---\nstatus: doing\ntags: td, meet\n---\n# Note\nbody\n"


def test_set_testlog_tags_replaces_and_deduplicates_lines():
    text = "---\ntags: old\nstatus: done\ntags: older\n---\nbody\n"

    assert set_testlog_tags(text, ["new"]) == "---\ntags: new\nstatus: done\n---\nbody\n"


def test_set_testlog_tags_with_no_tags_removes_line():
    text = "---\nstatus: todo\ntags: td\n---\nbody\n"

    assert set_testlog_tags(text, "") == "---\nstatus: todo\n---\nbody\n"


def test_set_testlog_tags_without_header():
    assert set_testlog_tags("# Note\n", "") == "# Note\n"
    assert set_testlog_tags("# Note\n", "td") == "---\ntags: td\n---\n\n# Note\n"


def test_set_testlog_status_keeps_tags_line():
    text = "---\nstatus: todo\ntags: td, meet\n---\nbody\n"

    updated = set_testlog_status(text, "done")

    assert get_testlog_tags(updated) == ["td", "meet"]
    assert get_testlog_status(updated) == "done"


def test_read_testlog_header_from_archive(tmp_path):
    path = tmp_path / "note.testlog"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("note.md", "---\nstatus: doing\ntags: td\n---\nbody\n")

    assert read_testlog_header_from_archive(str(path)) == ("doing", ["td"])


def test_read_testlog_header_from_archive_defaults_for_broken_file(tmp_path):
    path = tmp_path / "broken.testlog"
    path.write_text("hello", encoding="utf-8")

    assert read_testlog_header_from_archive(str(path)) == (DEFAULT_TESTLOG_STATUS, [])


@pytest.mark.parametrize("name", ["Report", "2026-10-17 smoke", "möte (v2)", "a.b", "Archive"])
def test_valid_item_names(name):
    assert is_valid_item_name(name)


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "Bug/login", "Bug\\login", "a?b", "Bug: login", "a*b", 'a"b', "a<b", "a|b", "trailing.", "trailing ", "CON", "con.txt", "LPT1", "tab\there"],
)
def test_invalid_item_names(name):
    assert not is_valid_item_name(name)
