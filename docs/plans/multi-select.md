# Select several items in the file tree and act on them together

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `tests/PLANS.md` (the ExecPlan rules for this repository; the file lives in the `tests/` folder even though `AGENTS.md` refers to it simply as `PLANS.md`).


## Purpose / Big Picture

Today the sidebar tree of TestLog Editor holds one selected item at a time, so changing the status or tags of ten notes, or archiving them, takes ten round trips through the right-click menu. After this change a user can select several notes and folders, with the mouse (Shift+click for a range, Ctrl+click to add or remove one) or the keyboard (Shift+arrows, Ctrl+Space, Ctrl+A), and then set the status, add or remove tags, pin, archive, move or delete all of them at once from the same right-click menu (also reachable with the Menu key or Shift+F10) or the Delete key. One confirmation covers the whole selection, and a failure on one item (for example a file locked by another program on Windows) does not stop the others; the user gets a single summary.

How to see it working: in a scratch workspace, click a note, Shift+click another note further down, right-click, choose Status, Done; every selected note's dot turns grey. Choose Tags, Add tags..., type `td`; every selected note shows `td` and keeps its other tags. Press Delete; one dialog asks "Move 4 items to Trash?" and all four go to Trash.


## Progress

- [x] (2026-10-18) Milestone 1: `ExtendedSelection` on the tree; `tree_item_clicked` ignores Shift/Ctrl clicks; `_selected_tree_paths()` (visible selected rows in on-screen order, falling back to the current row), `_tree_row_visible`, `_is_tree_item`; `trash.top_level_paths` with 3 tests (218 passed); the tree delegate paints the row background across the whole row. Scripted real-window run with real clicks and keys and screenshots (see `Artifacts and Notes`).
- [ ] Milestone 2: dialog-free per-item cores for status, tags, pin, archive, move, trash, permanent delete and restore, and bulk functions on top of them with one confirmation and one summary; unit tests for the pure parts and a scripted check.
- [ ] Milestone 3: the right-click menu, Delete key and Menu key act on the whole selection; translations; scripted check and screenshots.
- [ ] Milestone 4: `README.md` and `AGENTS.md`; full test run; retrospective; manual check on a real display.


## Surprises & Discoveries

- Observation: `QTreeView.setCurrentIndex` in extended mode already clears other selected rows (Qt uses ClearAndSelect for a programmatic current change), so `_select_file_in_tree` and the keyboard handlers needed no change.
  Evidence: after a three-item selection, `open_testlog(b)` left `selected=['b.testlog']`.
- Observation: Qt keeps rows selected when their folder is collapsed; they are invisible but would still be acted on.
  Evidence: Ctrl+clicking `folder/inner` and collapsing `folder` kept it in `selectedRows()`; `_selected_tree_paths` filters such rows out (`_tree_row_visible`).
- Observation: the tree delegate drew the selection only behind the name, leaving the tags and status dot unhighlighted; harmless for one row, but a multi-selection looked broken.
  Evidence: screenshots before and after the full-row `PE_PanelItemViewItem` paint in `WorkspaceTreeItemDelegate.paint`.


## Decision Log

- Decision: bulk tags are two actions, "Add tags..." and "Remove tags...", not "Set tags".
  Rationale: chosen by the user. Each note keeps the tags the action does not mention, so selecting notes with different tags never loses any.
  Date/Author: 2026-10-17 / Daniel Lindkvist.
- Decision: a plain click still opens the clicked note; Shift+click and Ctrl+click only change the selection.
  Rationale: keeps today's single-item behaviour exactly, and building a selection must not keep opening (and saving) notes.
  Date/Author: 2026-10-17 / Claude, agreed with Daniel Lindkvist.
- Decision: Rename and Empty Trash are not offered when more than one item is selected; Status, Tags and Archive skip folders in the selection; Move To... and Delete act on folders too.
  Rationale: rename has no sensible meaning for several items; status and tags live in note headers; archive only takes notes today.
  Date/Author: 2026-10-17 / Claude, agreed with Daniel Lindkvist.
- Decision: when a selection contains a folder and items inside that folder, only the folder is acted on for Move To..., Delete and Restore.
  Rationale: moving or trashing the folder already takes its contents along; acting on the inner items as well would fail (they are gone) and produce false errors in the summary.
  Date/Author: 2026-10-17 / Claude.


## Outcomes & Retrospective

Milestone 1 (2026-10-18): the tree supports file-manager style multi-selection with mouse and keyboard, single-item behaviour (click opens, arrow preview) is unchanged, and selected rows are highlighted across the full width. No action uses the selection yet; Milestones 2-4 remain.


## Context and Orientation

