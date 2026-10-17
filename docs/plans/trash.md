# Move deleted notes to a Trash folder with restore and 30-day purge

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `tests/PLANS.md` (the ExecPlan rules for this repository; the file lives in the `tests/` folder even though `AGENTS.md` refers to it simply as `PLANS.md`).


## Purpose / Big Picture

Today, deleting a note or folder in TestLog Editor's sidebar removes it from disk for good. After this change, Delete (the Delete key or right-click, Delete, both after the existing confirmation dialog) moves the item into a `Trash` folder inside the workspace instead. The Trash folder is visible at the bottom of the sidebar, labelled "Trash" in English and "Papperskorg" in Swedish, with a bin icon. Right-clicking an item inside it offers Restore, which puts it back where it came from. Deleting inside Trash removes permanently, as Delete does today. Right-clicking the Trash folder offers Empty Trash. Each time a workspace is opened, anything that has sat in Trash for 30 days, counted from the later of when it was trashed and when it was last edited, is removed for good.

How to see it working: delete a note, open the Trash folder in the sidebar and find it there under its original folder path; right-click it, Restore, and it is back in its original folder with its content and images. Notes in Trash do not show up in full-text search, sidebar search, tag suggestions or the recent-files switcher.


## Progress

- [x] (2026-10-17) Milestone 1: `trash.py` (`move_to_trash`, `restore_from_trash`, `purge_trash`, `empty_trash`, `is_in_trash`, `skip_trash_dirs`, `available_path`, record file handling); `MainWindow._available_path` now delegates to `trash.available_path`. `tests/test_trash.py` (26 tests); 134 passed. Three deliberate mutations of `trash.py` (ignore modification time, clean folders inside trashed folders, trust a record pointing outside the workspace) were each caught by exactly one test.
- [x] (2026-10-17) Milestone 1 committed as `f86b87e`.
- [x] (2026-10-17) Milestone 2: `delete_item` moves to Trash outside it (new dialog texts) and deletes permanently inside it, refuses the Trash folder itself, and saves the open note first if it is being trashed; `_purge_workspace_trash` runs in `_set_workspace`; `skip_trash_dirs` in all five workspace walks, and the recent-files loop in `_open_most_recent_testlog` skips notes in Trash; 3 Swedish strings. 134 passed. Scripted real-window run (see `Artifacts and Notes`).
- [ ] Milestone 3: Trash in the sidebar: localized label, bin icon, sorted last, record file hidden; Restore and Empty Trash in the right-click menu; translations; scripted check and screenshots.
- [ ] Milestone 4: `README.md` and `AGENTS.md`; full test run; retrospective; manual check on a real display.


## Surprises & Discoveries

- Observation: recording empty folders found during a purge, as first planned, would keep the empty mirror folder left behind after a restore (for example `Trash/tdialog/` after restoring its only note) for another 30 days instead of cleaning it up.
  Evidence: found while writing `purge_trash`; see the Decision Log entry below.


## Decision Log

- Decision: the folder is named `Trash` on disk in every language, and only its label in the sidebar is translated ("Papperskorg" in Swedish).
  Rationale: one folder regardless of UI language. The existing Archive feature shows the problem with the alternative: it creates `Arkiv` or `Archive` depending on the language (`MainWindow._archive_folder_name`), so switching language splits the archive. Archive is left as it is in this plan.
  Date/Author: 2026-10-17 / Daniel Lindkvist and Claude.
- Decision: the folder is visible in the sidebar, not hidden.
  Rationale: requested; users go there to restore.
  Date/Author: 2026-10-17 / Daniel Lindkvist.
- Decision: an item keeps its path relative to the workspace inside Trash (`tdialog/login.testlog` becomes `Trash/tdialog/login.testlog`); a taken name gets a number (`login 2.testlog`), as Archive does with `_available_path`.
  Rationale: the user can see where something came from, and nothing in Trash is ever overwritten.
  Date/Author: 2026-10-17 / Claude.
