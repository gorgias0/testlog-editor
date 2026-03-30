from testlog_utils import (
    collect_referenced_image_filenames,
    resolve_preview_image_path,
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
