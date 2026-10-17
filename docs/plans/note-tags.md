# Tag notes and filter the sidebar by tag

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `tests/PLANS.md` (the ExecPlan rules for this repository; the file lives in the `tests/` folder even though `AGENTS.md` refers to it simply as `PLANS.md`).


## Purpose / Big Picture

TestLog Editor users keep many notes for different products and kinds of work, for example notes about the "TDialog" product and meeting notes. Today the only ways to group them are folders (a note can be in only one) and the file name. After this change a user can give any note one or more short tags such as `td` and `meet`, see those tags next to the note in the sidebar, and type `#td` in the sidebar search box to see only the notes tagged `td`, across every folder.

How to see it working: open a note, type `td, meet` into the new tag field in the toolbar and press Enter; the sidebar shows `td · meet` in grey after the note's name. Type `#td` in the sidebar search box and only notes tagged `td` remain visible. Right-click another note, choose "Tags...", enter `TD`, and it appears in the `#td` results too, because tags are case-insensitive.

Sorting the tree by tag was discussed and deliberately left out of this plan (see `Decision Log`).


## Progress

- [x] (2026-10-17) Milestone 1: `normalize_testlog_tags`, `format_testlog_tags`, `get_testlog_tags`, `set_testlog_tags`, `read_testlog_header_from_archive` in `testlog_utils.py` (`read_testlog_status_from_archive` now wraps the header reader); `rewrite_testlog_note` and `rewrite_testlog_tags` in `testlog_archive.py` (`rewrite_testlog_status` now uses `rewrite_testlog_note`). 20 tests added; 97 passed.
- [x] (2026-10-17) Milestone 1 committed as `2a715f9`.
- [x] (2026-10-17) Milestone 2: `TESTLOG_TAGS_ROLE`, header cache (`_header_for_path`, `tags_for_path`), tags in the tooltip, `parse_sidebar_search` and `sidebar_search_matches` in `workspace_models.py`; tags drawn in `WorkspaceTreeItemDelegate`; folder matching now decided from the files on disk and the tree re-expanded on `directoryLoaded` (see `Surprises & Discoveries`). `tests/test_workspace_search.py` (11 tests); 108 passed. Scripted real-window run and screenshots (see `Artifacts and Notes`).
- [x] (2026-10-17) Milestone 2 committed as `ae0958b`.
- [x] (2026-10-17) Milestone 3: `TagLineEdit` and `TagCompleter` in `main.py`; toolbar tag field with suggestions from `_known_workspace_tags` (Archive skipped); `_on_tags_edit_finished`, `_sync_tags_from_editor`; right-click "Tags..." with `edit_file_tags` / `set_file_tags` (plus a small `_is_open_file` helper); 3 Swedish strings. No new unit tests (Qt-dialog driven); scripted real-window run and toolbar screenshots (see `Artifacts and Notes`). 108 passed.
- [x] (2026-10-17) Milestone 3 committed as `e8f2791`.
- [x] (2026-10-17) Milestone 4: `README.md` (Highlights) and `AGENTS.md` (new "Note Header" section) updated; full test run 108 passed; retrospective written.
- [ ] Manual check on a real display (Windows build): the `Validation and Acceptance` scenarios, especially completion popup behaviour and the sidebar at the user's real width.


## Surprises & Discoveries

- Observation: a single piece such as `"x y"` inside a list passed to `normalize_testlog_tags` is split into two tags, because lists are split with the same comma/whitespace rule as strings. This is intended (a tag cannot contain a space) and covered by a test.
  Evidence: `normalize_testlog_tags(["TD", "x y"]) == ["td", "x", "y"]`.
- Observation: the sidebar search (already before this plan) only found notes in folders the tree had loaded. `QFileSystemModel` loads a folder's contents only when it is expanded, and `_directory_contains_match` counted loaded rows, so collapsed folders looked empty and were hidden, and `expandAll()` never reached them. `#td` across folders could not work without fixing this.
  Evidence: at commit `2a715f9`, searching `login` in a scratch workspace showed `misc/untagged-login` but not `tdialog/login-flow`.
