#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$ROOT_DIR/testlog-editor.desktop"
ICON_FILE="$ROOT_DIR/testlog-editor.svg"

REAL_HOME="$(getent passwd "$(id -un)" | cut -d: -f6)"
REAL_HOME="${REAL_HOME:-$HOME}"

if [[ -n "${XDG_DATA_HOME:-}" && "$XDG_DATA_HOME" != "$REAL_HOME"/snap/* ]]; then
  TARGET_DIR="$XDG_DATA_HOME/applications"
else
  TARGET_DIR="$REAL_HOME/.local/share/applications"
fi

TARGET_FILE="$TARGET_DIR/testlog-editor.desktop"

MODE="${1:-source}"

mkdir -p "$TARGET_DIR"

case "$MODE" in
  source)
    EXEC_CMD="\"$ROOT_DIR/.venv/bin/python\" \"$ROOT_DIR/main.py\""
    ;;
  package)
    EXEC_CMD="\"$ROOT_DIR/dist/TestLog Editor/TestLog Editor\""
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
  -e "s|__ICON__|$ICON_FILE|" \
  -e "s|__ROOT_DIR__|$ROOT_DIR|" \
  "$DESKTOP_FILE" > "$TARGET_FILE"

chmod +x "$TARGET_FILE"

echo "Installed desktop entry: $TARGET_FILE"
echo "Mode: $MODE"
