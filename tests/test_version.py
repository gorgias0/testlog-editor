import subprocess
import sys

import pytest

import version


def test_format_version_uses_commit_count_as_patch_number():
    assert version.format_version(68) == "1.0.68"
    assert version.format_version(68, dirty=True) == "1.0.68+dirty"
    assert version.format_version(None) == "unknown"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "first")
    (tmp_path / "a.txt").write_text("two", encoding="utf-8")
    _git(tmp_path, "commit", "-q", "-am", "second")
    return tmp_path


def test_collect_build_info_counts_commits(repo):
    info = version.collect_build_info(repo)

    assert info["version"] == "1.0.2"
    assert len(info["commit"]) >= 7


def test_untracked_files_do_not_make_build_dirty(repo):
    (repo / "install.sh").write_text("echo", encoding="utf-8")

    assert version.collect_build_info(repo)["version"] == "1.0.2"


def test_modified_tracked_file_makes_build_dirty(repo):
    (repo / "a.txt").write_text("three", encoding="utf-8")

    assert version.collect_build_info(repo)["version"] == "1.0.2+dirty"


def test_collect_build_info_outside_git_is_unknown(tmp_path):
    info = version.collect_build_info(tmp_path / "not-a-repo")

    assert info["version"] == "unknown"
    assert info["commit"] == "unknown"


def test_build_info_round_trips_through_generated_module(tmp_path, monkeypatch):
    info = {"version": "1.0.68", "commit": "1e68ca2", "build_date": "2026-10-17"}
    version.write_build_info(tmp_path / "_build_info.py", info)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delitem(sys.modules, "_build_info", raising=False)
    version.get_version_info.cache_clear()
    try:
        assert version.get_version_info() == info
    finally:
        version.get_version_info.cache_clear()
        sys.modules.pop("_build_info", None)
