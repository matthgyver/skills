#!/usr/bin/env bash
# deploy.sh: copy a MicroPython project tree to a board with mpremote.
#
# The CONTENTS of the source directory are copied to the board's root, so
#   src/main.py      -> :main.py
#   src/lib/x.py     -> :lib/x.py
#
# Usage: deploy.sh [-s SRC_DIR] [-p PORT] [-c] [-r] [-n]
#   -s SRC_DIR  project directory to deploy (default: src)
#   -p PORT     serial port, e.g. /dev/ttyACM0, /dev/cu.usbmodem1101, COM3
#               (default: mpremote auto-detects the first board)
#   -c          compile lib/**/*.py to .mpy first (needs mpy-cross from the SAME
#               MicroPython release as the firmware). boot.py and main.py stay .py
#   -r          hard-reset the board after copying
#   -n          dry run: print the mpremote command instead of running it
#   -h          show this help
#
# Unchanged files are skipped by mpremote (hash comparison), so re-deploying is quick.
# With -c: an old lib/x.py already on the board shadows the new lib/x.mpy, so remove it
# once (mpremote fs rm :lib/x.py).

set -euo pipefail

usage() {
  # print the leading comment block (everything after the shebang, up to the first non-comment line)
  awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
}

SRC="src"
PORT=""
COMPILE=0
RESET=0
DRY=0

while getopts "s:p:crnh" opt; do
  case "$opt" in
    s) SRC="$OPTARG" ;;
    p) PORT="$OPTARG" ;;
    c) COMPILE=1 ;;
    r) RESET=1 ;;
    n) DRY=1 ;;
    h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[ -d "$SRC" ] || { echo "error: source directory '$SRC' not found" >&2; exit 1; }

if [ "$DRY" -eq 0 ] && ! command -v mpremote >/dev/null 2>&1; then
  echo "error: mpremote not found (pip install mpremote)" >&2
  exit 1
fi
if [ "$COMPILE" -eq 1 ] && ! command -v mpy-cross >/dev/null 2>&1; then
  echo "error: mpy-cross not found (pip install mpy-cross)" >&2
  exit 1
fi

# Stage a clean copy so the user's source tree is never modified.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$SRC"/. "$STAGE"/
find "$STAGE" \( -name '__pycache__' -o -name '.git' -o -name '.DS_Store' \) -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -name '*.pyc' -delete

if [ "$COMPILE" -eq 1 ] && [ -d "$STAGE/lib" ]; then
  while IFS= read -r -d '' f; do
    mpy-cross -o "${f%.py}.mpy" "$f"
    rm "$f"
  done < <(find "$STAGE/lib" -name '*.py' -print0)
fi

# One mpremote invocation, commands chained with '+', to keep a single serial session.
CMD=(mpremote)
if [ -n "$PORT" ]; then
  CMD+=(connect "$PORT")
fi

shopt -s nullglob
first=1
for entry in "$STAGE"/*; do
  if [ "$first" -eq 0 ]; then
    CMD+=("+")
  fi
  CMD+=(fs cp -r "$entry" :)
  first=0
done
shopt -u nullglob

if [ "$first" -eq 1 ]; then
  echo "error: nothing to deploy in '$SRC'" >&2
  exit 1
fi

if [ "$RESET" -eq 1 ]; then
  CMD+=("+" reset)
fi

if [ "$DRY" -eq 1 ]; then
  note="STAGED = temporary copy of '$SRC'"
  [ "$COMPILE" -eq 1 ] && note="$note, lib/ compiled to .mpy"
  echo "Dry run. Would execute ($note):"
  echo "${CMD[*]//$STAGE/STAGED}"
  exit 0
fi

echo "Deploying '$SRC' ..."
"${CMD[@]}"
echo "Done. Open the REPL with: mpremote${PORT:+ connect $PORT} repl"