- Observation: with tags capped at 40 percent of the row width, as first planned, the default 200-pixel sidebar cut most note names to a few letters (`weekly-s…`, `td-…`), which broke the plan's own "names stay readable" acceptance.


## Decision Log

- Decision: store tags in the note's header as a `tags:` line, next to the existing `status:` line.
  Rationale: the header already exists in every saved note, travels with the file when it is renamed, moved or archived, and is preserved by the existing code that rewrites the header (`set_testlog_status` keeps every header line it does not own). A file-name prefix such as `TD - login.testlog` was rejected because it allows only one tag and is lost on rename.
  Date/Author: 2026-10-17 / Claude, agreed with Daniel Lindkvist.
- Decision: tags are case-insensitive and stored in lowercase.
  Rationale: requested by the user; it stops `TD` and `td` from becoming two different tags.
  Date/Author: 2026-10-17 / Daniel Lindkvist.
- Decision: no "sort by tag" mode in this plan.
  Rationale: the user chose items 1-3 of the proposal (set tags, show tags, filter by `#tag`). The sidebar tree is built from folders, so tags cannot become real group headings across folders; filtering is the way to see all notes with one tag. Sorting within a folder can be added later in `WorkspaceSortProxyModel.lessThan`.
  Date/Author: 2026-10-17 / Daniel Lindkvist.
