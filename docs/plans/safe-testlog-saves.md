# Make .testlog saving, opening, renaming and moving safe

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `tests/PLANS.md` (the ExecPlan rules for this repository; the file lives in the `tests/` folder even though `AGENTS.md` refers to it simply as `PLANS.md`).


## Purpose / Big Picture

TestLog Editor stores every note as a `.testlog` file and autosaves it two seconds after the user stops typing. Today there are four ways that a user can lose work without noticing, and this plan closes all four.

After this change, a user can insert an image whose filename contains a space or a Swedish letter (for example `my shot.png` or `skärmbild.png`), close the note, reopen it, and still see the image; today the image silently disappears on the next save. A crash, a full disk, or a killed process in the middle of an autosave can no longer leave a half-written, unreadable `.testlog` file behind, because the file on disk is only replaced once the new version is completely written. Opening a damaged `.testlog` file now shows an error and leaves the note that was already open untouched, instead of wiping that note's images. Renaming or moving a file onto a name that already exists is refused with a message instead of silently overwriting the other file. Finally, when something does go wrong, the user is told (a dialog or status bar message) and the details are written to a log file, instead of the error vanishing because the packaged app has no console.

How to see it working: run `python -m pytest` and see new tests for each of the four behaviours pass; then follow the manual scenarios in `Validation and Acceptance`.


## Progress

- [x] (2026-10-17) Created `.venv` in the WSL clone (with `uv venv` + `uv pip install -r requirements.txt`; the plain `python3 -m venv` route works as well). Baseline: 53 passed.
- [x] (2026-10-17) Milestone 1: `testlog_archive.py` created (`read_testlog_note_text`, `write_testlog_archive`, `rewrite_testlog_status`); `main.py` `_write_testlog` and `_write_status_to_testlog` now call it; `collect_referenced_image_filenames` returns raw and decoded names; `tests/test_testlog_archive.py` added (3 tests). 56 passed. Smoke-tested through a real `MainWindow` (offscreen).
- [x] (2026-10-17) Milestone 1 committed as `cc6e1e8`.
- [x] (2026-10-17) Milestone 2: `_atomic_replace` in `testlog_archive.py`, used by `write_testlog_archive` and `rewrite_testlog_status`; existing permissions kept, new files get `0o666 & ~umask`. 5 tests added; 61 passed. The two failure tests fail against the Milestone 1 code (`2 failed, 6 passed`) and pass now. Real-window smoke test: file is `-rw-r--r--`, no `.tmp` left.
- [x] (2026-10-17) Milestone 2 committed as `898a5c6`.
- [x] (2026-10-17) Milestone 3: `TestlogArchiveError` and `extract_testlog_archive` in `testlog_archive.py`; `MainWindow._new_session(session_dir=None)`; `open_testlog` extracts first, warns and returns `False` on failure, returns `True` on success; the now-unused `import zipfile` removed from `main.py`; Swedish string added. 4 tests added; 65 passed. Real-window scenario run before and after (see `Artifacts and Notes`).
- [x] (2026-10-17) Milestone 4: `MainWindow._path_taken_by_other_item` and `_warn_item_exists`; `rename_item` and `move_item` refuse an existing target and report `OSError` instead of raising; 3 Swedish strings added. No unit tests (dialog-driven, as planned); scripted real-window scenario run before and after (see `Artifacts and Notes`). 65 passed.
- [ ] Milestone 5: report errors to the user and to a log file.
- [ ] Full test run, manual verification, `AGENTS.md`/`README.md` updated, retrospective written.


## Surprises & Discoveries

- Observation: the image-loss bug only affects images inserted from a file (menu "Insert Image..." or drag and drop), not pasted screenshots. Pasted screenshots are named `screenshot-<8 hex chars>.png`, which contains nothing that URL-encoding changes.
  Evidence: `main.py` `handle_image_paste` builds `f"screenshot-{uuid.uuid4().hex[:8]}.png"` and inserts it unencoded; `_copy_image_into_note` inserts `url_quote(candidate_name)`.