The repository root is the folder containing `main.py`. TestLog Editor is a PySide6 (Qt for Python) desktop app; `MainWindow` in `main.py` holds almost all UI code.

The sidebar tree is `self.tree`, a `QTreeView` created in `MainWindow._setup_ui` (search for `self.tree = QTreeView()`). Its model is `self.fs_proxy_model` (a `WorkspaceSortProxyModel` from `workspace_models.py`) over `self.fs_model` (a `WorkspaceFileSystemModel`, a `QFileSystemModel`). A tree row is a "proxy index"; `self.fs_proxy_model.mapToSource(index)` gives the file model's index, and `self.fs_model.filePath(source_index)` gives the path. The view's selection mode is Qt's default for `QTreeView`, single selection. Qt's `QAbstractItemView.SelectionMode.ExtendedSelection` gives the familiar file-manager behaviour (Shift+click range, Ctrl+click toggle, Shift+arrows, Ctrl+Space, Ctrl+A) without extra code.

Today's single-item behaviour, all in `main.py`:

`self.tree.clicked` is connected to `tree_item_clicked(index)`, which saves pending changes and opens the clicked note. With extended selection, Qt also emits `clicked` for Shift+click and Ctrl+click, so the handler must ignore clicks that carry a Shift or Control modifier (`QApplication.keyboardModifiers()`).

`MainWindow.eventFilter` handles keys for the tree: Enter opens (`_open_tree_index`), Esc returns to the editor, the Menu key and Shift+F10 open the context menu for the current row (`_open_keyboard_context_menu`), and keys in `TREE_NAVIGATION_KEYS` with no modifier restart `self.tree_preview_timer`, which opens the highlighted note after 300 ms (`_preview_tree_selection`). Shift+arrows reach the filter with a Shift modifier and therefore do not start the preview; keep it that way.

The Delete key is a `QShortcut` on the tree connected to `delete_selected_tree_item`, which uses `_selected_tree_item_path()` (the current row) and calls `delete_item(path)`. F2 calls `rename_selected_tree_item`.

`show_context_menu(pos)` and `show_context_menu_for_current_item()` both call `_show_tree_context_menu(index, global_pos)`, which builds one of three menus: for the Trash folder (Empty Trash), for an item inside Trash (Restore, Delete), or for anything else (Rename, Delete, Move To..., and for notes Status, Tags..., Pin/Unpin, Archive). Each entry calls a per-item method:

`set_file_status(path, status)` and `set_file_tags(path, tags)` write the header of a closed note with `rewrite_testlog_status`/`rewrite_testlog_tags` (atomic, `testlog_archive.py`) or, for the open note, change the editor text and save; both return `True` or `False` and log failures. `edit_file_tags(path)` asks for the tags first.

`delete_item(path)` asks for confirmation, then moves the item to Trash with `trash.move_to_trash` or, inside Trash, deletes it permanently; it updates pins, the recent list and the full-text index (`_remove_tracked_paths`, `_remove_fulltext_index_entries_for_path`), saves the open note first if it is being trashed, and afterwards selects (or opens, if the open note was deleted) the next note in the same folder (`_next_file_in_same_folder`).

`move_item(path)` asks for a destination folder with `QFileDialog.getExistingDirectory`, refuses a taken name (`_path_taken_by_other_item`, `_warn_item_exists`), renames, and updates tracked paths (`_update_tracked_paths`).

`archive_item(path)` marks the note done, moves it to `<workspace>/Archive` (`archive_folder.archive_dir`) with a free name, and selects or opens the next note in the same folder.

`restore_item(path)` calls `trash.restore_from_trash`. `toggle_pin(path)` adds or removes the path from `self.pinned_files`.

`translations.py` maps English UI strings to Swedish (`TRANSLATIONS["sv"]`), looked up with `self._tr`.

Tests run with `python -m pytest` from the repository root using the project `.venv`. At commit `3fe6d0b` there are 215 tests, all passing. UI behaviour is checked with throwaway scripts that run `MainWindow` with `QT_QPA_PLATFORM=offscreen`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `TMPDIR` pointed at a scratch folder; they script dialogs by replacing `QMessageBox.question`, `QInputDialog` and `QFileDialog` functions, and script menus by replacing `main.QMenu` with a subclass whose `exec` picks an action (assigning to `QMenu.exec` on the class has no effect in PySide6).


## Plan of Work

