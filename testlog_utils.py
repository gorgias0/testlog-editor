import os
import re
import zipfile
from html import escape
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname


TESTLOG_STATUS_OPTIONS = ("todo", "doing", "done")
DEFAULT_TESTLOG_STATUS = "todo"
TESTLOG_STATUS_LABELS = {
    "todo": "Todo",
    "doing": "Doing",
    "done": "Done",
}
IMAGE_REFERENCE_PATTERN = re.compile(r'!\[.*?\]\(images/([^)]+)\)')
HEADING_PATTERN = re.compile(r'^#+\s+(.+)$', re.MULTILINE)
CHECKBOX_PATTERN = re.compile(r"^\s*([☐☑☒])\s+(.*)$")
BULLET_PATTERN = re.compile(r"^\s*[•◦▪‣·*-–—]\s+(.*)$")
NUMBERED_LIST_PATTERN = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
INDENTED_LINE_PATTERN = re.compile(r"^(?: {4,}|\t+).*$")
FRONT_MATTER_DELIMITER = "---"
STATUS_KEY_PATTERN = re.compile(r"^status\s*:\s*(.*?)\s*$", re.IGNORECASE)
TAGS_KEY_PATTERN = re.compile(r"^tags\s*:\s*(.*?)\s*$", re.IGNORECASE)
TAG_SEPARATOR_PATTERN = re.compile(r"[,\s]+")


def collect_referenced_image_filenames(note_content):
    # Inserted image links are URL-encoded ("my%20shot.png"); keep the raw form too
    # so a file whose real name contains "%" still matches.
    referenced = set()
    for name in IMAGE_REFERENCE_PATTERN.findall(note_content):
        referenced.add(name)
        referenced.add(unquote(name))
    return referenced


INVALID_NAME_CHARACTERS = set('<>:"/\\|?*')
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}


def is_valid_item_name(name):
    # Names must work on Windows too (workspaces may be synced there): no path separators or
    # reserved characters, no trailing dot or space, and none of the reserved device names.
    if not name or name in {".", ".."} or name != name.rstrip(". "):
        return False
    if any(character in INVALID_NAME_CHARACTERS or ord(character) < 32 for character in name):
        return False
    return name.split(".")[0].upper() not in WINDOWS_RESERVED_NAMES


def normalize_testlog_status(status):
    normalized = (status or "").strip().lower()
    return normalized if normalized in TESTLOG_STATUS_OPTIONS else DEFAULT_TESTLOG_STATUS


def split_testlog_front_matter(text):
    lines = (text or "").splitlines(keepends=True)
    if not lines or lines[0].strip() != FRONT_MATTER_DELIMITER:
        return [], text or "", False

    for index in range(1, len(lines)):
        if lines[index].strip() == FRONT_MATTER_DELIMITER:
            return lines[1:index], "".join(lines[index + 1:]), True

    return [], text or "", False


def get_testlog_status(text):
    metadata_lines, _, has_front_matter = split_testlog_front_matter(text)
    if not has_front_matter:
        return DEFAULT_TESTLOG_STATUS

    for line in metadata_lines:
        match = STATUS_KEY_PATTERN.match(line.strip())
        if match:
            return normalize_testlog_status(match.group(1))

    return DEFAULT_TESTLOG_STATUS


def strip_testlog_front_matter(text):
    _, body, has_front_matter = split_testlog_front_matter(text)
    return body.lstrip("\r\n") if has_front_matter else text or ""


def set_testlog_status(text, status):
    normalized_status = normalize_testlog_status(status)
    metadata_lines, body, has_front_matter = split_testlog_front_matter(text)
    status_line = f"status: {normalized_status}\n"

    if not has_front_matter:
        separator = "" if not text else "\n"
        return f"---\n{status_line}---\n{separator}{text or ''}"

    updated_lines = []
    status_written = False
    for line in metadata_lines:
        if STATUS_KEY_PATTERN.match(line.strip()):
            if not status_written:
                updated_lines.append(status_line)
                status_written = True
            continue
        updated_lines.append(line)

    if not status_written:
        updated_lines.append(status_line)

    return "---\n" + "".join(updated_lines) + "---\n" + body


def normalize_testlog_tags(value):
    # Tags are single lowercase words so "#td" works in the sidebar search; commas and
    # spaces both separate them, and "TD" and "td" are the same tag.
    if not value:
        return []
    pieces = TAG_SEPARATOR_PATTERN.split(value) if isinstance(value, str) else [
        piece for item in value for piece in TAG_SEPARATOR_PATTERN.split(item or "")
    ]
    tags = []
    for piece in pieces:
        tag = piece.lstrip("#").lower()
        if tag and all(ch.isalnum() or ch in "-_" for ch in tag) and tag not in tags:
            tags.append(tag)
    return tags


def format_testlog_tags(tags):
    return ", ".join(tags)


def get_testlog_tags(text):
    metadata_lines, _, has_front_matter = split_testlog_front_matter(text)
    if not has_front_matter:
        return []

    for line in metadata_lines:
        match = TAGS_KEY_PATTERN.match(line.strip())
        if match:
            return normalize_testlog_tags(match.group(1))

    return []


