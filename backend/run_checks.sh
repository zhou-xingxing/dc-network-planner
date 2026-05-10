#!/usr/bin/env bash
# =============================================================================
# DC Network Planner - 代码检查脚本
# 用法: bash run_checks.sh
#   依次执行: ruff → black --check → mypy
#   mypy 为 non-blocking（允许类型问题但不阻断流程）
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   DC Network Planner - 代码检查                        ${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""

# 检测虚拟环境
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${YELLOW}⚠ 未检测到虚拟环境 (venv)${NC}"
    echo -e "${YELLOW}  请先执行: python3 -m venv venv${NC}"
    echo -e "${YELLOW}           source venv/bin/activate${NC}"
    echo -e "${YELLOW}           pip install -r requirements.txt${NC}"
    echo -e "${YELLOW}           pip install -e .${NC}"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查 lint 依赖
MISSING=""
python -c "import black" 2>/dev/null || MISSING="$MISSING black"
python -c "import ruff" 2>/dev/null || MISSING="$MISSING ruff"
python -c "import mypy" 2>/dev/null || MISSING="$MISSING mypy"

if [ -n "$MISSING" ]; then
    echo -e "${YELLOW}⚠ 缺少依赖:$MISSING，正在安装...${NC}"
    pip install black ruff mypy
    echo ""
fi

# 确认应用可导入
echo -e "${BLUE}► 检查应用导入...${NC}"
if python -c "from app.main import app" 2>/dev/null; then
    echo -e "${GREEN}  ✓ 应用导入成功${NC}"
else
    echo -e "${RED}  ✗ 应用导入失败${NC}"
    exit 1
fi
echo ""

FAILED=0

# ── ruff ──
echo -e "${CYAN}══════════ ruff 检查 ══════════${NC}"
if ruff check app/; then
    echo -e "${GREEN}  ✓ 通过${NC}"
else
    echo -e "${RED}  ✗ 未通过，提示: ruff check app/ --fix 可自动修复部分问题${NC}"
    FAILED=1
fi
echo ""

# ── black ──
echo -e "${CYAN}══════════ black 格式检查 ══════════${NC}"
if black --check app/; then
    echo -e "${GREEN}  ✓ 格式正确${NC}"
else
    echo -e "${RED}  ✗ 格式需要修正，运行 black app/ 自动格式化${NC}"
    FAILED=1
fi
echo ""

# ── mypy (non-blocking) ──
echo -e "${CYAN}══════════ mypy 类型检查 ══════════${NC}"
if mypy app/; then
    echo -e "${GREEN}  ✓ 通过${NC}"
else
    echo -e "${YELLOW}  ⚠ 存在类型问题（可查看上方详情）${NC}"
fi
echo ""

# ── 汇总 ──
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   ✅ 全部通过!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
else
    echo -e "${RED}══════════════════════════════════════════════════════${NC}"
    echo -e "${RED}   ❌ 存在需要修复的问题${NC}"
    echo -e "${RED}══════════════════════════════════════════════════════${NC}"
fi

exit $FAILED