- Decision: retention is 30 days counted from the later of the time the item was trashed and its last modification; the trash time is recorded by the app in `Trash/.trashed.json`, which also stores each item's original location for Restore. An item in Trash with no record (for example moved within Trash, or put there outside the app) is given the current time the first time the app sees it. A missing or unreadable record file therefore makes everything start a fresh 30 days; nothing is purged early because records are lost.
  Rationale: the user asked for purging after 30 days "unless they have been updated or moved". Moving a file does not change its modification time, and Windows does not record when a file was moved, so the app must record the trash time itself. Taking the later of that and the modification time makes an edit restart the clock; giving unrecorded items the current time makes a move restart it.
  Date/Author: 2026-10-17 / Daniel Lindkvist and Claude.
- Decision: purging happens when a workspace is opened (at app start and when switching workspace), not on a timer.
  Rationale: simple and predictable; an app left open for days purges at its next start.
  Date/Author: 2026-10-17 / Claude, accepted by Daniel Lindkvist.
- Decision: deleting does not reveal the moved item in the Trash folder; the tree behaves as it does after a delete today.
  Rationale: matches the Archive behaviour the user asked for earlier (stay in the current folder).
  Date/Author: 2026-10-17 / Claude, accepted by Daniel Lindkvist.
- Decision: `purge_trash` records only unrecorded files, not empty folders; empty folders inside Trash that are not recorded items and not inside one are removed at the end of each purge, and `restore_from_trash` removes the mirror folders it empties straight away. An empty folder deleted through the app is still recorded by `move_to_trash` and kept for 30 days.
  Rationale: see `Surprises & Discoveries`; the mirror folders exist only to show where items came from.
  Date/Author: 2026-10-17 / Claude.
- Decision: `restore_from_trash` falls back to the item's path inside Trash when a record's `original` would land outside the workspace or inside Trash.
  Rationale: the record file is plain JSON in a synced folder and could be edited or damaged; a restore must never write outside the workspace.
  Date/Author: 2026-10-17 / Claude.
- Decision: when the open note (or a folder containing it) is moved to Trash, unsaved edits are saved first (`_flush_pending_changes`), and the move is cancelled if that save fails.
  Rationale: Trash is meant for restoring; the trashed copy should hold the latest text. Permanent deletion inside Trash keeps today's behaviour (no save).
  Date/Author: 2026-10-17 / Claude.
- Decision: Delete on the Trash folder itself does nothing (no dialog) already in Milestone 2, rather than waiting for Milestone 3's menu changes.
  Rationale: otherwise the Delete key on the Trash folder would offer to delete all of Trash permanently through the generic folder dialog.
  Date/Author: 2026-10-17 / Claude.
- Decision: record keys and stored original paths use `/` as separator regardless of operating system, and times are stored as Unix timestamps (seconds since 1970, UTC).
  Rationale: the workspace may be shared between a Windows and a Linux machine through a sync tool; `/` and UTC timestamps read the same on both.
  Date/Author: 2026-10-17 / Claude.


## Outcomes & Retrospective

Milestone 1 (2026-10-17): every Trash rule exists as a tested, Qt-free function. Nothing in the app calls it yet apart from the shared `available_path`.

Milestone 2 (2026-10-17): Delete now moves to Trash, items in Trash are kept out of every search and scan, deleting inside Trash is permanent, and the 30-day purge runs when a workspace opens. Trash still looks like an ordinary folder in the sidebar and has no Restore yet; Milestones 3-4 remain.


## Context and Orientation

The repository root is the folder containing `main.py`; all paths below are relative to it. TestLog Editor is a PySide6 (Qt for Python) desktop app. A "workspace" is a folder the user opens; the sidebar tree shows its sub-folders and `.testlog` notes (zip files). `MainWindow.workspace_dir` holds its path.

