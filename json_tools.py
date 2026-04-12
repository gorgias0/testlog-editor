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
    escaped = False

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

    for char in text:
        if in_string:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            ensure_indent()
            current.append(char)
            in_string = True
        elif char in "{[":
            ensure_indent()
            current.append(char)
            flush_line()
            depth += 1
            stack.append("}" if char == "{" else "]")
        elif char in "}]":
            flush_line()
            if stack and stack[-1] == char:
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
        elif char.isspace():
            continue
        else:
            ensure_indent()
            current.append(char)

    if in_string:
        current.append('"')

    flush_line()
    while stack:
        depth = max(0, depth - 1)
        lines.append(f"{indent_text * depth}{stack.pop()}")

    return "\n".join(lines)