- Decision: a tag is one word made of letters, digits, `-` and `_`; tags are separated by commas or spaces; a leading `#` is dropped; duplicates are removed while keeping the first order.
  Rationale: `#td` must be usable in the search box, so a tag cannot contain spaces; accepting both commas and spaces means `td, meet`, `td meet` and `#td #meet` all give the same result, so the user does not need to remember a format. Letters include Swedish letters (Python's `str.isalnum` accepts them).
  Date/Author: 2026-10-17 / Claude.
- Decision: fix the collapsed-folder search problem inside Milestone 2: `WorkspaceSortProxyModel.set_search` walks the workspace on disk (`os.walk` from the file model's root path) once per search and records every folder that contains a match (`_matching_dirs`); `_directory_contains_match` looks folders up there, always accepting the workspace root and the folders above it so the tree keeps its root; and `MainWindow._on_tree_directory_loaded` (connected to `QFileSystemModel.directoryLoaded`) calls `expandAll()` again while a search is active, so matches inside folders that load later become visible. Paths are compared after `os.path.normcase(os.path.normpath(...))` because the file model uses `/` on Windows.
  Rationale: the feature's main purpose, finding all notes with a tag across folders, depends on it, and the same fix makes plain-text search find notes in collapsed folders.
  Date/Author: 2026-10-17 / Claude.
- Decision: tags get only the space the full note name does not need, and are hidden (tooltip only) when less than 28 pixels remain, replacing the planned 40 percent cap.
  Rationale: the sidebar defaults to 200 pixels; names must win. Widening the sidebar (up to 350 pixels) shows the tags.
  Date/Author: 2026-10-17 / Claude.
- Decision: tag suggestions in the toolbar come from reading the headers of all `.testlog` files in the workspace on demand, through the same per-file cache the sidebar uses, instead of extending the full-text indexer thread.
  Rationale: the indexer (`Indexer` in `main.py`) reads note text without the header and reports through a Qt signal with a fixed signature; changing it touches the full-text search dialog too. A workspace has at most a few hundred notes, and reading a zip header takes well under a millisecond, so an on-demand scan with a cache keyed on modification time is fast enough and keeps the change local. Revisit if a workspace grows to thousands of notes.
  Date/Author: 2026-10-17 / Claude.


## Outcomes & Retrospective

Milestone 1 (2026-10-17): tags can be read from and written to the note header and to closed `.testlog` files, case-insensitively, without disturbing `status:`, the body or images. Nothing in the UI uses them yet. Milestone 2 (2026-10-17): tags show in the sidebar and tooltip, and `#tag` search works across collapsed folders; plain-text search also gained that. Milestone 3 (2026-10-17): tags can be edited from the toolbar field, with suggestions for the tag being typed, from the note header itself, and from the right-click menu for notes that are not open.

Overall (2026-10-17): notes can carry case-insensitive tags in their header, set from the toolbar (with suggestions), the right-click menu or the header itself; the sidebar shows them where there is room and in the tooltip, and `#tag` in the sidebar search finds tagged notes in any folder, collapsed or not. The suite grew from 77 to 108 tests. Two things went beyond the original plan and are recorded in the `Decision Log`: the fix for search ignoring collapsed folders (it affected plain-text search too), and giving note names priority over tags in narrow sidebars. Not done: sorting by tag (out of scope by choice), and a check on a real display; every run here was offscreen in WSL. Lesson: screenshots of the real widgets caught the tag-width problem that no unit test would have.


## Context and Orientation

The repository root is the folder containing `main.py` (all paths below are relative to it). TestLog Editor is a PySide6 desktop app; PySide6 is the Python binding for the Qt GUI toolkit.

A `.testlog` file is a zip archive containing `note.md` (the note in Markdown) and an `images/` folder. `note.md` starts with a header block, called "front matter", between two lines of three dashes:

    ---
    status: doing
    ---
    # The note's title
    ...

The editor shows this header as ordinary text at the top of the note, so a user can also type in it directly.

`testlog_utils.py` holds the header helpers. `split_testlog_front_matter(text)` returns `(header_lines, body, has_front_matter)`. `get_testlog_status(text)` reads the `status:` line. `set_testlog_status(text, status)` writes the `status:` line and keeps every other header line untouched; if the text has no header it creates one. `read_testlog_status_from_archive(path)` opens a `.testlog` and returns its status, or the default `todo` on any error. `STATUS_KEY_PATTERN` is the regular expression for the `status:` line.

`testlog_archive.py` reads and writes `.testlog` files. `rewrite_testlog_status(path, status)` changes the status of a file that is not open in the editor: it reads every entry, updates the header in `note.md`, and replaces the file atomically (it writes a temporary file next to it and swaps it in with `os.replace`, through the private helper `_atomic_replace`).

`workspace_models.py` holds the two Qt "models" behind the sidebar tree. A model is the object a Qt view asks for the data of each row; a "role" is the kind of data asked for (display text, tooltip, icon, or a custom number). `WorkspaceFileSystemModel` (a `QFileSystemModel`, which lists the files of a folder and loads sub-folders lazily, that is, only when they are expanded or asked for) answers a custom role `TESTLOG_STATUS_ROLE` with each note's status. It caches the status per path together with the file's modification time (`_status_cache`, `_status_for_path`), so each file is opened only once until it changes. `refresh_status(path)` drops the cache entry and tells the view to repaint the row. `WorkspaceSortProxyModel` (a `QSortFilterProxyModel`, which sits between the file model and the view and hides or reorders rows) decides which rows are visible in `filterAcceptsRow`: when the search box has text (`set_search` stores it lowercased in `search_term`), a file is visible if its name contains that text, and a folder is visible if anything inside it matches (`_directory_contains_match`).

In `main.py`:

`WorkspaceTreeItemDelegate` (near line 1633; a "delegate" is the object that paints one row of a Qt view) paints each sidebar row: it lets Qt paint the name and icon in a slightly narrower rectangle and then draws a 10-pixel coloured status dot at the right edge. Its `STATUS_COLORS` table holds the dot colours.

The sidebar search box is `self.sidebar_search`. Typing starts `self.sidebar_search_timer`; when it fires, `_apply_sidebar_search` calls `self.fs_proxy_model.set_search(text)` and expands the whole tree so matches inside folders are visible.

The toolbar is built in `_setup_toolbar`. The status drop-down is `self.status_combo`; choosing a value runs `_on_status_combo_changed`, which writes the new `status:` line into the editor text with `set_testlog_status`, marks the document modified and starts the autosave timer. The opposite direction, a user typing in the header, is handled by `_sync_status_from_editor`, connected to `self.editor.textChanged`, which reads the status from the editor text and updates the drop-down. `_set_status_combo` updates the drop-down without triggering its handler.

`show_context_menu` builds the right-click menu of a tree row; for a file it has a "Status" sub-menu whose choice calls `set_file_status(path, status)`. `set_file_status` updates the editor for the open note and saves it, or calls `_write_status_to_testlog` (which calls `rewrite_testlog_status`) for any other note, then refreshes the tree row with `self.fs_model.refresh_status(path)`. It returns `True` on success and `False` on failure (failures are logged and shown in the status bar).

When a note is saved, `_write_testlog` runs `set_testlog_status(self.editor.toPlainText(), self.current_status)` and writes the result; since that keeps other header lines, a `tags:` line in the editor text is saved as is.

`translations.py` holds `TRANSLATIONS["sv"]`, mapping English UI strings to Swedish; `MainWindow._tr(text)` looks them up, and `_retranslate_ui` sets every menu and widget text so the language can switch at runtime.

Tests live in `tests/` and run with `python -m pytest` from the repository root (with the `.venv` activated). Qt-free helper tests import modules directly (see `tests/test_testlog_utils.py`, `tests/test_testlog_archive.py`). Tests that need Qt set `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before importing PySide6. At commit `451b055` the suite has 77 tests, all passing.


## Plan of Work

Milestone 1 adds tags to the header. In `testlog_utils.py`, add `TAGS_KEY_PATTERN = re.compile(r"^tags\s*:\s*(.*?)\s*$", re.IGNORECASE)` next to `STATUS_KEY_PATTERN`. Add `normalize_testlog_tags(value)`: it accepts a string or a list of strings, splits strings on commas and whitespace, strips a leading `#` from each piece, lowercases it, keeps only pieces made entirely of characters for which `ch.isalnum() or ch in "-_"` is true, and drops empty pieces and duplicates while keeping first-seen order; it returns a list. Add `format_testlog_tags(tags)`, which returns `", ".join(tags)`. Add `get_testlog_tags(text)`, which returns `normalize_testlog_tags` of the `tags:` header line, or `[]` when there is no header or no such line. Add `set_testlog_tags(text, tags)`, modelled on `set_testlog_status`: it normalizes the tags; if the list is empty it removes any `tags:` line (and, if the text had no header, returns the text unchanged rather than creating an empty header); otherwise it writes `tags: <formatted>` in place of the first existing `tags:` line, removes any further `tags:` lines, or appends the line after the existing header lines; if there is no header at all it creates one containing only the `tags:` line. Add `read_testlog_header_from_archive(path)`, which returns `(status, tags)` read from `note.md` in one pass, or `(DEFAULT_TESTLOG_STATUS, [])` on any error; keep `read_testlog_status_from_archive` as a thin wrapper around it so existing callers do not change.

In `testlog_archive.py`, generalize the status rewrite: add `rewrite_testlog_note(path, update_fn)`, which contains today's body of `rewrite_testlog_status` but applies `update_fn(note_text)` instead of `set_testlog_status(note_text, status)`; make `rewrite_testlog_status(path, status)` call `rewrite_testlog_note(path, lambda text: set_testlog_status(text, status))`; add `rewrite_testlog_tags(path, tags)` the same way with `set_testlog_tags`.

Add tests to `tests/test_testlog_utils.py`: normalization (`"TD, meet"`, `"#td #Meet td"`, `"td,,  meet "`, `["TD", "x y"]` all give `["td", "meet"]` or the expected list; `"bad!tag"` is dropped; `"möte"` is kept); `get_testlog_tags` with and without a header; `set_testlog_tags` adding, replacing, removing, keeping the `status:` line and the body untouched, and leaving header-less text unchanged when given no tags; `set_testlog_status` keeps a `tags:` line. Add to `tests/test_testlog_archive.py`: `rewrite_testlog_tags` keeps images and status, and `read_testlog_header_from_archive` returns both values and the default pair for a non-zip file.

Milestone 2 shows tags and filters by them. In `workspace_models.py`, add `TESTLOG_TAGS_ROLE = Qt.ItemDataRole.UserRole + 21`. Replace `_status_cache` with `_header_cache` holding `(modified_time, status, tags)` per path, filled by `read_testlog_header_from_archive`; add `_header_for_path(path)` returning `(status, tags)` (`("todo", [])` when the file cannot be read), make `_status_for_path` use it, and add a public `tags_for_path(path)`. Answer `TESTLOG_TAGS_ROLE` in `data()` for `.testlog` files, the same way as the status role. In `refresh_status`, include `TESTLOG_TAGS_ROLE` in the roles it reports as changed. In `_build_tooltip`, add a line `Taggar:  td, meet` under the status line when the note has tags (the tooltip is currently Swedish-only; keep that style).

Still in `workspace_models.py`, add a module-level pure function `parse_sidebar_search(text)` that returns `(name_term, tag_terms)`: every whitespace-separated word starting with `#` (and longer than just `#`) becomes a tag term (normalized with `normalize_testlog_tags`), and the remaining words, joined with single spaces and lowercased, form the name term. Add `sidebar_search_matches(name_term, tag_terms, filename, tags)`: true when `name_term` is empty or is contained in `filename.lower()`, and every tag term is in `tags`. A tag term matches a whole tag only, so `#td` does not match the tag `tdialog`; this keeps results predictable. In `WorkspaceSortProxyModel`, make `set_search` store both parts, and make both `filterAcceptsRow` and `_directory_contains_match` call `sidebar_search_matches` with the file's name and `self._source_model.tags_for_path(path)` (folders themselves are never matched by tags, only through their contents, as today). Only `.testlog` files can carry tags; other files have `[]`.

In `main.py`, extend `WorkspaceTreeItemDelegate.paint`: read `index.data(TESTLOG_TAGS_ROLE)`; when it is a non-empty list, build the text `" · ".join(tags)`, measure it with `option.fontMetrics`, cap its width at 40 percent of the row width (eliding the end with `elidedText` if longer), shrink the rectangle given to `super().paint` by that width plus 8 pixels, and draw the text right-aligned in the freed space, just left of the status dot, using `option.palette.color(QPalette.ColorRole.PlaceholderText)` as the pen colour so it reads as secondary text in both light and dark themes. Import `TESTLOG_TAGS_ROLE` from `workspace_models` and `QPalette` from `PySide6.QtGui` if not already imported.

Add `tests/test_workspace_search.py` with tests for `parse_sidebar_search` (`"#td login"` gives `("login", ["td"])`; `"#TD #meet"` gives `("", ["td", "meet"])`; `"#"` alone is treated as name text) and `sidebar_search_matches` (name only, tag only, both, a tag the file lacks, and that `#td` does not match `tdialog`).

Milestone 3 lets the user edit tags. In `_setup_toolbar`, right after the status drop-down, add `self.tags_edit = QLineEdit()` with a fixed width of about 180 pixels, a placeholder from `self._tr("Tags")` (set in `_retranslate_ui`), and `editingFinished` connected to `_on_tags_edit_finished`. `_on_tags_edit_finished` normalizes the field's text, writes it back to the field in normalized form, and, if it differs from `get_testlog_tags(self.editor.toPlainText())`, updates the editor text with `set_testlog_tags`, marks the document modified and starts `self.timer` and `self.autosave_timer`, exactly as `_on_status_combo_changed` does. Add `_sync_tags_from_editor`, connected to `self.editor.textChanged` next to `_sync_status_from_editor`; it updates the field (with signals blocked) to `format_testlog_tags(get_testlog_tags(...))` unless the field currently has keyboard focus, so typing in the field is never overwritten. Also call it after `open_testlog` and `new_file` load text, if `textChanged` does not already cover that (check by observation and record the result).

For suggestions, attach a `QCompleter` to the field. A plain completer completes the whole field, which is wrong for a comma-separated list, so subclass it as `TagCompleter` (in `main.py`, near the other small widget classes): override `splitPath(path)` to return only the text after the last comma or space, and override `pathFromIndex(index)` to return the field's text with that last word replaced by the chosen tag followed by `", "`. Give it a `QStringListModel` and case-insensitive matching. Fill the model when the field gets focus (install an event filter or subclass `QLineEdit` and override `focusInEvent`), with `self._known_workspace_tags()`: walk `self.workspace_dir` with `os.walk`, skip the top-level `Archive` and `Arkiv` folders as `_open_most_recent_testlog` does, and collect `self.fs_model.tags_for_path(path)` for every `.testlog`, returning a sorted list of unique tags.

In `show_context_menu`, for files add `tags_action = menu.addAction(self._tr("Tags..."))` after the Status sub-menu. When chosen, call a new `edit_file_tags(path)`: it reads the current tags (from the editor for the open note, otherwise from `self.fs_model.tags_for_path(path)`), shows `QInputDialog.getText(self, self._tr("Tags"), self._tr("Tags (comma-separated):"), text=format_testlog_tags(current))`, and on OK calls a new `set_file_tags(path, tags)`, which mirrors `set_file_status`: for the open note it updates the editor text and saves with `self.save_file()`; otherwise it calls `rewrite_testlog_tags` inside `try`, logs and shows `"Could not save {name}"` in the status bar on failure, and returns `False`; on success it calls `self.fs_model.refresh_status(path)` and `self._refresh_sidebar_sort()` and returns `True`. Note that `refresh_status` drops the whole header cache entry, so the new tags are read on the next paint.

Add Swedish translations to `translations.py`: `"Tags": "Taggar"`, `"Tags...": "Taggar..."`, `"Tags (comma-separated):": "Taggar (kommaseparerade):"`.

Milestone 4 updates `README.md` (one line under Highlights: tags in the note header, `#tag` in the sidebar search) and `AGENTS.md` (the `tags:` header line next to `status:`, and that `TESTLOG_TAGS_ROLE` exists), runs the full test suite and the manual checks below, and fills in `Outcomes & Retrospective`.


## Concrete Steps

From the repository root, with the virtual environment active (`source .venv/bin/activate` on Linux, `source .venv/Scripts/activate` in Git Bash on Windows):

    python -m pytest -q
    ...
    77 passed

After each milestone, run the same command and expect the count to rise by the tests added, with no failures.

For Milestone 3, check the behaviour through the real window without a display, as earlier plans in `docs/plans/` did: write a small script outside the repository that sets `QT_QPA_PLATFORM=offscreen` and points `XDG_CONFIG_HOME` at a scratch folder (so the user's real `QSettings` are untouched), creates a scratch workspace with three notes, opens the window with `MainWindow()`, calls `_set_workspace`, sets tags through `tags_edit` (`setText` then `editingFinished.emit()`) and through `set_file_tags`, and prints `get_testlog_tags` of each file plus which rows remain visible after `self.fs_proxy_model.set_search("#td")`. Expected: only the notes tagged `td` (in any letter case when they were entered) remain visible, and their header contains `tags: td...` in lowercase.


## Validation and Acceptance

Automated: `python -m pytest -q` passes with the 77 existing tests plus the new ones in `tests/test_testlog_utils.py`, `tests/test_testlog_archive.py` and `tests/test_workspace_search.py`.

Manual, with `python main.py` and a scratch workspace holding copies of a few notes (never the real workspace):

Open a note, type `TD, meet` in the toolbar tag field and press Enter. The field shows `td, meet`, the header in the editor shows `tags: td, meet`, the sidebar row shows `td · meet` in grey left of the status dot, and after the "Autosaved" message the file on disk has the same header (close and reopen the note to see it). Type `#td` in the sidebar search: only notes tagged `td` remain, from every folder, with their folders expanded. Type `#td login`: only `td` notes whose file name contains `login`. Clear the search: the tree returns to its previous expanded state.

Right-click a note that is not open, choose "Tags...", enter `Meet`, press OK: its row shows `meet` and `#meet` finds it. In the tag field, type `m`: the suggestion list offers `meet`. Type directly in the editor header, changing `tags: td, meet` to `tags: td`: the toolbar field follows when the editor has focus. Switch the language to Swedish: the field's placeholder and the menu item read "Taggar" and "Taggar...".

Long tags do not hide the note name: with tags `alpha, beta, gamma, delta, epsilon` the grey text is cut with an ellipsis and the name stays readable.


## Idempotence and Recovery

Every milestone is code plus tests and can be redone after `git checkout -- <file>`. Tag writes go through the same atomic save as status changes, so a failed write leaves the note unchanged. Commit after each milestone only when the repository owner asks. Use a scratch workspace with copied notes for manual checks.


## Artifacts and Notes

Milestone 2, real window (offscreen, scratch settings), workspace with notes in `tdialog/`, `meetings/`, `misc/` and `misc/deep/`, all folders collapsed before searching:

    '#td'          -> ['misc/deep/td-meeting-notes', 'tdialog/checkout', 'tdialog/login-flow']
    '#TD login'    -> ['tdialog/login-flow']
    '#meet'        -> ['meetings/weekly-sync', 'misc/deep/td-meeting-notes']
    '#td #meet'    -> ['misc/deep/td-meeting-notes']
    'login'        -> ['misc/untagged-login', 'tdialog/login-flow']
    '#tdialog'     -> []
    tooltip: 'Status:   Doing\nTaggar:   td, login\n...'

Sidebar screenshots were checked in light and dark mode at the default and the maximum sidebar width.

Milestone 3, real window (offscreen, scratch settings; key presses sent with `QTest`):

    field after open: ''
    suggestions (Archive skipped): ['regression']
    completion for 'TD, reg': TD, regression,  | popup visible: True
    field after Enter: 'td, meet'
    editor header: ['status: doing', 'tags: td, meet']
    on disk after autosave: ('doing', ['td', 'meet'])
    field after editing header in editor: 'td'
    closed note via Tags...: ('todo', ['meet', 'td']) | body kept: # meetings/weekly
    #td now shows: ['meetings/weekly.testlog', 'tdialog/login.testlog']
    sv placeholder: Taggar

Opening a note fills the field through `textChanged`, so no extra call in `open_testlog` or `new_file` was needed.


## Interfaces and Dependencies

No new dependencies; PySide6's `QCompleter`, `QStringListModel`, `QLineEdit` and `QInputDialog` are already available.

At the end, these exist:

In `testlog_utils.py`:

    TAGS_KEY_PATTERN: re.Pattern
    def normalize_testlog_tags(value: str | list[str] | None) -> list[str]
    def format_testlog_tags(tags: list[str]) -> str
    def get_testlog_tags(text: str) -> list[str]
    def set_testlog_tags(text: str, tags: str | list[str]) -> str
    def read_testlog_header_from_archive(path: str) -> tuple[str, list[str]]

In `testlog_archive.py`:

    def rewrite_testlog_note(path: str, update_fn: Callable[[str], str]) -> None
    def rewrite_testlog_tags(path: str, tags: str | list[str]) -> None

In `workspace_models.py`:

    TESTLOG_TAGS_ROLE = Qt.ItemDataRole.UserRole + 21
    def parse_sidebar_search(text: str) -> tuple[str, list[str]]
    def sidebar_search_matches(name_term: str, tag_terms: list[str], filename: str, tags: list[str]) -> bool
    WorkspaceFileSystemModel.tags_for_path(path: str) -> list[str]

In `main.py`: `TagCompleter(QCompleter)`, and on `MainWindow`: `tags_edit`, `_on_tags_edit_finished`, `_sync_tags_from_editor`, `_known_workspace_tags`, `edit_file_tags(path)`, `set_file_tags(path, tags) -> bool`.


Revision note (2026-10-17): first version, written after reading `testlog_utils.py`, `testlog_archive.py`, `workspace_models.py` and the sidebar, toolbar and context-menu code in `main.py` at commit `451b055`.

Revision note (2026-10-17): implementation complete for Milestones 1-4; living sections updated as each milestone landed.
