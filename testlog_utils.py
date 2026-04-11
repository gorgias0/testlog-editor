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
MARKDOWN_MIME_TYPES = (
    "text/markdown",
    "text/x-markdown",
    "application/x-markdown",
)
CHECKBOX_PATTERN = re.compile(r"^\s*([☐☑☒])\s+(.*)$")
BULLET_PATTERN = re.compile(r"^\s*[•◦▪‣·*-–—]\s+(.*)$")
NUMBERED_LIST_PATTERN = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
INDENTED_LINE_PATTERN = re.compile(r"^(?: {4,}|\t+).*$")
FRONT_MATTER_DELIMITER = "---"
STATUS_KEY_PATTERN = re.compile(r"^status\s*:\s*(.*?)\s*$", re.IGNORECASE)


def collect_referenced_image_filenames(note_content):
    return set(IMAGE_REFERENCE_PATTERN.findall(note_content))


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


def read_testlog_status_from_archive(path):
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "note.md" not in zf.namelist():
                return DEFAULT_TESTLOG_STATUS
            with zf.open("note.md") as note_file:
                return get_testlog_status(note_file.read().decode("utf-8"))
    except Exception:
        return DEFAULT_TESTLOG_STATUS


def suggest_filename_from_heading(text, default="export"):
    match = HEADING_PATTERN.search(text)
    if not match:
        return default

    heading = match.group(1).strip()
    filename = re.sub(r"[^\w\s-]", "", heading)[:100].strip()
    return filename or default


def preferred_markdown_paste_text(mime_data, plain_text):
    for mime_type in MARKDOWN_MIME_TYPES:
        raw_value = mime_data.get(mime_type)
        if raw_value is None:
            continue

        if isinstance(raw_value, str):
            return raw_value

        if isinstance(raw_value, (bytes, bytearray)):
            decoded = raw_value.decode("utf-8", errors="ignore")
            if decoded:
                return decoded

    return plain_text


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
    escaped_snippet = escape(snippet or "")
    normalized_query = (query or "").strip()
    if not normalized_query:
        return escaped_snippet

    pattern = re.compile(re.escape(normalized_query), re.IGNORECASE)
    return pattern.sub(
        lambda match: (
            f'<span style="color: {highlight_color}; font-weight: 600;">'
            f"{escape(match.group(0))}</span>"
        ),
        escaped_snippet,
    )
