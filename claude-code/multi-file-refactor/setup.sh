#!/usr/bin/env bash
# setup.sh — 一键搭好「多文件协同与终端代码级重构」实验工作区
#
# 用途：把 financial-automation + CRM-Assistant 快照进本目录，建好各自的 venv，
#       跑通「重构前」绿色基线。
#
# 运行：在仓库根执行 bash claude-code/multi-file-refactor/setup.sh

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

DST="claude-code/multi-file-refactor"
# 镜像可用环境变量覆盖：MIRROR=https://mirrors.aliyun.com/pypi/simple/ bash setup.sh
MIRROR="${MIRROR:-https://pypi.tuna.tsinghua.edu.cn/simple}"

# 跨平台：python3 不存在时回退到 python（Windows Git Bash 常见）
PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"

# venv 可执行目录：Windows 是 .venv/Scripts，其它是 .venv/bin
venv_bin() { [ -d "$1/.venv/Scripts" ] && echo "Scripts" || echo "bin"; }

# 复制子目录：有 rsync 用 rsync，没有（如 Windows）用 Python shutil 回退
copy_app() {
    local app="$1"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --exclude '.venv' --exclude 'runtime' --exclude '__pycache__' \
                --exclude '*.pyc' --exclude '.tmp_tests' \
                "$app/" "$DST/$app/"
    else
        "$PYTHON" - "$app" "$DST/$app" <<'PYEOF'
import sys, shutil
src, dst = sys.argv[1], sys.argv[2]
shutil.copytree(
    src, dst,
    ignore=shutil.ignore_patterns(
        '.venv', 'runtime', '__pycache__', '*.pyc', '.tmp_tests'),
    dirs_exist_ok=True,
)
PYEOF
    fi
}

# 检查是否已存在
if [ -e "$DST/financial-automation" ] || [ -e "$DST/CRM-Assistant" ]; then
    echo "⚠ $DST 下已有快照，为避免覆盖已有改动，脚本退出。"
    echo "  如需从头重建：rm -rf $DST/financial-automation $DST/CRM-Assistant $DST/common  然后重跑。"
    exit 1
fi

echo "==> 1/4 快照 financial-automation + CRM-Assistant 到 $DST/"
mkdir -p "$DST/common"

# 正确复制两个子目录（注意末尾没有/，这样复制的是目录本身）
for app in financial-automation CRM-Assistant; do
    echo "  复制 $app..."
    copy_app "$app"
done

echo "==> 2/4 financial-automation：建 venv + 装依赖（国内镜像）"
( cd "$DST/financial-automation"
  "$PYTHON" -m venv .venv
  ./.venv/"$(venv_bin .)/pip" install -q -i "$MIRROR" -r requirements.txt )

echo "==> 3/4 CRM-Assistant：建 venv（标准库，无三方依赖）"
( cd "$DST/CRM-Assistant" && "$PYTHON" -m venv .venv )

echo "==> 4/4 跑「重构前」绿色基线"
echo "-- 测试 financial-automation --"
( cd "$DST/financial-automation" && ./.venv/"$(venv_bin .)/python" -m unittest tests.test_smoke )
echo ""
echo "-- 测试 CRM-Assistant --"
( cd "$DST/CRM-Assistant"
  ./.venv/"$(venv_bin .)/python" scripts/crm_assistant.py run-merge-policy-tests )

echo ""
echo "✅ 工作区就绪：$DST"
echo "   - financial-automation 测试通过"
echo "   - CRM-Assistant 测试通过"
echo "   可以开始第 17 节重构了！"
