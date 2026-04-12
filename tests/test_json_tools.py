from json_tools import format_json_best_effort, pretty_print_json_like


def test_format_json_best_effort_formats_valid_json():
    formatted, valid, error = format_json_best_effort('{"name":"Alice","items":[1,2]}')

    assert valid is True
    assert error is None
    assert formatted == '{\n  "name": "Alice",\n  "items": [\n    1,\n    2\n  ]\n}'


def test_format_json_best_effort_formats_invalid_json_and_reports_error():
    formatted, valid, error = format_json_best_effort('{"name":"Alice","items":[1,2,]}')

    assert valid is False
    assert error
    assert formatted == '{\n  "name": "Alice",\n  "items": [\n    1,\n    2,\n  ]\n}'


def test_pretty_print_json_like_closes_missing_containers():
    assert pretty_print_json_like('{"name":"Alice","items":[1,2') == (
        '{\n'
        '  "name": "Alice",\n'
        '  "items": [\n'
        '    1,\n'
        '    2\n'
        '  ]\n'
        '}'
    )
