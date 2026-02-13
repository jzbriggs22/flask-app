#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="$ROOT_DIR/.git/hooks"
HOOK_FILE="$HOOK_DIR/pre-commit"
MARKER_START="# >>> retro-css-guardrails >>>"
SNIPPET=$(cat <<'HOOK'
# >>> retro-css-guardrails >>>
./scripts/check_retro_css.sh
# <<< retro-css-guardrails <<<
HOOK
)

if [[ ! -d "$ROOT_DIR/.git" ]]; then
  echo "No .git directory found at $ROOT_DIR"
  exit 1
fi

mkdir -p "$HOOK_DIR"

if [[ -f "$HOOK_FILE" ]]; then
  if rg -q --fixed-strings "$MARKER_START" "$HOOK_FILE"; then
    echo "Pre-commit hook already contains retro guardrails."
    exit 0
  fi

  if [[ ! -x "$HOOK_FILE" ]]; then
    chmod +x "$HOOK_FILE"
  fi

  printf "\n%s\n" "$SNIPPET" >> "$HOOK_FILE"
  echo "Appended retro guardrail block to existing pre-commit hook: $HOOK_FILE"
  exit 0
fi

cat > "$HOOK_FILE" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail

# >>> retro-css-guardrails >>>
./scripts/check_retro_css.sh
# <<< retro-css-guardrails <<<
HOOK

chmod +x "$HOOK_FILE"
echo "Installed pre-commit hook: $HOOK_FILE"
