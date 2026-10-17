import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from workspace_models import parse_sidebar_search, sidebar_search_matches


@pytest.mark.parametrize(
    "text, expected",
    [
        ("#td login", ("login", ["td"])),
        ("#TD #meet", ("", ["td", "meet"])),
        ("Login Flow", ("login flow", [])),
        ("#", ("#", [])),
        ("#td #td", ("", ["td"])),
        ("", ("", [])),
        ("  #td   checkout  page ", ("checkout page", ["td"])),
    ],
)
def test_parse_sidebar_search(text, expected):
    assert parse_sidebar_search(text) == expected


def test_name_term_matches_part_of_filename_case_insensitively():
    assert sidebar_search_matches("login", [], "Login-Flow.testlog", [])
    assert not sidebar_search_matches("checkout", [], "Login-Flow.testlog", [])


def test_tag_terms_must_all_be_present():
    assert sidebar_search_matches("", ["td"], "a.testlog", ["td", "meet"])
    assert sidebar_search_matches("", ["td", "meet"], "a.testlog", ["meet", "td"])
    assert not sidebar_search_matches("", ["td", "meet"], "a.testlog", ["td"])
    assert not sidebar_search_matches("", ["td"], "a.testlog", [])


def test_name_and_tag_terms_combine():
    assert sidebar_search_matches("login", ["td"], "login.testlog", ["td"])
    assert not sidebar_search_matches("login", ["td"], "checkout.testlog", ["td"])
    assert not sidebar_search_matches("login", ["td"], "login.testlog", ["meet"])


def test_tag_term_matches_whole_tags_only():
    assert not sidebar_search_matches("", ["td"], "a.testlog", ["tdialog"])