Milestone 1 turns on extended selection. In `_setup_ui`, call `self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)` (import `QAbstractItemView` from `PySide6.QtWidgets`). In `tree_item_clicked`, return early when `QApplication.keyboardModifiers()` contains Shift or Control. Add `_selected_tree_paths()`, which returns the paths of the selected rows (`self.tree.selectionModel().selectedRows()`), skipping the workspace root and anything that is not a `.testlog` file or a folder, in on-screen order, and falling back to the current row when nothing is selected. Then reduce it with a pure helper `top_level_paths(paths)` (put it in `trash.py` next to the other path helpers, or a small new module if that reads better) that drops any path inside another selected folder. Check that everything that today calls `self.tree.setCurrentIndex` (for example `_select_file_in_tree`, the keyboard handlers) still leaves exactly one row selected, because `setCurrentIndex` in extended mode selects the row and clears the rest only with the default flags; if a stale multi-selection survives, use `self.tree.selectionModel().setCurrentIndex(index, ClearAndSelect | Rows)`. Unit-test `top_level_paths`. Check with a scripted run: Shift+click and Ctrl+click select without opening, a plain click opens and leaves one row selected, Shift+Down extends without the preview opening anything, plain Down returns to one selected row and previews as before, Ctrl+A selects all visible rows.

Milestone 2 makes every action work on a list. For each per-item method, separate the part that asks the user and moves the selection from the part that does the work, so a bulk action can run the work part for every path and then ask once and move the selection once:

`_trash_or_delete_one(path, permanent)` does the work of `delete_item` after the dialog (save the open note first if it is inside `path`, move to Trash or delete, update tracked paths and the index) and returns `None` on success or an error message. `delete_item(path)` keeps its dialog and selection logic and calls it.

`_move_one(path, destination)` does the work of `move_item` after the folder dialog, including the taken-name check, and returns `None` or a message (for a taken name: "{name} already exists.").

`_archive_one(path)` does the work of `archive_item` without changing the selection or opening the next note, returning `None` or a message; `archive_item` calls it and then does what it does today afterwards.

`set_file_status` and `set_file_tags` already return a result; for bulk tags add a pure helper in `testlog_utils.py`, `merge_testlog_tags(current, add=(), remove=())`, which returns the new list in first-seen order, and use it with `set_file_tags`.

On top of these, add bulk methods that take the list from `_selected_tree_paths()` (reduced with `top_level_paths` where folders matter): `bulk_set_status(paths, status)`, `bulk_add_tags(paths)` and `bulk_remove_tags(paths)` (each asks once with `QInputDialog.getText`, using the existing tag completer suggestions where practical; for remove, pre-fill nothing and suggest only tags present on at least one selected note), `bulk_toggle_pin(paths)` (pin all if any is unpinned, otherwise unpin all), `bulk_archive(paths)`, `bulk_move(paths)` (one folder dialog), `bulk_delete(paths)` (one dialog: "Move {count} items to Trash?" outside Trash, "Delete {count} items? This cannot be undone." inside it), `bulk_restore(paths)`. Each counts successes, collects failure messages, refreshes the sidebar, pins and full-text index once at the end, and calls `_report_bulk_result(done, total, failures)`, which shows nothing when all succeeded, otherwise a single `QMessageBox.warning` such as "4 of 5 changed. Could not save x.testlog." (list at most five names and "and {n} more"). After archive, move or delete, select the next note in the folder of the first affected item (reuse `_next_file_in_same_folder`, computed before acting), and if the open note was among the affected items, open that next note or clear the editor, as the single-item versions do.

Unit-test `merge_testlog_tags` (add keeps existing order and appends new tags without duplicates, remove ignores tags that are absent, add and remove together, case-insensitive via the existing normalisation). Check the bulk methods with a scripted run on a scratch workspace: status and tags on five notes including the open one; archive three notes including the open one; delete a folder together with a note inside it (only the folder is trashed, no error); delete with one file made unremovable (summary reports one failure, the rest are trashed); restore two items from Trash; move two notes into a folder that already holds one of the names (one success, one "already exists" in the summary).

Milestone 3 wires the menu and keys. In `_show_tree_context_menu`, when `_selected_tree_paths()` has more than one entry and the clicked row is part of the selection, build a multi-item menu instead: for a selection inside Trash, "Restore" and "Delete"; otherwise "Status" (sub-menu), "Add tags...", "Remove tags...", "Pin to Top" or "Unpin", "Move To...", "Archive", "Delete", with entries disabled when nothing in the selection supports them (for example Status when only folders are selected). Show the count in a disabled first entry such as "5 items selected". A right-click on a row outside the selection first makes that row the only selection (this is what file managers do) and shows the normal single-item menu. `delete_selected_tree_item` calls `bulk_delete` when several items are selected. The Menu key and Shift+F10 already go through `_show_tree_context_menu` for the current row, which is part of the selection, so they get the multi-item menu. F2 does nothing when several items are selected.

