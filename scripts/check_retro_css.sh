#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET_FILES=(
  "frontend/src/styles/GameBoard.css"
  "frontend/src/styles/App.css"
  "frontend/src/styles/index.css"
)

if ! command -v rg >/dev/null 2>&1; then
  echo "Fail: ripgrep (rg) is required to run retro CSS checks."
  exit 1
fi

for file in "${TARGET_FILES[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing expected CSS file: $file"
    exit 1
  fi
done

# Retro constraints: no gradients, no rounded corners, no shadows.
if rg -n --fixed-strings "gradient(" "${TARGET_FILES[@]}"; then
  printf "\nFail: gradient usage found in retro styles.\n"
  exit 1
fi

if rg -n --pcre2 "border-radius\s*:" "${TARGET_FILES[@]}" | rg -v --pcre2 "border-radius\s*:\s*0(?:px)?\s*;"; then
  printf "\nFail: non-zero border-radius found in retro styles.\n"
  exit 1
fi

if rg -n --pcre2 "box-shadow\s*:" "frontend/src/styles/App.css" "frontend/src/styles/index.css" | rg -v --pcre2 "box-shadow\s*:\s*none\s*;"; then
  printf "\nFail: box-shadow found in app/global retro styles.\n"
  exit 1
fi

# Board sizing constraints: default 16px tile with 14px fallback.
if ! rg -n --pcre2 -- "--tile-size\s*:\s*16px\s*;" "frontend/src/styles/GameBoard.css" >/dev/null; then
  printf "\nFail: --tile-size default must be 16px in GameBoard.css.\n"
  exit 1
fi

if ! rg -n --pcre2 "@media\s*\(max-width:\s*\d+px\)" "frontend/src/styles/GameBoard.css" >/dev/null; then
  printf "\nFail: missing mobile media query for tile fallback in GameBoard.css.\n"
  exit 1
fi

if ! rg -n --pcre2 -- "--tile-size\s*:\s*14px\s*;" "frontend/src/styles/GameBoard.css" >/dev/null; then
  printf "\nFail: mobile --tile-size fallback must be 14px in GameBoard.css.\n"
  exit 1
fi

echo "Retro CSS guardrails passed."