- Observation: images already dropped from existing files by this bug cannot be recovered by this plan; the fix only stops further loss.
- Observation: PySide6 hands an exception raised inside a slot to `sys.excepthook`, so one hook covers every timer, menu and button handler. The prototype in `Concrete Steps` was run during planning.
  Evidence: `PySide6 6.12.0 hook saw: ['ZeroDivisionError']` (offscreen, Python 3.12, 2026-10-17).
- Observation: on Windows, `os.replace` raises `PermissionError` if another program (a sync client or virus scanner) holds the target open. The old file stays intact, which is the point of the change, but the save fails. Milestone 5's save-failure reporting is what makes this visible; retrying is left to the next autosave.
  Evidence: documented `os.replace` behaviour on Windows; not reproduced here (WSL only).
- Observation: pytest tries to collect `TestlogArchiveError` as a test class because its name starts with `Test`, and warns (`PytestCollectionWarning: cannot collect test class 'TestlogArchiveError'`). The test module imports `testlog_archive` and refers to `testlog_archive.TestlogArchiveError` instead of importing the name directly.
- Observation: when opening fails, the tree selection has already moved to the damaged file (the click selected it) while the editor still shows the previous note. This is cosmetic and left as is; the next click or save behaves correctly.


## Decision Log

- Decision: fix the image matching in `collect_referenced_image_filenames` (by decoding the matched name) rather than stop encoding names when inserting them.
  Rationale: encoding is needed, because a raw space or parenthesis inside `![alt](images/my shot.png)` is not a valid Markdown link and would not render. Existing notes already contain encoded names, so decoding on the reading side fixes old and new notes alike.
  Date/Author: 2026-10-17 / Claude (plan author), for Daniel Lindkvist.
- Decision: return both the raw and the decoded form of each name from `collect_referenced_image_filenames`.
  Rationale: a file whose real name literally contains `%20` (unlikely, but possible) still matches its raw form, so no existing note can get worse than today.
  Date/Author: 2026-10-17 / Claude.
- Decision: move the archive code into a new module `testlog_archive.py` instead of patching it in place inside `main.py`.
  Rationale: `main.py` is about 5,000 lines and its functions are methods on the `MainWindow` Qt window, which cannot be unit tested without building the whole window. Plain functions that take a path and return data can be tested with `pytest` and a temporary folder. This follows the existing pattern of `testlog_utils.py`, `diff_utils.py` and `json_tools.py`.
  Date/Author: 2026-10-17 / Claude.
- Decision: the temporary file used for an atomic write lives in the same folder as the target, is named `.<target name>.<random>.tmp`, and is deleted if anything fails.
  Rationale: `os.replace` is only atomic within one filesystem, so the temporary file must sit next to the target. The leading dot and the `.tmp` suffix keep it out of the sidebar tree and the full-text index, which only show files ending in `.testlog` (`self.fs_model.setNameFilters(["*.testlog"])` and the `name.endswith(".testlog")` checks in `main.py`).
  Date/Author: 2026-10-17 / Claude.
- Decision: a brand-new file gets mode `0o666 & ~umask`, not the `0o600` that `mkstemp` gives.
  Rationale: the plan only covered keeping an existing file's mode; without this, every newly created note (save as, rename of the open note) would become owner-only, unlike before. The umask is read with the usual set-and-restore `os.umask` pair, which is only done on the GUI thread.
  Date/Author: 2026-10-17 / Claude.
- Decision: a rename or move whose target already exists is refused, not auto-renamed to `name 2.testlog`.
  Rationale: the user typed or picked that name deliberately; silently choosing another name would surprise them. The `archive_item` action keeps its existing auto-numbering because there the user did not choose the target name.
  Date/Author: 2026-10-17 / Claude.
- Decision: a failed autosave shows a status bar message every time and a dialog only once until a save succeeds again.
  Rationale: autosave can run every few seconds while typing; a dialog on every failure would make the app unusable, but the first failure must be impossible to miss.
  Date/Author: 2026-10-17 / Claude.


