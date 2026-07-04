#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN_DIR="${KEEPER_BIN_DIR:-$HOME/.local/bin}"
SKILL_DIR="${KEEPER_SKILL_DIR:-$HOME/.codex/skills/context-keeper}"

mkdir -p "$BIN_DIR" "$(dirname "$SKILL_DIR")"
ln -sfn "$ROOT/tools/keeper/keeper.sh" "$BIN_DIR/ck"
ln -sfn "$ROOT/tools/keeper/keeper.sh" "$BIN_DIR/context-keeper"
ln -sfn "$ROOT/tools/keeper/keeper.sh" "$BIN_DIR/上下文管家"
ln -sfn "$ROOT/tools/keeper/keeper.sh" "$BIN_DIR/管家"
ln -sfn "$ROOT/skills/context_keeper" "$SKILL_DIR"

echo "已安装上下文管家命令：$BIN_DIR/ck"
echo "已安装中文命令：$BIN_DIR/上下文管家, $BIN_DIR/管家"
PATH_BIN=""
for candidate in "$HOME/.npm-global/bin" "$HOME/.local/bin" "$HOME/bin"; do
  case ":$PATH:" in
    *":$candidate:"*)
      mkdir -p "$candidate"
      if [ -w "$candidate" ]; then
        PATH_BIN="$candidate"
        break
      fi
      ;;
  esac
done
if [ -n "$PATH_BIN" ] && [ "$PATH_BIN" != "$BIN_DIR" ]; then
  ln -sfn "$ROOT/tools/keeper/keeper.sh" "$PATH_BIN/ck"
  ln -sfn "$ROOT/tools/keeper/keeper.sh" "$PATH_BIN/context-keeper"
  ln -sfn "$ROOT/tools/keeper/keeper.sh" "$PATH_BIN/上下文管家"
  ln -sfn "$ROOT/tools/keeper/keeper.sh" "$PATH_BIN/管家"
  echo "已同时安装到当前 PATH：$PATH_BIN/ck"
  echo "已同时安装中文命令：$PATH_BIN/上下文管家, $PATH_BIN/管家"
fi
echo "已安装 Codex Skill：$SKILL_DIR"
case ":$PATH:" in
  *":$BIN_DIR:"*|*":$PATH_BIN:"*) ;;
  *)
    echo "提示：当前 shell 的 PATH 里还没有 $BIN_DIR"
    echo "可把下面这一行加入 ~/.zshrc："
    echo "export PATH=\"$BIN_DIR:\$PATH\""
    ;;
esac