Deleting today: `MainWindow.delete_item(path)` in `main.py` (search for `def delete_item`) asks "Delete {filename}? This cannot be undone." (or "Delete Folder {filename}? ..." for folders) in a `QMessageBox.question` titled "Confirm Delete", then calls `shutil.rmtree` or `os.remove`, then `self._remove_tracked_paths(path)` (drops pins and clears `self.current_file` if the open note was inside), `self._remove_fulltext_index_entries_for_path(path)`, `self.refresh_pinned()`, opens a neighbouring note if the open one was deleted (`_replacement_file_path_after_delete`), and restarts full-text indexing. The Delete key calls it through `delete_selected_tree_item`, and the right-click menu (`show_context_menu`) through its Delete entry. `MainWindow._update_tracked_paths(old, new)` updates pins and `current_file` after a move (used by rename, move and archive). `MainWindow._available_path(path)` returns `path` or the first free `name 2.ext`, `name 3.ext`, ... in the same folder.

Places that walk the whole workspace with `os.walk` and must skip Trash (search `os.walk` in `main.py` and `workspace_models.py`): the full-text `Indexer.run` thread; the recent-files switcher (in `RecentFilesSwitcher`); `MainWindow._known_workspace_tags` (tag suggestions; already skips Archive); `MainWindow._open_most_recent_testlog` (already skips Archive); and `WorkspaceSortProxyModel._find_matching_dirs` in `workspace_models.py` (sidebar search). Note that `Indexer.run` and the switcher do not currently skip anything.

The sidebar: `WorkspaceFileSystemModel` (`workspace_models.py`) is a `QFileSystemModel` whose `data()` returns the display text (note names without `.testlog`) and icons per row; it receives its icons from `MainWindow` (built from SVG strings in `icons.py` with `icon_from_svg`). `WorkspaceSortProxyModel` hides rows in `filterAcceptsRow` and orders them in `lessThan`, where `_sort_rank` puts folders first, then pinned files, then other files. The file model is set to list `QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot`; it does not list hidden files on Linux (names starting with a dot), but on Windows a leading dot does not make a file hidden, so `Trash/.trashed.json` would show up there unless filtered. `show_context_menu` in `main.py` builds the right-click menu; `MainWindow._tr` translates through `translations.py` (`TRANSLATIONS["sv"]`), and `_retranslate_ui` re-applies texts when the language changes.

`MainWindow._set_workspace(path)` opens a workspace: it sets the model's root path, starts full-text indexing, and opens the last note (`_open_most_recent_testlog`). Purging belongs at its start.

Tests run with `python -m pytest` from the repository root with the project `.venv` active; Qt-free modules are tested directly with `tmp_path` folders (see `tests/test_testlog_archive.py`). At commit `09e64fe` there are 108 tests, all passing.


## Plan of Work

Milestone 1 creates `trash.py` at the repository root, with no Qt imports, so that every rule can be unit-tested with plain folders. It defines `TRASH_DIR_NAME = "Trash"`, `TRASH_RECORD_NAME = ".trashed.json"`, `RETENTION_DAYS = 30`, and an exception `TrashError(Exception)`.

The record file maps a key, the item's path inside Trash relative to the Trash folder with `/` separators (for example `tdialog/login.testlog`), to an object `{"trashed_at": <unix time>, "original": "<path relative to the workspace, with />"}`. `_load_records(workspace)` reads it and returns `{}` when it is missing or not valid JSON (log nothing here; the caller decides). `_save_records(workspace, records)` writes it atomically: write to a temporary file in the Trash folder and `os.replace` it over the record file, as `testlog_archive._atomic_replace` does for notes (write JSON with `indent=2`, `sort_keys=True`, UTF-8). If the records become empty, remove the file instead.

Public functions:

`trash_dir(workspace)` returns `os.path.join(workspace, TRASH_DIR_NAME)`. `is_in_trash(workspace, path)` is true when `path` is the Trash folder or inside it (compare with `os.path.normcase(os.path.abspath(...))` and `os.path.commonpath`, catching `ValueError` for different Windows drives).

`move_to_trash(workspace, path, now=None)` moves a file or folder into Trash and returns its new path. It refuses (raises `TrashError`) when `path` is the workspace itself, is in Trash already, or is outside the workspace. The destination is `Trash/<path relative to the workspace>`; parent folders are created; a taken destination gets the same numbering rule as `MainWindow._available_path` (copy that small loop into the module as `available_path(path)`, and make `MainWindow._available_path` call it so the rule lives in one place). The move is `os.rename`. Then it records `{"trashed_at": now or time.time(), "original": <relative original path>}` under the destination's key and saves.

