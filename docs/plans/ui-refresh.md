# Refresh the look of the main window ("clean native", light and dark)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `tests/PLANS.md` (the ExecPlan rules for this repository; the file lives in the `tests/` folder even though `AGENTS.md` refers to it simply as `PLANS.md`).


## Purpose / Big Picture

TestLog Editor works, but its main window looks dated and makes it hard to see at a glance what note is open and what state it is in. The formatting toolbar is a row of large grey text buttons (B, I, U, H1, H2, H3, H4, UL, 1., ─) that takes a lot of room for actions most people do with shortcuts; the note's status and tags sit as a drop-down and a text field in the middle of that toolbar; the sidebar has the same background as the editor, dense rows, glossy clip-art icons and a barely visible selected row; the editor text runs right up to the left border; and the status bar reads "Editor Count: 2316 | No ws: 1885 | Selected: 0 | Selected no ws: 0".

After this change the window follows the "clean native" direction the user chose from a set of mockups (the mockup canvas is at https://claude.ai/artifact/57Wrx1bXZnsArYqcakqk1d, frames "A · Clean native" and "A · Clean native (dark)"; this plan describes everything needed, so the canvas is a visual reference only). It keeps the menu bar, the single window and the sidebar/editor/preview layout, and it keeps working in both the light and the dark theme (View menu, Light/Dark). Concretely, a user will see: a compact toolbar of small icon buttons with tooltips naming the shortcut, one "Heading" drop-down instead of four H buttons, Text Tool and Diff on the right next to an Edit / Split / Preview switch; a sidebar with its own subtle background, a blue "+ New note" button, flat line icons, taller rows and a clearly highlighted selected row; a header bar above the editor showing the folder, the note's name, its status as a coloured pill and its tags as chips; more space around the editor text; and a short status bar such as "Saved" on the left and "1,284 characters · 1,051 without spaces" on the right.

How to see it working: run `python main.py`, open a workspace, open a note. The window looks like the mockup in the current theme; switch View, Dark and it looks like the dark mockup. Click the status pill and choose Done: the pill turns grey, the note's dot in the sidebar turns grey, and the note's header line `status: done` is written as before. Nothing about how notes are stored changes.


## Progress

- [x] (2026-10-30) Plan written; mockups agreed (direction A, light and dark).
- [x] (2026-10-30) Milestone 1: new palette keys and values (light and dark); sidebar on its own background with rounded controls, an accent "+ New note" button and an icon-only new-folder button; 28-pixel tree rows with a full-row highlight and no dotted focus frame; flat `{stroke}` line icons (`themed_icon`) re-rendered on theme change; status dots themed in the tree and the recent-files switcher; editor without a box border and with left/top padding; status bar "N characters · N without spaces" plus the selected counts while text is selected (`format_editor_counts`, 3 tests). 227 passed. Screenshots in both themes and a scripted check of live theme switching and the counts (see `Artifacts and Notes`).
- [ ] Milestone 1 commit (waiting for the user's approval) and Windows build for the user.
- [ ] Milestone 2: compact toolbar (icon buttons, Heading drop-down, checklist button, Edit/Split/Preview switch).
- [ ] Milestone 3: note header bar (folder, name, status pill, tag chips).
- [ ] Milestone 4 (optional, prototyping): setting to hide the front-matter lines in the editor.
- [ ] Milestone 5: documentation (`README.md`, `AGENTS.md`), full test run, Windows build handed to the user, retrospective.


## Surprises & Discoveries

- Observation: the style sheet rule `QTreeView::branch:selected` did not stop Qt from painting the indent area left of a selected row in the palette's default highlight blue; setting the tree's `QPalette` Highlight and HighlightedText roles to `row_selected_bg`/`row_selected_text` (in `_apply_theme`) makes the indent part of the same highlight.
  Evidence: offscreen screenshot crops before and after; before, a solid blue block left of the selected row in both themes.
- Observation: Qt style sheet padding on the editor (`QTextEdit`) also moves its scrollbar, so right padding left a strip between the scrollbar and the preview; the editor uses top and left padding only.
  Evidence: screenshot with `padding: 14px 20px 0 24px` showed the gap; `padding: 10px 0 0 20px` does not.
- Observation: the status bar counts never listened to `selectionChanged`, so clearing a selection without moving the cursor left stale selected numbers; harmless before, visible now that the selected part only appears while text is selected. `selectionChanged` now also starts the counts timer.
  Evidence: scripted check printed "… · 12 selected (10 without spaces)" after `clearSelection()` before the fix and the totals only after it.
- Observation: the "+ Folder" text no longer fit next to "+ New note" and the sort button at the default sidebar width; the new-folder button is icon-only (its tooltip and accessible name keep the text) and the default sidebar width is 260 pixels (a saved splitter state still wins).


## Decision Log

- Decision: direction A "clean native", in both light and dark theme; direction B (no menu bar, command palette, proportional editor font) is out of scope.
  Rationale: chosen by the user from the mockups ("A with darkmode would be ok").
  Date/Author: 2026-10-30 / Daniel Lindkvist.
- Decision: keep the existing `self.status_combo` (a `QComboBox`) and `self.tags_edit` (a `TagLineEdit`) objects and move them into the new header bar, restyled, rather than replacing them with new widget types.
  Rationale: `main.py` refers to `status_combo` 28 times and to `tags_edit` 23 times (status sync from the editor, bulk actions, retranslation, focus chain, file open and save). Keeping the objects keeps every one of those paths unchanged, and both widgets already work with the keyboard.
  Date/Author: 2026-10-30 / Claude.
- Decision: the editor keeps its monospace font; the user-interface font stays the operating system's default (Segoe UI on Windows); no font files are bundled.
  Rationale: direction A is "native, but cleaner"; bundling fonts would grow the packaged build and is not needed for the look.
  Date/Author: 2026-10-30 / Claude.
- Decision: hiding the front-matter lines in the editor (milestone 4) is a separate, opt-in setting, off by default, and may be dropped.
  Rationale: hidden text blocks change how the cursor, selection, undo and copy behave in the editor; the rest of the refresh must not depend on it.
  Date/Author: 2026-10-30 / Claude.
- Decision: the status bar keeps both selected numbers ("12 selected (10 without spaces)") rather than only the count with spaces.
  Rationale: character counts with and without spaces are used when testing field limits; dropping one would remove information the old status bar gave.
  Date/Author: 2026-10-30 / Claude.
- Decision: no separate preview background colour; the preview uses `panel_bg` like the editor (pure white in the light theme).
  Rationale: `_preview_theme_assets` is also used for PDF export with the light theme, and a tinted preview background would tint exported PDFs.
  Date/Author: 2026-10-30 / Claude.
- Decision: each milestone is committed separately, only after the user approves the commit; nothing is pushed without approval.
  Rationale: the user's standing rules (no commit or push without being told each time).
  Date/Author: 2026-10-30 / Daniel Lindkvist.


## Outcomes & Retrospective

(Not started.)


## Context and Orientation

TestLog Editor is a desktop Markdown note editor written in Python with PySide6 (the official Python bindings for the Qt user-interface toolkit). A note is a `.testlog` file: a zip archive holding `note.md` plus pasted images. Its first lines are a "front-matter" block, lines between two `---` lines, holding `status:` (one of `todo`, `doing`, `done`) and optionally `tags:` (lowercase words separated by commas). `testlog_utils.py` reads and writes these lines (`get_testlog_status`, `set_testlog_status`, `get_testlog_tags`, `set_testlog_tags`); `TESTLOG_STATUS_OPTIONS`, `TESTLOG_STATUS_LABELS` and `TESTLOG_STATUS_SORT_ORDER` are defined at the top of that file.

Almost all user-interface code is in `main.py`, in the class `MainWindow`. The parts this plan touches:

The theme. `MainWindow._theme_palette(theme_mode=None)` returns a dictionary of colour names to hex strings, one dictionary for `"dark"` and one for light (keys include `window_bg`, `chrome_bg`, `chrome_hover`, `panel_bg`, `panel_border`, `text`, `muted_text`, `link`, `selection_bg`, `selection_text` and the scrollbar and code colours). `MainWindow._apply_theme()` builds one Qt style sheet (Qt's CSS-like styling language, applied with `setStyleSheet`) from that palette for the whole window, then restyles the editor (`_apply_editor_stylesheet`), the preview, the toolbar (`_toolbar_stylesheet`), the old view toggle button (`_preview_toggle_button_stylesheet`), the syntax highlighter (`MarkdownHighlighter.set_theme_mode`) and some dialogs. `MainWindow._set_theme_mode(mode)` stores the choice in `QSettings` (Qt's per-user settings store) and calls `_apply_theme`. The preview pane is a web view whose HTML and CSS come from `styles.py` (`PREVIEW_STYLE`) plus `MainWindow._preview_theme_assets`; `AGENTS.md` asks that `styles.py` and the preview HTML generation stay aligned when either changes.

The toolbar. `MainWindow` builds `self.toolbar` (a `QToolBar`) in a block that starts with `self.toolbar = QToolBar("Formatting")`. It adds `QAction`s named `toolbar_bold_action`, `toolbar_italic_action`, `toolbar_underline_action`, `toolbar_h1_action` to `toolbar_h4_action`, `toolbar_bullet_action`, `toolbar_numbered_action`, `toolbar_hr_action`, `toolbar_text_tool_action` and `toolbar_diff_action`, then `self.status_combo`, `self.tags_edit`, a stretching spacer, and `self.toggle_btn` (a `QToolButton` that flips between editor and preview). Their visible texts and tooltips are set in `MainWindow._retranslate_ui` (texts like "B", "H1", "UL"; tooltips through `self._tr`, the translation function backed by `translations.py`, which holds Swedish strings keyed by the English text). The heading actions call `self._insert_line_prefix("# ")` and so on; the Format menu has its own heading actions with the shortcuts Ctrl+1 to Ctrl+4.

View modes. `ViewMode` has `SINGLE` (only the editor or only the preview is visible; `toggle_editor_preview`, bound to Ctrl+E and F11, flips between them) and `SPLIT` (both side by side; `set_split_mode(enabled)`, also reachable from the View menu's `action_split_view`). The editor and preview live in `self.inner_splitter`; the sidebar and `inner_splitter` live in `self.outer_splitter`. `closeEvent` saves the window geometry, both splitter states and the view mode in `QSettings`, and they are restored at start-up; this must keep working.

The sidebar. Built in `MainWindow._setup_ui`: a search field (`self.sidebar_search`), a row with `self.btn_new_file` ("+ New File"), `self.btn_new_folder` ("+ Folder") and `self.btn_sort` (the sort menu), then `self.tree`, a `QTreeView` showing a `WorkspaceFileSystemModel` through a `WorkspaceSortProxyModel` (both in `workspace_models.py`). Rows of notes are drawn by `WorkspaceTreeItemDelegate` in `main.py`, which paints the row background, the name, the tags in grey and a coloured status dot (`STATUS_COLORS`, currently the same in both themes). Icons for folders, notes, pinned items and Trash are SVG strings in `icons.py`, turned into `QIcon`s by `icon_from_svg(svg_text, size)`.

The status bar. `self.editor_count_label` is a `QLabel` in the status bar, filled by `MainWindow._update_editor_counts` with the translated string "Editor Count: {with_ws} | No ws: {without_ws} | Selected: {sel_with_ws} | Selected no ws: {sel_without_ws}". Other code shows temporary messages ("Autosaved", "Workspace opened: …") with `self.statusBar().showMessage`.

Scripted checks. `AGENTS.md` describes the usual way to check user-interface behaviour without a screen: a throwaway Python script that sets `QT_QPA_PLATFORM=offscreen` and points `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `TMPDIR` at a scratch folder, creates `QApplication` and `MainWindow`, drives it, and saves `window.grab()` to a PNG. This plan uses such screenshots, in both themes, as the visual evidence for every milestone.


## Plan of Work

Milestone 1, theme palette and polish. Nothing moves; only colours, spacing and icons change. In `MainWindow._theme_palette`, add keys and adjust values so both dictionaries carry what the new look needs: `sidebar_bg` (light `#f6f7f9`, dark `#1c2128`), `chrome_bg` (light `#f6f7f9`, dark `#1c2128`), `window_bg` and `panel_bg` for the editor (light `#ffffff`, dark `#22272e`), `preview_bg` (light `#fbfcfd`, dark `#1f242b`), `panel_border` (light `#e3e6ea`, dark `#373e47`), `control_bg` and `control_border` for small buttons (light `#ffffff`/`#d8dce1`, dark `#2d333b`/`#444c56`), `accent` (`#2563eb` in both) with `accent_text` `#ffffff`, `row_selected_bg` and `row_selected_text` (light `#dbe7fd`/`#0b3a8f`, dark `#1f3a63`/`#ffffff`), `chip_bg` and `chip_text` (light `#eef1f4`/`#3d444d`, dark `#2d333b`/`#cdd9e5`), and `status_doing`, `status_todo`, `status_done` (light `#1a7f37`, `#bf8700`, `#8c959f`; dark `#57ab5a`, `#c69026`, `#768390`). Keep every existing key so other code keeps working. In `_apply_theme`, style the sidebar container with `sidebar_bg` and a right border (give the sidebar `QWidget` an object name such as `sidebar` and target `QWidget#sidebar` in the style sheet), give `QTreeView::item` a height of about 28 pixels and rounded selected rows using `row_selected_bg`/`row_selected_text`, give `QLineEdit` and `QPushButton` rounded corners (6 pixels) using `control_bg`/`control_border`, and give `btn_new_file` an object name and the `accent` background. Rename the button text to "+ New note" (English key "+ New note", Swedish "+ Ny anteckning"; keep its tooltip). Make `WorkspaceTreeItemDelegate` take its status colours from the palette (add a `set_status_colors(dict)` method called from `_apply_theme`; keep `STATUS_COLORS` as the light defaults), and make `RecentFileItemDelegate` (just above it in `main.py`, which draws the rows of the recent-files switcher and also reads `WorkspaceTreeItemDelegate.STATUS_COLORS`) use the same themed colours. In `icons.py`, add flat line icons for folder, note, pinned folder, pinned note and Trash as SVG strings containing the placeholder `{stroke}`, and a helper `themed_icon(svg_template, color, size=20)` that substitutes the colour and calls `icon_from_svg`; in `MainWindow`, build the tree icons from these with `muted_text` as the colour, and rebuild them in `_apply_theme` so they follow the theme. Keep the old SVG constants (the app icon and `.ico` export use `APP_ICON_SVG`, which does not change). Give the editor text room: in `_apply_editor_stylesheet` set a padding of about 16 pixels top and 24 pixels left/right on the `QTextEdit` (if Qt's style sheet padding does not apply to the text area, use `self.editor.setViewportMargins` or `self.editor.document().setDocumentMargin` instead and record which one worked in `Surprises & Discoveries`). Shorten the status bar: change `_update_editor_counts` to show "{with_ws} characters · {without_ws} without spaces" and, only while text is selected, append " · {sel_with_ws} selected"; format numbers with a thousands separator using Python's `f"{n:,}"` for English and a non-breaking space for Swedish (`translations.py` gets the new keys "{with_ws} characters · {without_ws} without spaces" and " · {sel_with_ws} selected"). Keep the old translation key in `translations.py` until nothing uses it, then remove it in the same milestone.

At the end of milestone 1 the window has the new colours, sidebar, tree rows, icons, editor margins and status bar in both themes; the toolbar and the status/tags controls are where they were.

Milestone 2, compact toolbar. Add line icons for bold, italic, underline, bullet list, numbered list, checklist, horizontal rule, Text Tool and Diff to `icons.py` in the same `{stroke}` template form, rendered with the palette's `text` colour (rebuilt in `_apply_theme`). In the toolbar block of `MainWindow`, give the existing actions these icons and set the toolbar to `Qt.ToolButtonStyle.ToolButtonIconOnly` for the formatting part; bold, italic and underline may keep the letters B, I, U drawn as icons. Replace the four heading buttons with one `QToolButton` (`self.toolbar_heading_button`) whose popup menu holds the existing `toolbar_h1_action` to `toolbar_h4_action` with the texts "Heading 1" to "Heading 4"; the button text reads "Heading" (translated). Add `self.toolbar_checklist_action`, which calls `self._insert_line_prefix("- [ ] ")` (the same helper the list buttons use) with the tooltip "Checklist". Move `toolbar_text_tool_action` and `toolbar_diff_action` after the stretching spacer so they sit on the right, shown as icon plus text. Replace `self.toggle_btn` with a three-button view switch: three checkable `QToolButton`s ("Edit", "Split", "Preview") in a `QButtonGroup` with exclusive checking, held in a small `QWidget` styled as a segmented control (a rounded background with the checked button raised, colours from the palette). Add `MainWindow.set_view(name)` taking `"edit"`, `"split"` or `"preview"`: `"split"` calls `set_split_mode(True)`; `"edit"` and `"preview"` call `set_split_mode(False)` and then make the editor or the preview the visible one, using the same steps `toggle_editor_preview` uses today. Add `MainWindow._sync_view_switch()`, which checks the button matching the current state, and call it at the end of `toggle_editor_preview`, `set_split_mode` and start-up, so Ctrl+E, F11 and the View menu keep the switch right. Remove `toggle_btn`, `_update_toggle_icon` and `_preview_toggle_button_stylesheet` only once nothing refers to them (search with `rg -n "toggle_btn|_update_toggle_icon|_preview_toggle_button_stylesheet" main.py`). Update `_retranslate_ui` for the new texts and the Swedish strings in `translations.py`. Update the keyboard focus chain (the list that includes `self.status_combo` near the end of `_setup_ui`) so the new buttons are reachable with Tab as before.

At the end of milestone 2 the toolbar matches the mockup; every formatting action, Text Tool, Diff and every way of switching views works as before.

Milestone 3, note header bar. Create a header `QWidget` (`self.note_header`, object name `noteHeader`) and place it above the editor and preview: build a new container `QWidget` with a `QVBoxLayout` holding `self.note_header` and then `self.inner_splitter`, and add that container to `outer_splitter` where `inner_splitter` is added today (the outer splitter still has two widgets, so its saved state stays valid). The header is a horizontal layout: on the left a column with a small muted label for the folder (`self.note_header_folder`, the note's folder relative to the workspace, empty at the workspace root) and a larger label for the note's name (`self.note_header_title`, the file name without `.testlog`, or "Untitled" when no file is open); a stretch; then `self.status_combo` and the tags area. Move `self.status_combo` and `self.tags_edit` out of the toolbar into the header (remove the `self.toolbar.addWidget(...)` lines for them; keep their construction, signals and every other use unchanged). Style `status_combo` as a pill: rounded, 26 pixels high, its background, border and text taken from the status colours (a light tint of the colour for the background in the light theme, a dark tint in the dark theme), set in a new `MainWindow._style_status_pill(status)` called from `_set_status_combo` and `_apply_theme`. For tags, add `self.tags_chips`, a `QWidget` with a horizontal layout of small rounded `QLabel` chips (one per tag, `chip_bg`/`chip_text`) followed by a "+ tag" `QToolButton`, and put it and `self.tags_edit` in a `QStackedWidget` (`self.tags_stack`): the chips page shows normally; clicking a chip or "+ tag" switches to the `tags_edit` page and focuses it; when `tags_edit` emits `editingFinished` (already connected to `_on_tags_edit_finished`, which saves the tags) or loses focus, switch back and rebuild the chips. Add `MainWindow._refresh_note_header()` that updates the folder, title and chips; call it wherever the open file or its tags change: at the end of `open_testlog`, after rename and move of the open file, after `_sync_tags_from_editor`, after `_on_tags_edit_finished`, after `new_file`, and from `_set_workspace`. Keep the tooltip "Status" on the combo and add the tooltip "Tags" on the chips.

At the end of milestone 3 the header bar shows the open note's folder, name, status pill and tags; changing the status from the pill or by editing the `status:` line, or the tags from the chips or by editing the `tags:` line, updates the header, the sidebar dot and the file exactly as the old controls did.

Milestone 4 (optional, prototyping), hide the front-matter lines. Add a View menu entry "Hide note header lines" (checkable, stored in `QSettings` as `hide_front_matter`, default off). When on, mark the editor's front-matter blocks invisible (`QTextBlock.setVisible(False)` for each block of the `---` … `---` header, then `self.editor.document().markContentsDirty(start, length)`), and keep the cursor out of them: in the `Editor` subclass, after any cursor move, if the cursor lands inside the header, move it to the first visible position. Re-apply after `setPlainText` and whenever the header lines change. Saving must still write the header unchanged (the text is still in the document; only its display is hidden). Prove it with a scripted check: open a note, turn the setting on, press Ctrl+Home, type a letter, save, and read the file back; the header must be intact and the letter must be after it. If cursor, selection, undo or copy behave badly in a way that cannot be fixed simply, stop, record why in `Surprises & Discoveries`, and drop this milestone (the header bar from milestone 3 works without it).

Milestone 5, documentation and hand-over. Update `README.md` (the Highlights list: header bar, view switch, refreshed look in light and dark) and `AGENTS.md` (a short "Look and theme" section: the palette keys live in `MainWindow._theme_palette`, icons are `{stroke}` templates in `icons.py` re-rendered by `_apply_theme`, the header bar holds `status_combo` and `tags_edit`). Run the full tests, take final screenshots, build the Windows package the way described in `Concrete Steps`, and write the retrospective.


## Concrete Steps

All commands run from the repository root, `~/workspace/private/testlog-editor` in WSL, with the virtual environment's Python.

Before starting each milestone, check for local work in progress, as `AGENTS.md` asks:

    git status --short

Run the tests after each milestone:

    .venv/bin/python -m pytest -q

Expect "224 passed" at the start of this plan (more after new tests are added) and no failures.

Take screenshots of both themes after each milestone with a scratch script outside the repository (for example in a scratch folder), along these lines, run once with `light` and once with `dark` as the last argument:

    QT_QPA_PLATFORM=offscreen XDG_CONFIG_HOME=$SCRATCH/xdg/config XDG_DATA_HOME=$SCRATCH/xdg/data TMPDIR=$SCRATCH/tmp \
      .venv/bin/python $SCRATCH/shot.py $SCRATCH/ws $SCRATCH/light.png light

where `shot.py` imports `main`, creates `QApplication`, sets `QSettings("TestLog Editor", "TestLog Editor")` values `last_workspace` (a scratch workspace with a few folders and notes of each status), `theme_mode` and `language`, creates `MainWindow`, shows it at 1400×800, waits about 2.5 seconds with `QTimer.singleShot` for the preview to load, and saves `window.grab()` to the given path. Compare the result with the mockup frames.

To build and install for Windows (the user tests there), use the Windows checkout at `C:\Users\danie\workspace\private\testlog-editor` (from WSL: `/mnt/c/Users/danie/workspace/private/testlog-editor`) and Windows' own git and Python, because PyInstaller only builds for the system it runs on. Bring the checkout to the same commit (`git.exe pull --ff-only` after the user has approved pushing, or apply the uncommitted diff with `git.exe apply`), check that `TestLog Editor.exe` is not running (`tasklist.exe | grep -i testlog`), then:

    cd /mnt/c/Users/danie/workspace/private/testlog-editor
    ./.venv/Scripts/python.exe -m PyInstaller --noconfirm testlog.spec
    cp -r "./dist/TestLog Editor/_internal" "./dist/TestLog Editor/TestLog Editor.exe" /mnt/c/Users/danie/.bin/

Expect "Build complete!" at the end of the PyInstaller output (about two minutes).


## Validation and Acceptance

Milestone 1 is accepted when, in both themes, the screenshots show the sidebar on its own background with taller rows, flat line icons and a clearly highlighted selected row, a blue "+ New note" button, space around the editor text, and the short status bar; and when switching View, Light/Dark while the app runs repaints the icons and status dots in the new theme's colours. Selecting text adds " · N selected" to the status bar and removing the selection takes it away again.

Milestone 2 is accepted when every toolbar button still does what it did (bold, italic, underline, each heading level from the Heading drop-down, bullet, numbered, horizontal rule, Text Tool, Diff), the new checklist button inserts `- [ ] ` at the start of the line, and the view switch, Ctrl+E, F11 and View, Split View always agree: clicking Preview shows only the preview, Ctrl+E then shows only the editor and the switch shows Edit, choosing Split shows both. Closing and restarting the app keeps the view mode and splitter sizes.

Milestone 3 is accepted when opening a note shows its folder and name in the header; choosing Done from the pill turns the pill and the sidebar dot grey and the note's file contains `status: done`; typing `status: doing` in the editor turns the pill green; clicking "+ tag", typing `smoke` and pressing Enter shows a `smoke` chip and writes `tags: …, smoke` to the file; renaming the open note updates the header title.

Milestone 4, if kept, is accepted by the scripted check described in its paragraph, plus Ctrl+A then Ctrl+C copying the whole note including the header.

For every milestone, the full test suite passes, and a manual check on Windows (the user's real display) confirms the look; the user's approval of each commit is the final acceptance.


## Idempotence and Recovery

Every step edits code only; no notes or settings are rewritten except through the app's normal saving. Each milestone is one commit, so a milestone that turns out wrong can be undone with `git revert <commit>`. Screenshot scripts and scratch workspaces live outside the repository and can be deleted and recreated at any time. The Windows install copies over the previous build in `C:\Users\danie\.bin`; to go back, rebuild from the previous commit the same way.


## Artifacts and Notes

Milestone 1 scripted check (offscreen, scratch workspace, light theme then `_set_theme_mode("dark")`):

    light: dot doing #1a7f37 | icon pixel ['#565f6a', '#56606a', '#575f69']
    dark:  dot doing #57ab5a | icon pixel ['#acbac6', '#acbac7', '#adbac7']
    status bar: 2,316 characters · 1,885 without spaces
    with selection: 2,316 characters · 1,885 without spaces · 12 selected (10 without spaces)
    cleared: 2,316 characters · 1,885 without spaces
    swedish: 2 316 tecken · 1 885 utan blanksteg | button: + Ny anteckning | folder tooltip: Ny mapp i vald mapp (Ctrl+Shift+N)

The agreed mockups (static HTML, not code to copy) are in the canvas https://claude.ai/artifact/57Wrx1bXZnsArYqcakqk1d: "Today" (a screenshot of the app before this plan), "A · Clean native" and "A · Clean native (dark)". The colours in `Plan of Work` are taken from those frames.

Before this plan, a 1400×800 offscreen screenshot of the light theme shows the toolbar as eleven text buttons plus a 120-pixel status drop-down and a 180-pixel tags field, the sidebar on the window colour, and the status bar text "Editor Count: 2316 | No ws: 1885 | Selected: 0 | Selected no ws: 0".


## Interfaces and Dependencies

No new dependencies. Everything uses PySide6 classes the app already imports (`QToolButton`, `QButtonGroup`, `QStackedWidget`, `QLabel`, `QMenu`, `QTextBlock`).

At the end of the plan these exist:

In `icons.py`:

    def themed_icon(svg_template: str, color: str, size: int = 20) -> QIcon
        # svg_template contains the placeholder {stroke}; returns icon_from_svg(svg_template.replace("{stroke}", color), size)

plus SVG template constants for the folder, note, pinned folder, pinned note, Trash, and toolbar icons (bold, italic, underline, bullet list, numbered list, checklist, horizontal rule, Text Tool, Diff).

In `main.py`, on `MainWindow`:

    def set_view(self, name: str) -> None          # "edit", "split" or "preview"
    def _sync_view_switch(self) -> None
    def _style_status_pill(self, status: str) -> None
    def _refresh_note_header(self) -> None

and on `WorkspaceTreeItemDelegate`:

    def set_status_colors(self, colors: dict) -> None   # keys "todo", "doing", "done"

`MainWindow._theme_palette` returns, in addition to its current keys: `sidebar_bg`, `preview_bg`, `control_bg`, `control_border`, `accent`, `accent_text`, `row_selected_bg`, `row_selected_text`, `chip_bg`, `chip_text`, `status_doing`, `status_todo`, `status_done`.
