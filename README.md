# TestLog Editor

A local-first desktop Markdown editor for `.testlog` files, built with PySide6.

## Highlights

- Workspace-first flow with a searchable file tree, pinned files, and last-workspace restore
- Text tools for exploratory testing like; generate test data, lorem ipsum, count chars, convert to Base64 etc.
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
- Packaging is driven by `testlog.spec`
- Windows builds generate a real `.ico` from the app SVG so the packaged executable and taskbar use the TestLog Editor icon
- PyInstaller builds are platform-specific, so build on the target OS

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