`restore_from_trash(workspace, path)` moves an item inside Trash back and returns the restored path. It finds the record for the item, or for its nearest recorded ancestor folder (an item can be restored from inside a trashed folder); the original location is the recorded original plus the remaining part of the path. Without any record it falls back to the item's path relative to the Trash folder, which mirrors its original place by construction. It creates missing parent folders, applies `available_path` to the destination, renames, and removes the record for the item and any records below it (keys starting with the item's key plus `/`). It raises `TrashError` if `path` is not inside Trash or is the Trash folder itself.

`purge_trash(workspace, now=None, retention_days=RETENTION_DAYS)` returns the list of removed paths. It does nothing if the Trash folder does not exist. It first drops records whose item no longer exists. It then walks the Trash folder (skipping the record file and any temporary file) and, for every file and every empty folder that neither has a record nor sits under a recorded folder, adds a record with `trashed_at = now` and `original` equal to its path relative to Trash (these are items moved within or into Trash outside the app). For each recorded item, its last activity is the larger of `trashed_at` and the newest `st_mtime` of the item (for a folder: of anything inside it, or of the folder itself if empty). Items whose last activity is more than `retention_days * 86400` seconds before `now` are removed (`os.remove` or `shutil.rmtree`) and their records dropped. Finally it removes folders inside Trash that are now empty and are not themselves recorded items (the containers that mirrored the original folder structure), deepest first, and saves the records. A failure to remove one item (for example a file open in another program on Windows) is skipped and left for the next purge; it must not stop the others.

`empty_trash(workspace)` removes everything inside the Trash folder, including the record file, and leaves the empty Trash folder.

Tests in `tests/test_trash.py`, all with `tmp_path` as the workspace and explicit `now` values instead of sleeping: moving a nested note keeps its relative path and writes a record with original and time; moving onto a taken name numbers it; moving a folder; refusing the workspace, Trash itself, an item already in Trash, and a path outside the workspace; restore puts a note back (content unchanged), recreates a missing original folder, numbers a taken original name, and removes the record; restore of a file inside a trashed folder goes to the right place; restore without a record mirrors the Trash path; purge removes a note trashed 31 days ago but keeps one trashed 29 days ago; purge keeps a note trashed 40 days ago whose modification time is 5 days ago (set with `os.utime`); purge gives an unrecorded file a fresh record and keeps it; purge with a damaged record file keeps everything and rewrites valid records; purge removes empty mirror folders but keeps a recorded empty folder; a purge that cannot remove one item still removes the others (simulate by monkeypatching `os.remove` to raise for one path); `empty_trash` leaves an empty Trash folder; record keys and originals use `/` (check the JSON text).

Milestone 2 wires this into the app, in `main.py`. In `delete_item`, decide `in_trash = is_in_trash(self.workspace_dir, path)` (false when there is no workspace). Outside Trash, the dialog text becomes "Move {filename} to Trash?" (folders: "Move folder {filename} to Trash?"), and on Yes the item is moved with `move_to_trash`; the bookkeeping is the same as today's delete (the item is gone from its old place), so keep the existing `_remove_tracked_paths`, full-text removal, `refresh_pinned` and replacement-note logic. Inside Trash, keep today's texts and permanent deletion. Errors from `move_to_trash` (`TrashError`, `OSError`) are logged with `logger.exception` and shown as "Could not move {name} to Trash." in a `QMessageBox.warning`, and nothing else changes. At the start of `_set_workspace` (after the workspace path is known, before indexing), call `purge_trash` inside `try`; log failures and continue, and log the number of purged items at info level.

Make every workspace walk skip Trash: add to `trash.py` a helper `skip_trash_dirs(workspace, root, dirs)` that removes `TRASH_DIR_NAME` from `dirs` in place when `root` is the workspace folder (compare normalized paths), and call it in each `os.walk` loop listed in `Context and Orientation`, using `for root, dirs, files in os.walk(...)` (rename `_` to `dirs` where needed). In `workspace_models.py`, the proxy has no `workspace_dir`; use the file model's `rootPath()`, which is the workspace.

