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


def test_highlight_does_not_break_html_entities():
    html = highlight_fulltext_snippet("R&D amp", "amp")

    assert html == 'R&amp;D <span style="color: #2563eb; font-weight: 600;">amp</span>'


def test_highlight_finds_queries_with_special_characters():
    html = highlight_fulltext_snippet("Team R&D <beta>", "r&d")

    assert html == 'Team <span style="color: #2563eb; font-weight: 600;">R&amp;D</span> &lt;beta&gt;'
