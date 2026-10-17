import os

from trash import available_path


ARCHIVE_DIR_NAME = "Archive"
# Older versions named the folder after the UI language, so a Swedish session created "Arkiv".
LEGACY_ARCHIVE_DIR_NAMES = ("Arkiv",)


def archive_dir(workspace):
    return os.path.join(os.path.abspath(workspace), ARCHIVE_DIR_NAME)


def _merge_into(source, destination, moves):
    for name in sorted(os.listdir(source)):
        source_path = os.path.join(source, name)
        destination_path = os.path.join(destination, name)
        if os.path.isdir(source_path) and os.path.isdir(destination_path):
            _merge_into(source_path, destination_path, moves)
            continue
        # Never overwrite: a name already taken in Archive gets a number, as archiving does.
        destination_path = available_path(destination_path)
        os.rename(source_path, destination_path)
        moves.append((source_path, destination_path))
    try:
        os.rmdir(source)
    except OSError:
        pass


def merge_legacy_archives(workspace):
    """Move the contents of legacy archive folders into Archive; return the (old, new) moves."""
    workspace_abs = os.path.abspath(workspace)
    target = archive_dir(workspace_abs)
    moves = []
    for legacy_name in LEGACY_ARCHIVE_DIR_NAMES:
        legacy = os.path.join(workspace_abs, legacy_name)
        # On a case-insensitive file system a legacy name could resolve to Archive itself.
        if not os.path.isdir(legacy) or (os.path.exists(target) and os.path.samefile(legacy, target)):
            continue
        if not os.path.exists(target):
            os.rename(legacy, target)
            moves.append((legacy, target))
            continue
        _merge_into(legacy, target, moves)
    return moves
