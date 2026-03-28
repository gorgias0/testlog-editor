# TestLog Editor

A small Markdown-based test log editor built with PySide6.

## Features

- Workspace browser for `.testlog` files
- Autosave (every 2 seconds when file is open)
- Undo/Redo via Edit menu
- Last opened workspace is restored at startup
- Paste images to embed in markdown

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