## Outcomes & Retrospective

Milestone 1 (2026-10-17): images inserted from files with spaces or non-ASCII letters in their names now survive saving. The archive code is in `testlog_archive.py` and covered by tests. `_write_testlog` no longer writes `note.md` into the session folder (it uses `writestr`); nothing else read that copy. Milestone 2 (2026-10-17): every write of a `.testlog` file now goes through a temporary file in the same folder and `os.replace`, so an interrupted save leaves the previous version readable. Milestone 3 (2026-10-17): opening a damaged `.testlog` shows a warning and leaves the open note, its session folder and its images untouched; before, the next autosave rewrote the open note without its images. Milestone 4 (2026-10-17): renaming or moving onto an existing name now shows "<name> already exists." and changes nothing; before, the other file was silently overwritten on Linux. The case-only rename path (`Foo` to `foo`) relies on `os.path.samefile` and was not exercised, because WSL's ext4 is case-sensitive; check it on Windows. Milestone 5 remains.


## Context and Orientation

The repository root is `/home/daniel/workspace/private/testlog-editor` (any clone works; all paths below are relative to the root). It is a PySide6 desktop app. PySide6 is the Python binding for Qt, a GUI toolkit; a "slot" in Qt is a Python function that Qt calls in response to an event such as a timer firing or a menu click.

A `.testlog` file is a zip archive. It contains `note.md` (the Markdown text, starting with a small header block between `---` lines that holds a `status:` value) and an `images/` folder with any images the note shows. Markdown refers to an image as `![alt text](images/<file name>)`.

While a note is open, the app unpacks it into a "session folder": a temporary folder created with `tempfile.mkdtemp(prefix="testlog_")` inside the operating system temp directory, stored on the window as `self.session_dir`, with the images in `self.images_dir` (`<session_dir>/images`). New images are copied or saved into that folder. On save, the app writes a fresh zip containing `note.md` and only those images that the note text still refers to, so deleting an image link from the text drops the image from the file.

The relevant code, all in `main.py` unless stated otherwise (line numbers are as of commit `d856c30` and will drift; search for the function names):

`read_testlog_note_text(path)` (a module-level function near line 1183) opens a `.testlog` and returns its text without the header, or `None` on any error. The full-text search indexer (`FullTextIndexer.run`, just below it) and `MainWindow` (near line 3556) call it.

`MainWindow._new_session()` (near line 2285) creates a new session folder and sets `self.session_dir` and `self.images_dir`.

`MainWindow.open_testlog(path)` (near line 4416) deletes the current session folder, creates a new one, extracts the zip into it, reads `note.md`, and puts the text in the editor. It is called from several places (search `open_testlog(`), none of which use a return value.

`MainWindow._write_testlog(path)` (near line 4505) writes the editor text to `<session_dir>/note.md`, then opens `path` with `zipfile.ZipFile(path, "w")` (which immediately empties the existing file) and adds `note.md` plus every file in `images_dir` whose name is in `collect_referenced_image_filenames(note_content)`. It is called by `save_file` (used by autosave and by `_flush_pending_changes`, which runs before switching files and on window close), `save_file_as`, and `rename_item`.

`MainWindow._write_status_to_testlog(path, status)` (near line 3943) changes the status of a file that is not open: it reads every entry of the zip into memory, then rewrites the file with `ZipFile(path, "w")`, again emptying it first. `set_file_status` calls it.

`MainWindow.autosave()` (near line 4387) runs from a 2-second `QTimer` (`self.autosave_timer`, set up near line 3212) and calls `save_file()`.

`MainWindow._copy_image_into_note(source_path)` (near line 3798) copies an image file into `images_dir` and returns the link target `images/<url_quote(name)>`. `url_quote` is `urllib.parse.quote`, which turns a space into `%20` and `ä` into `%C3%A4`.

