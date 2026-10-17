import os
import zipfile

from testlog_utils import (
    collect_referenced_image_filenames,
    set_testlog_status,
    strip_testlog_front_matter,
)


NOTE_ENTRY = "note.md"


def read_testlog_note_text(path):
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if NOTE_ENTRY not in zf.namelist():
                return None
            with zf.open(NOTE_ENTRY) as note_file:
                return strip_testlog_front_matter(note_file.read().decode("utf-8"))
    except Exception:
        return None


def write_testlog_archive(path, note_content, images_dir):
    # Only images the note still references are packed, so removing a link drops the image.
    referenced = collect_referenced_image_filenames(note_content)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(NOTE_ENTRY, note_content)
        if os.path.exists(images_dir):
            for img in os.listdir(images_dir):
                if img in referenced:
                    zf.write(os.path.join(images_dir, img), f"images/{img}")


def rewrite_testlog_status(path, status):
    entries = []
    note_content = ""
    with zipfile.ZipFile(path, "r") as zf:
        for info in zf.infolist():
            if info.filename == NOTE_ENTRY:
                note_content = zf.read(info.filename).decode("utf-8")
                continue
            entries.append((info, zf.read(info.filename)))

    note_content = set_testlog_status(note_content, status)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(NOTE_ENTRY, note_content)
        for info, content in entries:
            zf.writestr(info, content)
