import zipfile

from testlog_archive import read_testlog_note_text, rewrite_testlog_status, write_testlog_archive
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