Add the Swedish strings to `translations.py`: "{count} items selected": "{count} objekt markerade", "Add tags...": "Lägg till taggar...", "Remove tags...": "Ta bort taggar...", "Tags to add (comma-separated):": "Taggar att lägga till (kommaseparerade):", "Tags to remove (comma-separated):": "Taggar att ta bort (kommaseparerade):", "Move {count} items to Trash?": "Flytta {count} objekt till papperskorgen?", "Delete {count} items? This cannot be undone.": "Ta bort {count} objekt? Detta går inte att ångra.", "{done} of {total} changed.": "{done} av {total} ändrade.", "and {count} more": "och {count} till".

Check with a scripted run driving the real menu through the `QMenu` subclass and real key presses, and take screenshots of the tree with a multi-selection in both themes.

Milestone 4 adds a README Highlights line and an `AGENTS.md` note (bulk actions go through the per-item `_..._one` cores; new per-item actions should follow the same split), runs the full suite, and writes the retrospective.


## Concrete Steps

From the repository root with the project virtual environment active:

    python -m pytest -q
    ...
    215 passed

After each milestone, run it again and expect the count to rise by the new tests, with no failures. Scripted checks are throwaway files outside the repository, run as:

    XDG_CONFIG_HOME=<scratch>/xdg XDG_DATA_HOME=<scratch>/data TMPDIR=<scratch> QT_QPA_PLATFORM=offscreen .venv/bin/python -I <script>.py


## Validation and Acceptance

Automated: the full suite passes with new tests for `top_level_paths` and `merge_testlog_tags`.

Manual, with `python main.py` on a scratch workspace: Shift+click and Ctrl+click build a selection without opening notes, and a plain click opens a note and leaves only it selected. Shift+Down extends the selection; plain Down returns to one item and shows it after a short pause. With five notes selected, Status, Done turns all five dots grey; Add tags... `td` adds `td` to all five and keeps their other tags; Remove tags... `td` removes it again. Archive moves the selected notes to Archive and marks them done. Delete asks once and moves all of them to Trash; inside Trash, selecting two items and choosing Restore puts both back. With one selected note open in another program (Windows) or made read-only (Linux folder permission), a bulk action reports "N-1 of N changed" and names the file. The Menu key and Shift+F10 open the multi-item menu for the selection.


## Idempotence and Recovery

Each milestone is code plus tests and can be redone after `git checkout -- <file>`. The bulk actions reuse the existing per-item operations (atomic header rewrites, Trash moves that can be restored), so a partial failure leaves every item either fully changed or untouched. Use a scratch workspace for manual tests.


## Artifacts and Notes

Milestone 1, real window (offscreen, scratch settings), real mouse clicks and key presses:

    click a                            selected=['a.testlog'] open=a.testlog
    shift+click c                      selected=['a.testlog', 'b.testlog', 'c.testlog'] open=a.testlog
    ctrl+click b                       selected=['a.testlog', 'c.testlog'] open=a.testlog
    click d                            selected=['d.testlog'] open=d.testlog
    shift+down x2, wait                selected=['d.testlog', 'e.testlog', 'f.testlog'] open=d.testlog
    plain down, wait (preview)         selected=['f.testlog'] open=f.testlog
    ctrl+up x2, ctrl+space             selected=['d.testlog', 'f.testlog'] open=f.testlog
    expand folder, ctrl+click inner    selected=['folder/inner.testlog', 'd.testlog', 'f.testlog'] open=f.testlog
    collapse folder                    selected=['d.testlog', 'f.testlog'] open=f.testlog
    ctrl+a (folder collapsed)          selected=['folder', 'a.testlog', 'b.testlog', 'c.testlog', 'd.testlog', 'e.testlog', 'f.testlog'] open=f.testlog
    open b from code                   selected=['b.testlog'] open=b.testlog


## Interfaces and Dependencies

No new dependencies. At the end:

In `testlog_utils.py`:

    def merge_testlog_tags(current: list[str], add=(), remove=()) -> list[str]

In `trash.py` (or a small helper module):

    def top_level_paths(paths: list[str]) -> list[str]

On `MainWindow`: `_selected_tree_paths()`, `_trash_or_delete_one(path, permanent)`, `_move_one(path, destination)`, `_archive_one(path)`, `bulk_set_status`, `bulk_add_tags`, `bulk_remove_tags`, `bulk_toggle_pin`, `bulk_archive`, `bulk_move`, `bulk_delete`, `bulk_restore`, `_report_bulk_result(done, total, failures)`.


Revision note (2026-10-17): first version, written after reading the tree setup, `tree_item_clicked`, the key handling in `eventFilter`, `_show_tree_context_menu` and the per-item actions in `main.py` at commit `3fe6d0b`.