`MainWindow.rename_item(path)` (near line 3959) asks for a new name. If the item is the open file, it writes the note to the new path and deletes the old one; otherwise it calls `os.rename(path, new_path)`. `MainWindow.move_item(path)` (near line 4058) asks for a folder and calls `os.rename`. On Linux and macOS `os.rename` silently replaces an existing file of the same name; on Windows it raises `FileExistsError`, which nothing catches. `MainWindow.archive_item` uses `MainWindow._available_path(path)` to pick a free name and is not changed by this plan.

`closeEvent` (near line 3379) saves pending changes and window layout; the session folder is not removed (a separate cleanup issue, out of scope here).

The block under `if __name__ == "__main__":` at the end of `main.py` creates the `QApplication` and the `MainWindow`.

In `testlog_utils.py`, `collect_referenced_image_filenames(note_content)` returns the set of names matched by `IMAGE_REFERENCE_PATTERN = r'!\[.*?\]\(images/([^)]+)\)'`, exactly as written in the text (still URL-encoded). `resolve_preview_image_path` decodes the name with `unquote` before showing it, which is why the preview keeps working while the save loses the image. `read_testlog_status_from_archive` is a similar reader used by the sidebar.

`translations.py` holds a dictionary `TRANSLATIONS["sv"]` that maps each English UI string to Swedish; `MainWindow._tr(text)` looks strings up there. Every new user-visible string in this plan needs a Swedish entry.

