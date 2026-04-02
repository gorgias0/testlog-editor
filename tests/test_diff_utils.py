from diff_utils import collect_change_blocks, compute_line_diff_states


def test_compute_line_diff_states_marks_replace_lines():
    lines_a = ["same", "old", "tail"]
    lines_b = ["same", "new", "tail"]

    states_a, states_b = compute_line_diff_states(lines_a, lines_b)

    assert states_a == ["equal", "replace", "equal"]
    assert states_b == ["equal", "replace", "equal"]


def test_compute_line_diff_states_marks_delete_and_insert_lines():
    lines_a = ["same", "left-only", "tail"]
    lines_b = ["same", "tail", "right-only"]

    states_a, states_b = compute_line_diff_states(lines_a, lines_b)

    assert states_a == ["equal", "delete", "equal"]
    assert states_b == ["equal", "equal", "insert"]


def test_compute_line_diff_states_keeps_equal_lines_unhighlighted():
    lines = ["alpha", "beta", "gamma"]

    states_a, states_b = compute_line_diff_states(lines, lines)

    assert states_a == ["equal", "equal", "equal"]
    assert states_b == ["equal", "equal", "equal"]


def test_compute_line_diff_states_can_ignore_whitespace_only_changes():
    lines_a = ["alpha beta", "gamma"]
    lines_b = [" alpha   beta ", "gamma"]

    states_a, states_b = compute_line_diff_states(lines_a, lines_b, ignore_whitespace=True)

    assert states_a == ["equal", "equal"]
    assert states_b == ["equal", "equal"]


def test_collect_change_blocks_returns_non_equal_opcode_ranges():
    lines_a = ["same", "old", "tail"]
    lines_b = ["same", "new", "tail", "extra"]

    blocks = collect_change_blocks(lines_a, lines_b)

    assert blocks == [
        {"tag": "replace", "a_start": 1, "a_end": 2, "b_start": 1, "b_end": 2},
        {"tag": "insert", "a_start": 3, "a_end": 3, "b_start": 3, "b_end": 4},
    ]


def test_compute_line_diff_states_can_ignore_blank_lines():
    lines_a = ["alpha", "", "beta"]
    lines_b = ["alpha", "beta"]

    states_a, states_b = compute_line_diff_states(lines_a, lines_b, ignore_blank_lines=True)

    assert states_a == ["equal", "equal", "equal"]
    assert states_b == ["equal", "equal"]


def test_collect_change_blocks_can_ignore_blank_lines():
    lines_a = ["alpha", "", "beta", ""]
    lines_b = ["alpha", "beta"]

    blocks = collect_change_blocks(lines_a, lines_b, ignore_blank_lines=True)

    assert blocks == []
