import os
import re
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname


IMAGE_REFERENCE_PATTERN = re.compile(r'!\[.*?\]\(images/([^)]+)\)')
HEADING_PATTERN = re.compile(r'^#+\s+(.+)$', re.MULTILINE)


def collect_referenced_image_filenames(note_content):
    return set(IMAGE_REFERENCE_PATTERN.findall(note_content))


def suggest_filename_from_heading(text, default="export"):
    match = HEADING_PATTERN.search(text)
    if not match:
        return default

    heading = match.group(1).strip()
    filename = re.sub(r"[^\w\s-]", "", heading)[:100].strip()
    return filename or default


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
