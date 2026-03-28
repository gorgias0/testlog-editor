# TestLog Editor

A small Markdown-based test log editor built with PySide6.

## Features

- Workspace browser for `.testlog` files
- Autosave (every 3 seconds when file is open)
- Undo/Redo via Edit menu
- Last opened workspace is restored at startup
- Paste images to embed in markdown
- Swedish and English UI support

## Install

```bash
cd /home/daniel/workspace/testlog-editor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
python main.py
```

## Package

Build on the same operating system you want to distribute for:

```bash
source .venv/bin/activate
./build.sh
```

The packaged app is written to `dist/TestLog Editor/`.

The build is driven by `testlog_editor.spec`, so packaging tweaks should go there rather than expanding the shell command in `build.sh`.

PyInstaller builds are platform-specific, so create the package on Windows for Windows, on macOS for macOS, and on Linux for Linux.

## Linux Shortcut

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
