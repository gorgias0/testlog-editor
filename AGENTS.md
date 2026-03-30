# AGENTS.md

## Project Overview

TestLog Editor is a small desktop Markdown editor built with PySide6. The main application lives in `main.py` and provides:

- a workspace tree for `.testlog` files
- a split editor/preview UI
- autosave while a file is open
- Markdown conveniences such as smart list continuation and code block helpers
- image paste support for embedded markdown images

## Repository Layout

- `main.py`: application entrypoint and almost all UI/editor behavior
- `styles.py`: HTML/CSS used by the preview pane
- `requirements.txt`: Python dependencies for running and packaging the app
- `build.sh`: PyInstaller build script for local packaging
- `testlog.spec`: PyInstaller build definition
- `testlog-editor.desktop`: desktop launcher template for Linux
- `install-desktop-entry.sh`: installs a per-user Linux desktop entry
- `README.md`: basic setup and run instructions

## Run The App

Use a virtual environment and launch the app directly:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The project currently depends on `PySide6`, `markdown-it-py`, `mdit-py-plugins`, and `pyinstaller`.

## Packaging

Create distributable builds with:

```bash
source .venv/bin/activate
./build.sh
```

PyInstaller outputs the packaged app in `dist/TestLog Editor/`. Builds are platform-specific.
Prefer updating `testlog.spec` when packaging needs to change.

## Linux Launcher

Install a desktop launcher with:

```bash
./install-desktop-entry.sh source
```

Use `package` instead of `source` to target the packaged Linux app.

## Working Conventions

- Keep the app lightweight and local-first. There is no backend or service layer in this repo.
- Preserve the current single-window desktop flow unless a task explicitly asks for a larger refactor.
- Prefer small, targeted edits. `main.py` is currently monolithic, so avoid opportunistic rewrites.
- When changing editor shortcuts or typing behavior, verify that normal text entry still works in the `Editor` subclass.
- When changing preview rendering, keep `styles.py` and the markdown generation logic aligned.
- When changing workspace handling or window layout, remember that `QSettings` persists the last workspace, geometry, and splitter state.

## Manual Verification

There is no automated test suite in this repository right now, so rely on focused manual checks:

1. Launch `python main.py`.
2. Open a workspace containing `.testlog` files.
3. Edit a file and confirm autosave still works.
4. Verify Markdown preview updates correctly.
5. Smoke test editor helpers you touched, such as Enter, Tab, Shift+Tab, bold/italic, and pasted images.

## File And State Side Effects

- App state is written through `QSettings`.
- Temporary session data is created under the operating system temp directory with a `testlog_*` prefix.
- Sample documents may live inside the chosen workspace and should not be rewritten unless the task calls for it.

## Notes For Future Agents

- Check the current git diff before editing; this repo may have local work in progress.
- Avoid deleting user files in the chosen workspace during testing.
- If you add dependencies or commands, update both this file and `README.md`.
- Windows packaging should use the committed `testlog.spec` one-directory build, and packaged output remains ignored via `build/` and `dist/`.
