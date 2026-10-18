# TestLog Editor

A local-first desktop Markdown editor for `.testlog` files, built with PySide6.

## Highlights

- Workspace-first flow with a searchable file tree, pinned files, and last-workspace restore
- Keyboard navigation in the sidebar: Ctrl+L focuses the file search (↓ moves into the list, Enter opens the first match), Ctrl+0 or Alt+← focuses the file tree (arrows move and show the highlighted note after a short pause, Enter opens it in the editor or toggles a folder, Esc or Alt+→ returns to the editor), F2 renames, Delete moves to Trash, and the Menu key or Shift+F10 opens the item's context menu; Ctrl+N creates a note and Ctrl+Shift+N a folder in the selected folder
- Multi-select in the file tree (Shift+click or Shift+arrows for a range, Ctrl+click or Ctrl+Space to add or remove one, Ctrl+A for all): set status, add or remove tags, pin, move, archive or delete the whole selection from the right-click menu or the Delete key
- Status (todo/doing/done) and tags per note; type `#tag` in the sidebar search to show only notes with that tag, across folders
- Deleted notes and folders go to a Trash folder (Papperskorg in Swedish) at the bottom of the sidebar, where they can be restored; anything left untouched in Trash for 30 days is removed when the workspace is opened
- Text tools for exploratory testing like; generate test data, lorem ipsum, count chars, pretty-print JSON/HTML, convert to Base64 etc.
- Split editor and live preview with clickable task list checkboxes
- Robust autosave for saved files, plus save/discard prompts when leaving untitled changes behind
- Paste screenshots and images directly into a note as embedded markdown assets
- PDF export that carries embedded images along
- Light/dark preview themes, editor font sizing, and Swedish/English UI support

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The text tool's locale-aware test data generator now uses `Faker` for names, addresses, emails, and company names.

## Run

```bash
source .venv/bin/activate
python main.py
```

## Tests

Run the focused unit tests with:

```bash
source .venv/bin/activate
python -m pytest
```

Enforce the test suite before each commit in this clone with:

```bash
git config core.hooksPath .githooks
```

The committed pre-commit hook uses the project virtualenv and runs `python -m pytest`.

## Packaging

Build on the same operating system you want to distribute for:

```bash
./build.sh
```

`build.sh` will automatically use either `.venv/bin/activate` on Linux/macOS or `.venv/Scripts/activate` on Windows shells such as Git Bash.

If you prefer to activate the virtual environment yourself first, you can still do that:

```bash
source .venv/bin/activate
./build.sh
```

On Windows with a Unix-like shell:

```bash
source .venv/Scripts/activate
./build.sh
```

Notes:
- Packaged output is written to `dist/TestLog Editor/`
- The version is `1.0.<commit count>` and is stamped into the build from git (`git` must be on the PATH). Check it under Help → About or in the window title. `+dirty` means the build had uncommitted changes to tracked files
- Packaging is driven by `testlog.spec`
- Windows builds generate a real `.ico` from the app SVG so the packaged executable and taskbar use the TestLog Editor icon
- PyInstaller builds are platform-specific, so build on the target OS

## Troubleshooting

Errors, including failed saves, are written to `testlog-editor.log`:

- Linux: `~/.local/share/TestLog Editor/TestLog Editor/`
- Windows: `%APPDATA%\TestLog Editor\TestLog Editor\`

If a save fails, the text stays in the editor and the window will not close until a save succeeds. A hidden `.<name>.testlog.<random>.tmp` file left next to a note after a crash is safe to delete.

## Linux Launcher

Install a desktop launcher on Linux:

```bash
./install-desktop-entry.sh source
```

That creates:

```text
~/.local/share/applications/testlog-editor.desktop
```

If you want the launcher to use the packaged Linux build instead:

```bash
./install-desktop-entry.sh package
```
