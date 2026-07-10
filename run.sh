#!/usr/bin/env bash
# 一键跑某个阶段的评测：自动使用 .venv 里的 Python，无需手动激活环境。
#
# 用法：
#   ./run.sh                # 默认跑阶段 1 (stage1_chat)
#   ./run.sh stage1_chat    # 跑指定阶段（传目录名）
#   ./run.sh 1              # 也可以只传数字，自动匹配 stage1_*

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$PROJECT_DIR/.venv/bin/python"
ARG="${1:-stage1_chat}"

# 若存在 .env 文件，自动读取里面的环境变量（比如 ANTHROPIC_API_KEY），
# 这样你不用每次手动 export。
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

# 允许只传数字：1 -> stage1_*
if [[ "$ARG" =~ ^[0-9]+$ ]]; then
  STAGE="$(ls -d "$PROJECT_DIR/exercises/stage${ARG}_"* 2>/dev/null | head -n1 | xargs -r basename)"
  STAGE="${STAGE:-stage${ARG}_unknown}"
# 也允许传子阶段号：6.1 -> stage6_1_*
elif [[ "$ARG" =~ ^[0-9]+\.[0-9]+$ ]]; then
  PREFIX="stage${ARG//./_}"
  STAGE="$(ls -d "$PROJECT_DIR/exercises/${PREFIX}_"* 2>/dev/null | head -n1 | xargs -r basename)"
  STAGE="${STAGE:-${PREFIX}_unknown}"
else
  STAGE="$ARG"
fi
TEST_DIR="$PROJECT_DIR/exercises/$STAGE"

# 1) 检查虚拟环境
if [ ! -x "$VENV_PY" ]; then
  echo "❌ 没找到虚拟环境：$VENV_PY"
  echo "   先建好环境：python3 -m venv .venv && .venv/bin/pip install anthropic"
  exit 1
fi

# 2) 检查测试目录
if [ ! -f "$TEST_DIR/test.py" ]; then
  echo "❌ 没找到 $TEST_DIR/test.py"
  echo "   可用阶段："
  ls "$PROJECT_DIR/exercises" 2>/dev/null | sed 's/^/     /'
  exit 1
fi

# 3) 检查 API key
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "⚠️  未设置 ANTHROPIC_API_KEY"
  echo "   先运行：export ANTHROPIC_API_KEY=\"你的key\""
  exit 1
fi

echo "▶ 跑评测：$STAGE"
echo "─────────────────────────────"
cd "$TEST_DIR"
exec "$VENV_PY" test.py