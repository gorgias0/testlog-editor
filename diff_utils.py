from difflib import SequenceMatcher


def _normalized_line(line, ignore_whitespace=False):
    if not ignore_whitespace:
        return line
    return " ".join(line.split())


def _comparison_lines(lines, ignore_whitespace=False, ignore_blank_lines=False):
    filtered_lines = []
    index_map = []
    for index, line in enumerate(lines):
        normalized = _normalized_line(line, ignore_whitespace=ignore_whitespace)
        if ignore_blank_lines and normalized == "":
            continue
        filtered_lines.append(normalized)
        index_map.append(index)
    return filtered_lines, index_map


def diff_opcodes(lines_a, lines_b, ignore_whitespace=False, ignore_blank_lines=False):
    compare_a, index_map_a = _comparison_lines(
        lines_a,
        ignore_whitespace=ignore_whitespace,
        ignore_blank_lines=ignore_blank_lines,
    )
    compare_b, index_map_b = _comparison_lines(
        lines_b,
        ignore_whitespace=ignore_whitespace,
        ignore_blank_lines=ignore_blank_lines,
    )
    return SequenceMatcher(a=compare_a, b=compare_b).get_opcodes(), index_map_a, index_map_b


def _range_start(index_map, filtered_index, total_length):
    if filtered_index < len(index_map):
        return index_map[filtered_index]
    return total_length


def _range_end(index_map, filtered_index, total_length):
    if filtered_index <= 0:
        return 0
    if filtered_index >= len(index_map):
        return total_length
    return index_map[filtered_index]


def compute_line_diff_states(lines_a, lines_b, ignore_whitespace=False, ignore_blank_lines=False):
    states_a = ["equal"] * len(lines_a)
    states_b = ["equal"] * len(lines_b)

    opcodes, index_map_a, index_map_b = diff_opcodes(
        lines_a,
        lines_b,
        ignore_whitespace=ignore_whitespace,
        ignore_blank_lines=ignore_blank_lines,
    )
    for tag, i1, i2, j1, j2 in opcodes:
        start_a = _range_start(index_map_a, i1, len(lines_a))
        end_a = _range_end(index_map_a, i2, len(lines_a))
        start_b = _range_start(index_map_b, j1, len(lines_b))
        end_b = _range_end(index_map_b, j2, len(lines_b))
        if tag == "replace":
            for index in range(start_a, end_a):
                states_a[index] = "replace"
            for index in range(start_b, end_b):
                states_b[index] = "replace"
        elif tag == "delete":
            for index in range(start_a, end_a):
                states_a[index] = "delete"
        elif tag == "insert":
            for index in range(start_b, end_b):
                states_b[index] = "insert"

    return states_a, states_b


def collect_change_blocks(lines_a, lines_b, ignore_whitespace=False, ignore_blank_lines=False):
    blocks = []
    opcodes, index_map_a, index_map_b = diff_opcodes(
        lines_a,
        lines_b,
        ignore_whitespace=ignore_whitespace,
        ignore_blank_lines=ignore_blank_lines,
    )
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue
        blocks.append(
            {
                "tag": tag,
                "a_start": _range_start(index_map_a, i1, len(lines_a)),
                "a_end": _range_end(index_map_a, i2, len(lines_a)),
                "b_start": _range_start(index_map_b, j1, len(lines_b)),
                "b_end": _range_end(index_map_b, j2, len(lines_b)),
            }
        )
    return blocks
