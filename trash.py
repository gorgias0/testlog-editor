import json
import logging
import os
import shutil
import tempfile
import time


TRASH_DIR_NAME = "Trash"
TRASH_RECORD_NAME = ".trashed.json"
RETENTION_DAYS = 30
SECONDS_PER_DAY = 86400

logger = logging.getLogger("testlog")


class TrashError(Exception):
    pass


def trash_dir(workspace):
    return os.path.join(os.path.abspath(workspace), TRASH_DIR_NAME)


def _norm(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _is_inside(path, folder):
    try:
        return os.path.commonpath([_norm(folder), _norm(path)]) == _norm(folder)
    except ValueError:
        # Different drives on Windows.
        return False


def is_in_trash(workspace, path):
    return bool(workspace) and _is_inside(path, trash_dir(workspace))


def skip_trash_dirs(workspace, root, dirs):
    # For os.walk over the workspace: never descend into Trash.
    if _norm(root) == _norm(workspace):
        dirs[:] = [name for name in dirs if os.path.normcase(name) != os.path.normcase(TRASH_DIR_NAME)]


def available_path(path):
    if not os.path.exists(path):
        return path

    directory = os.path.dirname(path)
    stem, extension = os.path.splitext(os.path.basename(path))
    counter = 2
    while True:
        candidate = os.path.join(directory, f"{stem} {counter}{extension}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def _key(trash, path):
    # Record keys are paths inside Trash with "/" so a workspace synced between Windows
    # and Linux reads the same records on both.
    return os.path.relpath(os.path.abspath(path), trash).replace(os.sep, "/")


def _item_path(trash, key):
    return os.path.join(trash, *key.split("/"))


def is_trash_record_file(name):
    return name == TRASH_RECORD_NAME or (name.startswith(TRASH_RECORD_NAME + ".") and name.endswith(".tmp"))


def _valid_record(value):
    return isinstance(value, dict) and isinstance(value.get("trashed_at"), (int, float)) and isinstance(value.get("original"), str)


def _load_records(trash):
    # A missing or damaged record file only means every item starts a fresh 30 days.
    try:
        with open(os.path.join(trash, TRASH_RECORD_NAME), "r", encoding="utf-8") as f:
            records = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(records, dict):
        return {}
    return {key: value for key, value in records.items() if isinstance(key, str) and _valid_record(value)}


def _save_records(trash, records):
    record_path = os.path.join(trash, TRASH_RECORD_NAME)
    if not records:
        try:
            os.remove(record_path)
        except FileNotFoundError:
            pass
        return

    fd, temp_path = tempfile.mkstemp(dir=trash, prefix=TRASH_RECORD_NAME + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(records, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        os.replace(temp_path, record_path)
    except BaseException:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        raise


def move_to_trash(workspace, path, now=None):
    workspace_abs = os.path.abspath(workspace)
    path_abs = os.path.abspath(path)
    trash = trash_dir(workspace_abs)
    if not os.path.lexists(path_abs):
        raise TrashError(f"{path_abs} does not exist")
    if _norm(path_abs) == _norm(workspace_abs) or not _is_inside(path_abs, workspace_abs):
        raise TrashError(f"{path_abs} is not inside the workspace")
    if is_in_trash(workspace_abs, path_abs):
        raise TrashError(f"{path_abs} is already in Trash")

    relative = os.path.relpath(path_abs, workspace_abs)
    destination = available_path(os.path.join(trash, relative))
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    os.rename(path_abs, destination)

    # The item is safely in Trash at this point; a lost record only means a fresh 30 days.
    try:
        records = _load_records(trash)
        records[_key(trash, destination)] = {
            "trashed_at": time.time() if now is None else now,
            "original": relative.replace(os.sep, "/"),
        }
        _save_records(trash, records)
    except OSError:
        logger.warning("Could not record %s in the Trash records", destination, exc_info=True)
    return destination


def _remove_empty_parents(trash, directory):
    # Restoring the last item from a mirrored folder leaves an empty container behind.
    while _norm(directory) != _norm(trash) and _is_inside(directory, trash):
        try:
            os.rmdir(directory)
        except OSError:
            return
        directory = os.path.dirname(directory)


def restore_from_trash(workspace, path):
    workspace_abs = os.path.abspath(workspace)
    path_abs = os.path.abspath(path)
    trash = trash_dir(workspace_abs)
    if not is_in_trash(workspace_abs, path_abs) or _norm(path_abs) == _norm(trash):
        raise TrashError(f"{path_abs} is not an item in Trash")
    if not os.path.lexists(path_abs):
        raise TrashError(f"{path_abs} does not exist")

    key = _key(trash, path_abs)
    records = _load_records(trash)
    original = None
    probe = key
    while probe:
        if probe in records:
            remainder = key[len(probe):].lstrip("/")
            original = records[probe]["original"] + (f"/{remainder}" if remainder else "")
            break
        probe = probe.rpartition("/")[0]

    destination = os.path.join(workspace_abs, *(original or key).split("/"))
    # Never restore outside the workspace or back into Trash, whatever the record says.
    if not _is_inside(destination, workspace_abs) or is_in_trash(workspace_abs, destination):
        destination = os.path.join(workspace_abs, *key.split("/"))
    destination = available_path(destination)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    os.rename(path_abs, destination)
    _remove_empty_parents(trash, os.path.dirname(path_abs))

    remaining = {
        record_key: value
        for record_key, value in records.items()
        if record_key != key and not record_key.startswith(key + "/")
    }
    try:
        _save_records(trash, remaining)
    except OSError:
        logger.warning("Could not update the Trash records after restoring %s", destination, exc_info=True)
    return destination


def _newest_mtime(path):
    if not os.path.isdir(path):
        return os.lstat(path).st_mtime
    newest = None
    for root, _, files in os.walk(path):
        for name in files:
            try:
                mtime = os.lstat(os.path.join(root, name)).st_mtime
            except OSError:
                continue
            newest = mtime if newest is None else max(newest, mtime)
    return os.lstat(path).st_mtime if newest is None else newest


def _covered_by_record(records, key):
    # True when the item at key, or a folder it is inside, is a recorded Trash item.
    while key:
        if key in records:
            return True
        key = key.rpartition("/")[0]
    return False


def _remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def purge_trash(workspace, now=None, retention_days=RETENTION_DAYS):
    trash = trash_dir(workspace)
    if not os.path.isdir(trash):
        return []
    now = time.time() if now is None else now

    records = {key: value for key, value in _load_records(trash).items() if os.path.lexists(_item_path(trash, key))}

    # Files the app has no record of (moved within Trash, or put there by hand) start their
    # 30 days now. Folders the app trashed are covered by their own record.
    for root, dirs, files in os.walk(trash):
        root_key = "" if _norm(root) == _norm(trash) else _key(trash, root)
        if _covered_by_record(records, root_key):
            dirs[:] = []
            continue
        for name in files:
            if not root_key and is_trash_record_file(name):
                continue
            key = f"{root_key}/{name}" if root_key else name
            if key not in records:
                records[key] = {"trashed_at": now, "original": key}

    purged = []
    cutoff = now - retention_days * SECONDS_PER_DAY
    for key in sorted(records):
        item = _item_path(trash, key)
        if not os.path.lexists(item):
            records.pop(key, None)
            continue
        try:
            last_activity = max(records[key]["trashed_at"], _newest_mtime(item))
            if last_activity >= cutoff:
                continue
            _remove(item)
        except OSError:
            # For example a file held open by another program on Windows; try again next time.
            logger.warning("Could not purge %s from Trash", item, exc_info=True)
            continue
        purged.append(item)
        records.pop(key, None)

    # Remove the folders that only mirrored the original structure and are now empty.
    for root, _, _ in os.walk(trash, topdown=False):
        if _norm(root) == _norm(trash) or _covered_by_record(records, _key(trash, root)):
            continue
        try:
            os.rmdir(root)
        except OSError:
            pass

    _save_records(trash, records)
    return purged


def empty_trash(workspace):
    trash = trash_dir(workspace)
    if not os.path.isdir(trash):
        return
    for name in os.listdir(trash):
        _remove(os.path.join(trash, name))
