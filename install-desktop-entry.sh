#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$ROOT_DIR/testlog-editor.desktop"
TARGET_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
TARGET_FILE="$TARGET_DIR/testlog-editor.desktop"

MODE="${1:-source}"

mkdir -p "$TARGET_DIR"

case "$MODE" in
  source)
    EXEC_CMD="$ROOT_DIR/.venv/bin/python $ROOT_DIR/main.py"
    ;;
  package)
    EXEC_CMD="$ROOT_DIR/dist/TestLog Editor/TestLog Editor"
    if [[ ! -x "$ROOT_DIR/dist/TestLog Editor/TestLog Editor" ]]; then
      echo "Packaged app not found. Build it first with ./build.sh"
      exit 1
    fi
    ;;
  *)
    echo "Usage: ./install-desktop-entry.sh [source|package]"
    exit 1
    ;;
esac

sed \
  -e "s|__EXEC__|$EXEC_CMD|" \
  -e "s|__ROOT_DIR__|$ROOT_DIR|" \
  "$DESKTOP_FILE" > "$TARGET_FILE"

chmod +x "$TARGET_FILE"

echo "Installed desktop entry: $TARGET_FILE"
echo "Mode: $MODE"