Tests live in `tests/` and run with `python -m pytest` from the repository root. Pure-logic tests import modules directly (see `tests/test_testlog_utils.py`). Tests that need Qt set `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before importing PySide6 and create one `QApplication` (see `tests/test_editor_smart_enter.py`). At commit `d856c30` the suite is 53 tests, all passing.


## Plan of Work

Milestone 1 creates `testlog_archive.py` and fixes the image bug. Create `testlog_archive.py` at the repository root. Move `read_testlog_note_text` from `main.py` into it unchanged and import it back into `main.py` from the new module (the indexer uses it from a background thread; that is fine because it touches no Qt objects). Add `write_testlog_archive(path, note_content, images_dir)`, which does what the zip part of `_write_testlog` does today: it writes `note_content` as the `note.md` entry (use `zf.writestr`, so there is no need to write `note.md` into the session folder first) and adds each file from `images_dir` whose name is in `collect_referenced_image_filenames(note_content)` as `images/<name>`. Add `rewrite_testlog_status(path, status)`, which does what `_write_status_to_testlog` does. In `main.py`, make `_write_testlog` call `write_testlog_archive(path, note_content, self.images_dir)` and keep the rest of its body (marking the document unmodified, stopping the timer, refreshing the index, sidebar and sort); make `_write_status_to_testlog` call `rewrite_testlog_status`. Grep for any other reader of `<session_dir>/note.md` before dropping that file write; at `d856c30` only `open_testlog` reads it, and only right after extracting it from the archive.

Then fix the bug in `testlog_utils.py`: change `collect_referenced_image_filenames` so that for every match it adds both the raw match and `unquote(match)` (`unquote` is already imported in that module, from `urllib.parse`) to the result set. Update the existing test in `tests/test_testlog_utils.py` only if it now fails; it should not, because its names contain nothing encoded.

Add `tests/test_testlog_archive.py` with a round-trip test: in a pytest `tmp_path`, create an `images` folder holding `my shot.png`, `skärmbild.png`, and an unreferenced `unused.png` (any bytes will do, for example `b"png"`); write a note whose text contains `![a](images/my%20shot.png)` and `![b](images/sk%C3%A4rmbild.png)`; call `write_testlog_archive`; open the result with `zipfile.ZipFile` and assert that its names are exactly `{"note.md", "images/my shot.png", "images/skärmbild.png"}` and that `note.md` holds the text. Add a test for `rewrite_testlog_status` that keeps the images and changes `status:`. Add a test that `read_testlog_note_text` returns `None` for a file that is not a zip. Run the round-trip test once before the `testlog_utils.py` fix to see it fail (the two encoded images are missing), then after the fix to see it pass, and record both outputs in `Artifacts and Notes`.

Milestone 2 makes writes atomic. In `testlog_archive.py`, add a private helper `_atomic_replace(path, write_fn)`. It creates a temporary file next to `path` with `tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix="." + os.path.basename(path) + ".", suffix=".tmp")`, closes the returned file descriptor, calls `write_fn(temp_path)` (which writes the complete zip to the temporary path), then, if `path` already exists, copies its permission bits onto the temporary file with `shutil.copymode(path, temp_path)` (`mkstemp` creates files readable only by the owner, and without this every save would tighten the file's permissions), and finally calls `os.replace(temp_path, path)`. If anything raises, it deletes the temporary file (ignoring a missing file) and re-raises. Use it in `write_testlog_archive` and `rewrite_testlog_status`. Note that `rewrite_testlog_status` reads the whole old archive before writing; keep that order so a failed read leaves the file untouched.

Add tests: after a successful write there is no `*.tmp` file left in the folder; when `write_fn` raises (simulate by passing an `images_dir` path that is a regular file, or by monkeypatching `zipfile.ZipFile.writestr` to raise `OSError`), the original file's bytes are unchanged and no `*.tmp` file remains; on POSIX, a file with mode `0o644` still has mode `0o644` after a rewrite (skip this test on Windows with `pytest.mark.skipif(sys.platform == "win32", ...)`).

Milestone 3 makes opening safe. In `testlog_archive.py`, add `extract_testlog_archive(path)`, which creates a fresh folder with `tempfile.mkdtemp(prefix="testlog_")`, extracts the zip into it, makes sure `<folder>/images` exists, and reads `note.md` as UTF-8 if present (returning `None` for the text if absent, as today). If extraction or decoding fails (`zipfile.BadZipFile`, `OSError`, `UnicodeDecodeError`), it deletes the new folder and raises `TestlogArchiveError` (a new exception class defined in the module, subclass of `Exception`) carrying the path and the original error as its cause. On success it returns `(session_dir, note_text)`.

In `main.py`, change `_new_session` to accept an optional `session_dir` argument: when given, it uses that folder instead of calling `mkdtemp`; the rest of its body is unchanged. Rewrite the start of `open_testlog(path)`: stop the autosave timer and close the find bar as today, then call `extract_testlog_archive(path)` inside `try`. On `TestlogArchiveError`, show `QMessageBox.warning(self, self._tr("Open testlog"), self._tr("Could not open {name}. The file may be damaged.").format(name=os.path.basename(path)))`, log the error (see Milestone 5; until then, nothing), restart the autosave timer if the editor still has unsaved changes, and return `False` without touching `self.session_dir`, `self.current_file` or the editor. On success, delete the old session folder with `shutil.rmtree(self.session_dir, ignore_errors=True)`, call `self._new_session(new_session_dir)`, and continue with the existing code that sets the status and editor text from the returned note text instead of reading `note.md` again. Return `True` at the end. Add the Swedish translation `"Could not open {name}. The file may be damaged.": "Kunde inte öppna {name}. Filen kan vara skadad."` to `translations.py`.

Add tests for `extract_testlog_archive`: a valid archive returns a folder containing `note.md` and the images and the right text; a non-zip file raises `TestlogArchiveError` and leaves no new `testlog_*` folder behind (compare the set of `testlog_*` entries in `tempfile.gettempdir()` before and after); a zip whose `note.md` is not valid UTF-8 raises `TestlogArchiveError`.

Milestone 4 guards rename and move. In `rename_item`, after computing `new_path` and the early return for an unchanged path, add: if `os.path.exists(new_path)` and not `os.path.samefile(path, new_path)`, show `QMessageBox.warning(self, self._tr("Rename"), self._tr("{name} already exists.").format(name=os.path.basename(new_path)))` and return. The `samefile` check matters on Windows and macOS, where renaming `Foo.testlog` to `foo.testlog` changes only letter case and `os.path.exists` reports the target as existing because it is the same file. In `move_item`, after the early return for an unchanged path, add the same check with the title `self._tr("Move Item")`. Wrap both `os.rename` calls (and the `_write_testlog`/`os.remove` pair for the open file in `rename_item`) in `try/except OSError`, showing `self._tr("Could not rename {name}.")` or `self._tr("Could not move {name}.")` and returning, so that a permissions error or a race with another program is reported instead of escaping the slot. Add Swedish translations: `"{name} already exists."` → `"{name} finns redan."`, `"Could not rename {name}."` → `"Kunde inte byta namn på {name}."`, `"Could not move {name}."` → `"Kunde inte flytta {name}."`. Check that `"Move Item"` and `"Rename"` already have translations (they are existing dialog titles).

These guards live in Qt dialogs, so they are verified manually (see `Validation and Acceptance`) rather than with unit tests, unless the implementer finds a cheap way to call `rename_item` with a patched `QInputDialog`; that is optional.

Milestone 5 reports errors. Create `app_logging.py` at the repository root with `setup_logging()`, which uses the standard library `logging` module and a `logging.handlers.RotatingFileHandler` (1 MB, 3 backups, UTF-8) writing to `testlog-editor.log` inside `QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)`, creating the folder if needed, and returns the log file path. It must be called after `QApplication` exists and after the application and organisation names are known. The window currently only passes names to `QSettings("TestLog Editor", "TestLog Editor")`, so in the `__main__` block call `app.setOrganizationName("TestLog Editor")` and `app.setApplicationName("TestLog Editor")` right after creating `app`; this does not change where `QSettings` stores anything because `MainWindow` passes the names explicitly. If the folder cannot be created, fall back to logging to stderr only; logging must never stop the app from starting.

In the same module, add `install_excepthook(show_error, log_path)`, which sets `sys.excepthook` to a function that logs the exception with `logging.getLogger("testlog").error(..., exc_info=(exc_type, exc, tb))` and then calls `show_error(log_path)`. PySide6 passes an exception that escapes a slot to `sys.excepthook` instead of crashing; confirm this with the prototype step in `Concrete Steps` before relying on it, and record the result in `Surprises & Discoveries`. In the `__main__` block of `main.py`, call `log_path = setup_logging()` right after creating `app`, and call `install_excepthook(show_error, log_path)` right after `window = MainWindow()`, so that `show_error` can use the window's translation function. `show_error(path)` shows `QMessageBox.critical(window, "TestLog Editor", window._tr("Something went wrong. Details were written to {path}.").format(path=path or "stderr"))`; Swedish: `"Något gick fel. Detaljer har skrivits till {path}."`. Guard the hook against re-entry: if showing the dialog itself raises, only log.

Then handle save failures explicitly, because a failed save is the most important error. In `save_file`, wrap the `_write_testlog(self.current_file)` call in `try/except (OSError, zipfile.BadZipFile)`: log the exception, call `self._report_save_failure(self.current_file)`, and return `False`. Do the same in `save_file_as`. Because `_flush_pending_changes` returns what `save_file` returns, a failed save on close or on switching files now returns `False`, which already stops the window from closing (`closeEvent` calls `event.ignore()` on `False`) and stops the switch; that is the desired behaviour, since closing would lose the unsaved text. Add `_report_save_failure(path)`: it shows `self.statusBar().showMessage(self._tr("Could not save {name}").format(...))` with no timeout, and, if `self._save_failure_reported` is `False`, also shows a `QMessageBox.warning` with `"Could not save {name}. Your changes are still in the editor. Details were written to the log."` and sets the flag. Set `self._save_failure_reported = False` in `__init__` and again at the end of every successful `_write_testlog`. In `autosave`, only show the "Autosaved" message when `save_file()` returned `True`. Swedish: `"Could not save {name}"` → `"Kunde inte spara {name}"`, and the long message → `"Kunde inte spara {name}. Dina ändringar finns kvar i editorn. Detaljer har skrivits till loggen."`.

Wrap `set_file_status`'s call to `_write_status_to_testlog` the same way (log, status bar message, no dialog flag needed). In `read_testlog_note_text` (now in `testlog_archive.py`), keep returning `None` on error but log the exception at `warning` level with the path, using `logging.getLogger("testlog")`; logging calls before `setup_logging` are harmless.

Finally update `AGENTS.md` (the "File And State Side Effects" section: mention the log file location and the `.<name>.<random>.tmp` files that may briefly appear next to a `.testlog` during a save) and `README.md` (a short "Troubleshooting" note giving the log file location). No new dependencies are added, so `requirements.txt` and `testlog.spec` do not change, except: add `"testlog_archive"` and `"app_logging"` to `hiddenimports` in `testlog.spec` only if a test build shows PyInstaller missing them (it normally follows imports from `main.py` on its own).


## Concrete Steps

All commands run from the repository root. Create the virtual environment once if `.venv` does not exist (it does not exist in the WSL clone at the time of writing; the pre-commit hook in `.githooks/pre-commit` refuses commits without it):

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt

Baseline before any change:

    python -m pytest -q
    ...
    53 passed

After Milestone 1, run the round-trip test once before the `testlog_utils.py` fix and once after:

    python -m pytest -q tests/test_testlog_archive.py
    (before the fix) FAILED ... AssertionError ... missing 'images/my shot.png', 'images/skärmbild.png'
    (after the fix)  all passed

Prototype for Milestone 5 (confirms that PySide6 routes exceptions raised inside a slot to `sys.excepthook`). Save this as a file in a scratch folder outside the repository and run it with the venv's Python:

    import sys
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    seen = []
    sys.excepthook = lambda *exc: seen.append(exc[0].__name__)
    QTimer.singleShot(0, lambda: 1 / 0)
    QTimer.singleShot(50, app.quit)
    app.exec()
    print("hook saw:", seen)

With `QT_QPA_PLATFORM=offscreen` set, the expected output is `hook saw: ['ZeroDivisionError']`. If the list is empty, record that in `Surprises & Discoveries` and instead wrap the bodies of the slots that touch the filesystem (`autosave`, `rename_item`, `move_item`, `archive_item`, `set_file_status`, `delete_item`) in `try/except Exception` that logs and reports.

After each milestone:

    python -m pytest -q

and expect the count to rise by the tests added in that milestone, with zero failures.


## Validation and Acceptance

Automated: `python -m pytest -q` passes, with the 53 original tests plus the new ones in `tests/test_testlog_archive.py` (round trip with encoded image names, status rewrite keeps images, invalid file read returns `None`, atomic write leaves no temp files, failed write keeps the original bytes, permissions kept on POSIX, safe extraction of valid, non-zip and non-UTF-8 files). The round-trip test fails before Milestone 1's fix and passes after.

Manual, with `python main.py` and a scratch workspace folder containing copies of a few `.testlog` files (never the real workspace):

Image names: create a note, use "Insert Image..." to add a picture file named `my shot.png`, wait for "Autosaved", open another file, reopen the first. The image is visible. Before the fix it is shown as a broken image after reopening.

Damaged file: create `broken.testlog` containing plain text (`echo hello > broken.testlog`). Open a good note that has an image, then click `broken.testlog`. A warning says the file could not be opened; the good note is still shown with its image; edit it, wait for "Autosaved", reopen it, and the image is still there.

Rename and move: create `a.testlog` and `b.testlog`. Rename `a` to `b`: a warning says `b.testlog already exists.` and both files still exist with their own content. Move `a.testlog` into a folder that already has an `a.testlog`: same warning, nothing overwritten. Rename `a` to `A` (letter case only): allowed.

Save failure: open a note, then make its file read-only from outside the app on Linux (`chmod a-w` on the containing folder, because `os.replace` needs write access to the folder), type a character and wait. The status bar shows "Could not save …" and one dialog appears; further typing does not produce more dialogs. Closing the window is refused while the save keeps failing. Restore permissions (`chmod u+w` on the folder), type again, and the next autosave succeeds and the message clears. The log file (`~/.local/share/TestLog Editor/TestLog Editor/testlog-editor.log` on Linux; print the path from `setup_logging()` if unsure) contains the traceback.

Autosave still works for ordinary editing, and the `AGENTS.md` manual checklist (Enter, Tab, Shift+Tab, bold/italic, pasted images) still behaves as before.


## Idempotence and Recovery

Every step is a code edit plus tests, so it can be redone by resetting the files with `git checkout -- <file>` and repeating it. The milestones are ordered so the suite passes after each one; commit after each milestone, but only when the repository owner asks, as their instructions require. Manual testing must use a scratch workspace with copies of files, because this plan is about code that writes and deletes `.testlog` files. A crash during an atomic save after this plan can leave a stray `.<name>.<random>.tmp` file next to a note; it is safe to delete.


## Artifacts and Notes

Milestone 1, round-trip test before the `testlog_utils.py` fix:

    tests/test_testlog_archive.py:23: AssertionError
    E   AssertionError: assert {'note.md'} == {'images/my s...g', 'note.md'}
    1 failed, 2 passed

After the fix, full suite: `56 passed`.

Milestone 1, end-to-end through `MainWindow` (offscreen, settings redirected with `XDG_CONFIG_HOME` to a scratch folder): `_copy_image_into_note("my shot.png")`, `save_file()`, `open_testlog()`:

    link: images/my%20shot.png
    archive: ['images/my shot.png', 'note.md']
    reopened image exists: True

Milestone 3, real window: save `good.testlog` with an image, open it, open a plain-text `broken.testlog`, type, save. Against commit `898a5c6` (before):

    open broken returned: BadZipFile
    session unchanged: False
    image still in session: False
    good archive after save: ['note.md']

After:

    open broken returned: False
    warning: ['Could not open broken.testlog. The file may be damaged.']
    current file still good: True
    session unchanged: True
    image still in session: True
    good archive after save: ['images/shot.png', 'note.md']

Milestone 4, real window with `QInputDialog` and `QFileDialog` patched to return scripted answers; files `a`, `b`, `open` and `sub/a` each hold "content <name>". Before (commit `898a5c6`):

    rename a->b:      a = MISSING | b = content a
    rename open->b:   open = MISSING | b = content open
    FileNotFoundError ... (the old move then failed because a.testlog was already gone)

After:

    rename a->b:      a = content a | b = content b
    rename open->b:   open = content open | b = content b
    move a->sub/:     a = content a | sub/a = content a-sub
    rename a->c:      a = MISSING | c = content a
    warnings: ['b.testlog already exists.', 'b.testlog already exists.', 'a.testlog already exists.']

To be filled in later: the final `pytest` summary line.


## Interfaces and Dependencies

No new third-party dependencies. Standard library only: `zipfile`, `tempfile`, `os`, `shutil`, `logging`, `logging.handlers`, `urllib.parse`. Qt pieces used: `QStandardPaths`, `QMessageBox`, already available through PySide6.

At the end, `testlog_archive.py` exports:

    class TestlogArchiveError(Exception): ...

    def read_testlog_note_text(path: str) -> str | None
        # note text without the status header, or None if unreadable

    def write_testlog_archive(path: str, note_content: str, images_dir: str) -> None
        # atomically replaces path; packs only images referenced by note_content

    def rewrite_testlog_status(path: str, status: str) -> None
        # atomically replaces path with the same entries and an updated status

    def extract_testlog_archive(path: str) -> tuple[str, str | None]
        # new session folder and note text; raises TestlogArchiveError and cleans up on failure

`testlog_utils.collect_referenced_image_filenames(note_content: str) -> set[str]` returns both the raw and the URL-decoded form of each referenced name.

`app_logging.py` exports:

    def setup_logging() -> str | None
        # returns the log file path, or None if only stderr logging is active

    def install_excepthook(show_error: Callable[[str], None], log_path: str | None) -> None

`MainWindow` gains `_report_save_failure(path)`, `_new_session(session_dir=None)`, and `open_testlog(path)` returns `bool`.


Revision note (2026-10-17): first version, written after a read-only review of `main.py` at commit `d856c30`.