def set_testlog_tags(text, tags):
    normalized_tags = normalize_testlog_tags(tags)
    metadata_lines, body, has_front_matter = split_testlog_front_matter(text)
    tags_line = f"tags: {format_testlog_tags(normalized_tags)}\n" if normalized_tags else None

    if not has_front_matter:
        if tags_line is None:
            return text or ""
        separator = "" if not text else "\n"
        return f"---\n{tags_line}---\n{separator}{text or ''}"

    updated_lines = []
    tags_written = False
    for line in metadata_lines:
        if TAGS_KEY_PATTERN.match(line.strip()):
            if tags_line is not None and not tags_written:
                updated_lines.append(tags_line)
                tags_written = True
            continue
        updated_lines.append(line)

    if tags_line is not None and not tags_written:
        updated_lines.append(tags_line)

    return "---\n" + "".join(updated_lines) + "---\n" + body


def read_testlog_header_from_archive(path):
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "note.md" not in zf.namelist():
                return DEFAULT_TESTLOG_STATUS, []
            with zf.open("note.md") as note_file:
                note_text = note_file.read().decode("utf-8")
    except Exception:
        return DEFAULT_TESTLOG_STATUS, []
    return get_testlog_status(note_text), get_testlog_tags(note_text)


def read_testlog_status_from_archive(path):
    return read_testlog_header_from_archive(path)[0]


def suggest_filename_from_heading(text, default="export"):
    match = HEADING_PATTERN.search(text)
    if not match:
        return default

    heading = match.group(1).strip()
    filename = re.sub(r"[^\w\s-]", "", heading)[:100].strip()
    return filename or default


def guess_markdown_from_plain_text(text):
    lines = text.splitlines()
    result = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.strip() == "":
            result.append("")
            index += 1
            continue

        if INDENTED_LINE_PATTERN.match(line):
            block_lines = []
            while index < len(lines):
                current = lines[index]
                if current.strip() == "":
                    break
                if not INDENTED_LINE_PATTERN.match(current):
                    break
                block_lines.append(current)
                index += 1

            stripped_block = _strip_common_indentation(block_lines)
            result.append("```")
            result.extend(stripped_block)
            result.append("```")
            continue

        checkbox_match = CHECKBOX_PATTERN.match(line)
        if checkbox_match:
            checked = "x" if checkbox_match.group(1) in {"☑", "☒"} else " "
            result.append(f"- [{checked}] {checkbox_match.group(2)}")
            index += 1
            continue

        bullet_match = BULLET_PATTERN.match(line)
        if bullet_match:
            result.append(f"- {bullet_match.group(1)}")
            index += 1
            continue

        numbered_match = NUMBERED_LIST_PATTERN.match(line)
        if numbered_match:
            result.append(f"{numbered_match.group(1)}. {numbered_match.group(2)}")
            index += 1
            continue

        result.append(line)
        index += 1

    return "\n".join(result)


def _strip_common_indentation(lines):
    indent_widths = []
    for line in lines:
        stripped = line.lstrip(" \t")
        if not stripped:
            continue
        indent_widths.append(len(line) - len(stripped))

    if not indent_widths:
        return lines

    common_indent = min(indent_widths)
    return [line[common_indent:] if len(line) >= common_indent else "" for line in lines]


def _local_path_from_file_url(src):
    parsed = urlsplit(src)
    path = url2pathname(parsed.path)

    if re.match(r"^/[A-Za-z]:", path):
        path = path[1:]

    if parsed.netloc and parsed.netloc != "localhost":
        return f"//{parsed.netloc}{path}"

    return path


def resolve_preview_image_path(src, session_dir):
    if not src or src.startswith(("data:", "http://", "https://")):
        return None

    if src.startswith("file://"):
        return _local_path_from_file_url(src)

    decoded_src = unquote(src)
    if os.path.isabs(decoded_src):
        return decoded_src

    return os.path.normpath(os.path.join(session_dir, decoded_src))


def build_fulltext_search_results(query, index, limit=50, snippet_radius=50):
    normalized_query = (query or "").strip()
    if not normalized_query:
        return []

    query_lower = normalized_query.lower()
    results = []
    for path, text in index.items():
        haystack = text or ""
        match_pos = haystack.lower().find(query_lower)
        if match_pos == -1:
            continue

        snippet_start = max(0, match_pos - snippet_radius)
        snippet_end = min(len(haystack), match_pos + len(normalized_query) + snippet_radius)
        snippet = haystack[snippet_start:snippet_end].replace("\n", " ").strip()
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(haystack):
            snippet = snippet + "..."

        results.append({
            "path": path,
            "snippet": snippet,
            "position": match_pos,
        })

    results.sort(key=lambda item: (os.path.basename(item["path"]).lower(), item["path"].lower()))
    return results[:limit]


def highlight_fulltext_snippet(snippet, query, highlight_color="#2563eb"):
    snippet = snippet or ""
    normalized_query = (query or "").strip()
    if not normalized_query:
        return escape(snippet)

    # Match on the plain text and escape each piece; matching the escaped text broke entities
    # ("amp" inside "&amp;") and never found queries containing & < >.
    pattern = re.compile(re.escape(normalized_query), re.IGNORECASE)
    parts = []
    position = 0
    for match in pattern.finditer(snippet):
        parts.append(escape(snippet[position:match.start()]))
        parts.append(f'<span style="color: {highlight_color}; font-weight: 600;">{escape(match.group(0))}</span>')
        position = match.end()
    parts.append(escape(snippet[position:]))
    return "".join(parts)
