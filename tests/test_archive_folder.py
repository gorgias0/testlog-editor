import os

from archive_folder import merge_legacy_archives


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_no_legacy_folder_does_nothing(tmp_path):
    _write(tmp_path / "Archive" / "a.testlog", "a")

    assert merge_legacy_archives(tmp_path) == []
    assert os.listdir(tmp_path / "Archive") == ["a.testlog"]


def test_legacy_folder_is_renamed_when_archive_is_missing(tmp_path):
    _write(tmp_path / "Arkiv" / "sub" / "a.testlog", "a")

    moves = merge_legacy_archives(tmp_path)

    assert moves == [(str(tmp_path / "Arkiv"), str(tmp_path / "Archive"))]
    assert (tmp_path / "Archive" / "sub" / "a.testlog").read_text(encoding="utf-8") == "a"
    assert not (tmp_path / "Arkiv").exists()


def test_legacy_folder_is_merged_without_overwriting(tmp_path):
    _write(tmp_path / "Archive" / "same.testlog", "english")
    _write(tmp_path / "Archive" / "shared" / "x.testlog", "english x")
    _write(tmp_path / "Arkiv" / "same.testlog", "swedish")
    _write(tmp_path / "Arkiv" / "shared" / "x.testlog", "swedish x")
    _write(tmp_path / "Arkiv" / "shared" / "y.testlog", "swedish y")
    _write(tmp_path / "Arkiv" / "only-sv.testlog", "only")

    moves = merge_legacy_archives(tmp_path)

    archive = tmp_path / "Archive"
    assert (archive / "same.testlog").read_text(encoding="utf-8") == "english"
    assert (archive / "same 2.testlog").read_text(encoding="utf-8") == "swedish"
    assert (archive / "shared" / "x.testlog").read_text(encoding="utf-8") == "english x"
    assert (archive / "shared" / "x 2.testlog").read_text(encoding="utf-8") == "swedish x"
    assert (archive / "shared" / "y.testlog").read_text(encoding="utf-8") == "swedish y"
    assert (archive / "only-sv.testlog").read_text(encoding="utf-8") == "only"
    assert not (tmp_path / "Arkiv").exists()
    assert (str(tmp_path / "Arkiv" / "same.testlog"), str(archive / "same 2.testlog")) in moves
    assert len(moves) == 4


def test_merge_runs_once(tmp_path):
    _write(tmp_path / "Arkiv" / "a.testlog", "a")
    merge_legacy_archives(tmp_path)

    assert merge_legacy_archives(tmp_path) == []
