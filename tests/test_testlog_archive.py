import os
import shutil
import stat
import sys
import tempfile
import zipfile

import pytest

import testlog_archive
from testlog_archive import (
    extract_testlog_archive,
    read_testlog_note_text,
    rewrite_testlog_status,
    write_testlog_archive,
)
from testlog_utils import get_testlog_status, set_testlog_status


def _images_dir(tmp_path, *names):
    images_dir = tmp_path / "session" / "images"
    images_dir.mkdir(parents=True)
    for name in names:
        (images_dir / name).write_bytes(b"png")
    return images_dir


def test_write_testlog_archive_keeps_images_with_url_encoded_names(tmp_path):
    images_dir = _images_dir(tmp_path, "my shot.png", "skärmbild.png", "unused.png")
    note = "# Report\n\n![a](images/my%20shot.png)\n![b](images/sk%C3%A4rmbild.png)\n"
    path = tmp_path / "note.testlog"

    write_testlog_archive(str(path), note, str(images_dir))

    with zipfile.ZipFile(path) as zf:
        assert set(zf.namelist()) == {"note.md", "images/my shot.png", "images/skärmbild.png"}
        assert zf.read("note.md").decode("utf-8") == note


def test_rewrite_testlog_status_keeps_images_and_updates_status(tmp_path):
    images_dir = _images_dir(tmp_path, "shot.png")
    note = set_testlog_status("![a](images/shot.png)\n", "todo")
    path = tmp_path / "note.testlog"
    write_testlog_archive(str(path), note, str(images_dir))

    rewrite_testlog_status(str(path), "done")

    with zipfile.ZipFile(path) as zf:
        assert set(zf.namelist()) == {"note.md", "images/shot.png"}
        assert get_testlog_status(zf.read("note.md").decode("utf-8")) == "done"
        assert zf.read("images/shot.png") == b"png"


def test_read_testlog_note_text_returns_none_for_non_zip_file(tmp_path):
    path = tmp_path / "broken.testlog"
    path.write_text("hello", encoding="utf-8")

    assert read_testlog_note_text(str(path)) is None


def _temp_files(directory):
    return [name for name in os.listdir(directory) if name.endswith(".tmp")]


def test_write_testlog_archive_leaves_no_temp_file(tmp_path):
    images_dir = _images_dir(tmp_path)
    path = tmp_path / "note.testlog"

    write_testlog_archive(str(path), "first", str(images_dir))
    write_testlog_archive(str(path), "second", str(images_dir))

    assert _temp_files(tmp_path) == []
    assert read_testlog_note_text(str(path)) == "second"


def test_failed_write_keeps_original_file(tmp_path, monkeypatch):
    images_dir = _images_dir(tmp_path)
    path = tmp_path / "note.testlog"
    write_testlog_archive(str(path), "original", str(images_dir))
    original_bytes = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(zipfile.ZipFile, "writestr", fail)
    with pytest.raises(OSError, match="disk full"):
        write_testlog_archive(str(path), "replacement", str(images_dir))

    assert path.read_bytes() == original_bytes
    assert _temp_files(tmp_path) == []


def test_failed_status_rewrite_keeps_original_file(tmp_path, monkeypatch):
    images_dir = _images_dir(tmp_path, "shot.png")
    path = tmp_path / "note.testlog"
    write_testlog_archive(str(path), set_testlog_status("![a](images/shot.png)\n", "todo"), str(images_dir))
    original_bytes = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(zipfile.ZipFile, "writestr", fail)
    with pytest.raises(OSError):
        rewrite_testlog_status(str(path), "done")

    assert path.read_bytes() == original_bytes
    assert _temp_files(tmp_path) == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_rewrite_keeps_file_permissions(tmp_path):
    images_dir = _images_dir(tmp_path)
    path = tmp_path / "note.testlog"
    write_testlog_archive(str(path), "first", str(images_dir))
    os.chmod(path, 0o640)

    write_testlog_archive(str(path), "second", str(images_dir))

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_new_file_gets_default_permissions(tmp_path):
    images_dir = _images_dir(tmp_path)
    path = tmp_path / "note.testlog"
    umask = os.umask(0o022)
    try:
        write_testlog_archive(str(path), "first", str(images_dir))
    finally:
        os.umask(umask)

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o644


def _session_dirs():
    return {name for name in os.listdir(tempfile.gettempdir()) if name.startswith("testlog_")}


def test_extract_testlog_archive_returns_session_with_note_and_images(tmp_path):
    images_dir = _images_dir(tmp_path, "shot.png")
    note = "![a](images/shot.png)\n"
    path = tmp_path / "note.testlog"
    write_testlog_archive(str(path), note, str(images_dir))

    session_dir, note_text = extract_testlog_archive(str(path))
    try:
        assert note_text == note
        assert os.path.isfile(os.path.join(session_dir, "images", "shot.png"))
    finally:
        shutil.rmtree(session_dir)


def test_extract_testlog_archive_without_note_returns_none_and_images_dir(tmp_path):
    path = tmp_path / "empty.testlog"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("other.txt", "x")

    session_dir, note_text = extract_testlog_archive(str(path))
    try:
        assert note_text is None
        assert os.path.isdir(os.path.join(session_dir, "images"))
    finally:
        shutil.rmtree(session_dir)


def test_extract_testlog_archive_rejects_non_zip_and_cleans_up(tmp_path):
    path = tmp_path / "broken.testlog"
    path.write_text("hello", encoding="utf-8")
    before = _session_dirs()

    with pytest.raises(testlog_archive.TestlogArchiveError):
        extract_testlog_archive(str(path))

    assert _session_dirs() == before


def test_extract_testlog_archive_rejects_invalid_utf8_note(tmp_path):
    path = tmp_path / "latin1.testlog"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("note.md", "sk\xe4rmbild".encode("latin-1"))
    before = _session_dirs()

    with pytest.raises(testlog_archive.TestlogArchiveError):
        extract_testlog_archive(str(path))

    assert _session_dirs() == before
