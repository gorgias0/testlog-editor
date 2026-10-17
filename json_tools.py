import json


def format_json_best_effort(text, indent=2):
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        return pretty_print_json_like(text, indent=indent), False, str(error)
    return json.dumps(parsed, indent=indent, ensure_ascii=False), True, None


def pretty_print_json_like(text, indent=2):
    indent_text = " " * indent
    lines = []
    current = []
    depth = 0
    stack = []
    in_string = False
    string_quote = '"'
    escaped = False
    # Whitespace between bare words ("hello world" without quotes) is kept as one space.
    pending_space = False

    def line_text():
        return "".join(current).rstrip()

    def flush_line():
        value = line_text()
        if value:
            lines.append(value)
        current.clear()

    def ensure_indent():
        if not current:
            current.append(indent_text * depth)

    def append_value_char(char):
        nonlocal pending_space
        ensure_indent()
        if pending_space and current[-1] and not current[-1].isspace() and current[-1][-1] not in "{[:, ":
            current.append(" ")
        pending_space = False
        current.append(char)

    for char in text:
        if in_string:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == string_quote:
                in_string = False
            continue

        if char in "\"'":
            # Invalid JSON often uses single quotes; treat them as strings so their spaces stay.
            append_value_char(char)
            in_string = True
            string_quote = char
            continue

        if not char.isspace() and char not in "{[}],:":
            append_value_char(char)
            continue

        pending_space = char.isspace() and bool(current)
        if char in "{[":
            ensure_indent()
            current.append(char)
            flush_line()
            depth += 1
            stack.append("}" if char == "{" else "]")
        elif char in "}]":
            flush_line()
            # A mismatched closer (as in "[1, 2}") still closes the open container, so no
            # extra bracket is added at the end.
            if stack:
                stack.pop()
            depth = max(0, depth - 1)
            ensure_indent()
            current.append(char)
        elif char == ",":
            ensure_indent()
            current.append(char)
            flush_line()
        elif char == ":":
            ensure_indent()
            current.append(": ")

    if in_string:
        current.append(string_quote)

    flush_line()
    while stack:
        depth = max(0, depth - 1)
        lines.append(f"{indent_text * depth}{stack.pop()}")

    return "\n".join(lines)
