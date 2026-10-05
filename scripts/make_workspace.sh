#!/usr/bin/env bash
# Create a governed demo workspace: the tools, docs, skill and Chinese wrappers
# from this repository plus the example workspace files.
#
#   bash scripts/make_workspace.sh <new-directory>
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "usage: bash scripts/make_workspace.sh <new-directory>" >&2
  exit 2
fi
if [ -e "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ]; then
  echo "refusing to write into a non-empty directory: $TARGET" >&2
  exit 2
fi
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

mkdir -p "$TARGET/tools"
cp -R "$REPO/tools/." "$TARGET/tools/"
cp -R "$REPO/docs" "$TARGET/docs"
cp -R "$REPO/skills" "$TARGET/skills"
for wrapper in ctx k 管家 上下文管家; do
  cp "$REPO/$wrapper" "$TARGET/$wrapper"
done
cp -R "$REPO/examples/workspace/." "$TARGET/"
find "$TARGET" -name __pycache__ -type d -prune -exec rm -rf {} +

if command -v git >/dev/null 2>&1; then
  git -C "$TARGET" init -q
fi
echo "$TARGET"
