import os
import shutil
import tempfile
import zipfile

from testlog_utils import (
    collect_referenced_image_filenames,
    set_testlog_status,
    strip_testlog_front_matter,
)


NOTE_ENTRY = "note.md"


def _current_umask():
    # The umask can only be read by setting it; restore it immediately.
    umask = os.umask(0)
    os.umask(umask)
    return umask


def _atomic_replace(path, write_fn):
    # Write the new archive next to the target and swap it in, so a crash or a full
    # disk mid-write leaves the previous file intact instead of a truncated one.
    directory = os.path.dirname(os.path.abspath(path))
    fd, temp_path = tempfile.mkstemp(dir=directory, prefix="." + os.path.basename(path) + ".", suffix=".tmp")
    os.close(fd)
    try:
        write_fn(temp_path)
        # mkstemp creates owner-only files; keep the note's permissions, or give a new
        # note the same default a plain open() would.
        if os.path.exists(path):
            shutil.copymode(path, temp_path)
        else:
            os.chmod(temp_path, 0o666 & ~_current_umask())
        os.replace(temp_path, path)
    except BaseException:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        raise


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

    def write(target):
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(NOTE_ENTRY, note_content)
            if os.path.exists(images_dir):
                for img in os.listdir(images_dir):
                    if img in referenced:
                        zf.write(os.path.join(images_dir, img), f"images/{img}")

    _atomic_replace(path, write)


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

    def write(target):
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(NOTE_ENTRY, note_content)
            for info, content in entries:
                zf.writestr(info, content)

    _atomic_replace(path, write)
