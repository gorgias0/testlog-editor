#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Create it first with: python -m venv .venv"
  exit 1
fi

# source .venv/bin/activate doesn't work in bash on Windows, so we have to use the .venv\Scripts\activate script instead
source .venv\Scripts\activate

if [[ "${SKIP_PIP_INSTALL:-0}" != "1" ]]; then
  if ! python -m pip install -r requirements.txt; then
    echo
    echo "Dependency installation failed."
    echo "If this machine is offline, install dependencies first and rerun with:"
    echo "  SKIP_PIP_INSTALL=1 ./build.sh"
    exit 1
  fi
fi

if ! python -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller is not installed in the active virtual environment."
  echo "Install it with: python -m pip install pyinstaller"
  exit 1
fi

python -m PyInstaller --noconfirm testlog.spec

echo "Build complete: $ROOT_DIR/dist/TestLog Editor"