Check by a scripted run of the real window (offscreen, scratch `XDG_CONFIG_HOME`, `QMessageBox.question` patched to answer Yes): delete a nested note, a folder and the open note; confirm they are in `Trash/` with records; confirm full-text search and `#tag` search no longer find them; delete one inside Trash and confirm it is gone from disk; reopen the workspace with an item recorded 31 days ago and confirm it was purged.

Milestone 3 presents Trash in the sidebar. In `icons.py`, add `TRASH_ICON_SVG`, a simple bin in the same flat style and colours as `FOLDER_ICON_SVG`. In `WorkspaceFileSystemModel`, add attributes `trash_label = "Trash"` and `trash_icon = None`, set by `MainWindow` (the label from `self._tr("Trash")` in `_retranslate_ui`, followed by a repaint of the tree). In `data()`, for the folder whose path is the root path plus `/Trash` (compare normalized paths), return `trash_label` for `DisplayRole` and `trash_icon` for `DecorationRole`. In `WorkspaceSortProxyModel._sort_rank`, give that folder a rank after every other item (folders 0, pinned files 1, files 2, Trash 3), so it is always last. In `filterAcceptsRow`, hide the record file `Trash/.trashed.json` (and any `.trashed.json.*.tmp` left by an interrupted save). The Trash folder itself stays visible during a search only if it has matches, which after Milestone 2 it never has, so it simply disappears while searching.

In `show_context_menu`: for the Trash folder itself, show only "Empty Trash" (and nothing else; it cannot be renamed, moved, archived or deleted); "Empty Trash" asks "Permanently delete everything in Trash? This cannot be undone." and calls `empty_trash`, then refreshes pins, removes full-text entries under Trash, and clears the editor if the open note was in Trash (reuse `_remove_tracked_paths(trash_dir)`). For items inside Trash, show "Restore" first, then Delete (permanent), and leave out Move To, Archive, Status, Tags and Pin. Restore calls `restore_from_trash`, then `_update_tracked_paths(old, new)`, selects the restored item with `_select_file_in_tree(new, retry_attempts=6)` (here revealing it is wanted: the user went looking for it), and restarts full-text indexing. F2 (rename) and the Delete key keep working inside Trash through the same checks: make `rename_item` refuse the Trash folder itself, and `delete_item` refuse it too (use Empty Trash instead).

Translations to add to `translations.py`: "Trash": "Papperskorg", "Restore": "Återställ", "Empty Trash": "Töm papperskorgen", "Move {filename} to Trash?": "Flytta {filename} till papperskorgen?", "Move folder {filename} to Trash?": "Flytta mappen {filename} till papperskorgen?", "Permanently delete everything in Trash? This cannot be undone.": "Ta bort allt i papperskorgen permanent? Detta går inte att ångra.", "Could not move {name} to Trash.": "Kunde inte flytta {name} till papperskorgen.", "Could not restore {name}.": "Kunde inte återställa {name}.".

Check by a scripted real-window run and screenshots of the sidebar in both languages and themes: the Trash folder is last with the bin icon and the right label, the record file is not shown, Restore puts a note back and selects it, Empty Trash empties it.

Milestone 4 updates `README.md` (Highlights: deleted notes go to Trash, restorable, purged after 30 days) and `AGENTS.md` (the `Trash` folder, its record file, the purge rule, and that workspace scans must call `skip_trash_dirs`), runs the full suite, and writes the retrospective.


## Concrete Steps

From the repository root with the virtual environment active:

    python -m pytest -q
    ...
    108 passed

After Milestone 1, the count rises by the new tests in `tests/test_trash.py`, with no failures:

    python -m pytest -q tests/test_trash.py

