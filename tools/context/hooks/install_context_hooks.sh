#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

mkdir -p tools/context/hooks

if git rev-parse --git-dir >/dev/null 2>&1; then
  HOOK_DIR="$(git rev-parse --git-path hooks)"
  mkdir -p "$HOOK_DIR"
  TARGET="$HOOK_DIR/pre-commit"
  if [[ -f "$TARGET" ]] && ! grep -q "pre_commit_context_check.sh" "$TARGET"; then
    cp "$TARGET" "$TARGET.backup.context-governor-$(date -u +%Y%m%d%H%M%S)"
  fi
  cat > "$TARGET" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
bash tools/context/hooks/pre_commit_context_check.sh
HOOK
  chmod +x "$TARGET"
  echo "installed git pre-commit hook: $TARGET"
else
  chmod +x tools/context/check_before_change.sh
  echo "not a git repository; use tools/context/check_before_change.sh before changes"
fi
