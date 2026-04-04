from testlog_utils import build_fulltext_search_results, highlight_fulltext_snippet


def test_build_fulltext_search_results_finds_case_insensitive_matches_and_sorts_by_filename():
    index = {
        "/workspace/zeta/report.testlog": "Alpha without match",
        "/workspace/alpha/notes.testlog": "First line\nSearch token appears here",
        "/workspace/beta/notes.testlog": "Another SEARCH token lives here",
    }

    results = build_fulltext_search_results("search", index)

    assert [result["path"] for result in results] == [
        "/workspace/alpha/notes.testlog",
        "/workspace/beta/notes.testlog",
    ]
    assert results[0]["snippet"].startswith("First line Search")


def test_build_fulltext_search_results_adds_ellipses_when_snippet_is_trimmed():
    index = {
        "/workspace/long/sample.testlog": "A" * 80 + "needle" + "B" * 80,
    }

    results = build_fulltext_search_results("needle", index, snippet_radius=10)

    assert results[0]["snippet"].startswith("...")
    assert results[0]["snippet"].endswith("...")


def test_highlight_fulltext_snippet_wraps_all_case_insensitive_matches():
    highlighted = highlight_fulltext_snippet("Search and SEARCH again", "search")

    assert highlighted.count("<span") == 2
    assert "font-weight: 600;" in highlighted