For Milestones 2 and 3, write throwaway scripts outside the repository that set `QT_QPA_PLATFORM=offscreen` and point `XDG_CONFIG_HOME` and `XDG_DATA_HOME` at a scratch folder (so the user's settings and log are untouched), build a scratch workspace, create `MainWindow()`, and drive it through its methods, printing what is on disk and what the tree shows. Earlier plans in `docs/plans/` record examples of such runs.


## Validation and Acceptance

Automated: `python -m pytest -q` passes, with the 108 existing tests plus `tests/test_trash.py`.

Manual, with `python main.py` and a scratch workspace holding copies of notes (never the real workspace): select a note in a sub-folder and press Delete; the dialog asks to move it to Trash; after Yes it is gone from its folder, the next note is selected, and the Trash folder at the bottom of the sidebar (bin icon, "Trash", or "Papperskorg" after switching to Swedish) contains it under the same sub-folder name. Search for its name or one of its tags: it is not found. Right-click it in Trash, Restore: it is back in its folder and selected, with content and images. Delete it again, then select it in Trash and press Delete: the dialog says it cannot be undone, and after Yes it is gone from disk. Delete a whole folder: it appears in Trash and can be restored as a whole. Right-click Trash, Empty Trash: everything inside is gone. To see the purge, edit `Trash/.trashed.json` with a text editor to set an item's `trashed_at` to a time more than 30 days ago (and make sure the file itself was not modified recently, for example by giving it an old modification time with `touch -d "40 days ago" <file>` on Linux), then reopen the workspace; the item is gone.


## Idempotence and Recovery

All milestones are code plus tests and can be redone after `git checkout -- <file>`. Moving to Trash and restoring are renames within one folder tree, so they either happen completely or not at all; the record file is written atomically, and losing it only gives items a fresh 30 days. The purge is the only automatic permanent deletion; it never touches anything outside the `Trash` folder, and the unit tests pin that down. Use a scratch workspace for all manual testing, since this feature deletes files.


## Artifacts and Notes

Milestone 2, real window (offscreen, scratch settings, `QMessageBox.question` patched to answer Yes), workspace with `tdialog/login`, `tdialog/checkout` (both tagged `td`), `meetings/weekly` and `top`, all containing the word `secretword`:

    dialog: Move login.testlog to Trash?
    open note after deleting it: top.testlog
    trashed copy has unsaved edit: True
    folder dialog: Move folder meetings to Trash?
    on disk: ['Trash/meetings/weekly.testlog', 'Trash/tdialog/login.testlog', 'tdialog/checkout.testlog', 'top.testlog']
    records: ['meetings', 'tdialog/login.testlog']
    full-text index: ['tdialog/checkout.testlog', 'top.testlog']
    tag suggestions: ['td']
    switcher 'login' matches: []
    sidebar '#td' matching folders: ['.', 'tdialog']
    delete on Trash itself asked: False | Trash exists: True
    inside-Trash dialog: Delete login.testlog? This cannot be undone.
    on disk: ['Trash/meetings/weekly.testlog', 'tdialog/checkout.testlog', 'top.testlog']
    after reopening with meetings trashed 31 days ago: ['tdialog/checkout.testlog', 'top.testlog'] | Trash contents: []

The note opened after deleting the open one is the next row in the tree, which can be in another folder (`top.testlog` here); that is the existing delete behaviour, unchanged.


## Interfaces and Dependencies

Standard library only (`os`, `shutil`, `json`, `time`, `tempfile`, `logging`). At the end, `trash.py` provides:

    TRASH_DIR_NAME = "Trash"
    TRASH_RECORD_NAME = ".trashed.json"
    RETENTION_DAYS = 30
    class TrashError(Exception)
    def trash_dir(workspace: str) -> str
    def is_in_trash(workspace: str, path: str) -> bool
    def available_path(path: str) -> str
    def move_to_trash(workspace: str, path: str, now: float | None = None) -> str
    def restore_from_trash(workspace: str, path: str) -> str
    def purge_trash(workspace: str, now: float | None = None, retention_days: int = RETENTION_DAYS) -> list[str]
    def empty_trash(workspace: str) -> None
    def skip_trash_dirs(workspace: str, root: str, dirs: list[str]) -> None

`icons.py` gains `TRASH_ICON_SVG`. `WorkspaceFileSystemModel` gains `trash_label` and `trash_icon`.


Revision note (2026-10-17): first version, written after reading `delete_item`, the context menu, the workspace walks and the sidebar models at commit `09e64fe`.
