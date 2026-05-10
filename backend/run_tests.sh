#!/usr/bin/env bash
# =============================================================================
# DC Network Planner - 测试运行脚本
# 所有参数透传给 pytest（如 -v, -k "region", -x 等）
# 用法: bash run_tests.sh [pytest 选项...]
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   DC Network Planner - 测试                          ${NC}"
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

# 检查测试依赖
MISSING=""
python -c "import pytest" 2>/dev/null || MISSING="$MISSING pytest"
python -c "import httpx" 2>/dev/null || MISSING="$MISSING httpx"

if [ -n "$MISSING" ]; then
    echo -e "${YELLOW}⚠ 缺少依赖:$MISSING，正在安装...${NC}"
    pip install "pytest>=8.0" "httpx>=0.27.0"
    echo ""
fi

# 确认应用可导入
echo -e "${BLUE}► 检查应用导入...${NC}"
if python -c "from app.main import app" 2>/dev/null; then
    echo -e "${GREEN}  ✓ 应用导入成功${NC}"
else
    echo -e "${RED}  ✗ 应用导入失败，请检查 pip install -e . 是否执行${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}► 运行测试...${NC}"
echo ""

# 执行测试，所有参数透传
python -m pytest tests/ -v "$@"
EXIT_CODE=$?

echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   ✅ 全部通过!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
else
    echo -e "${RED}══════════════════════════════════════════════════════${NC}"
    echo -e "${RED}   ❌ 存在失败的测试 (退出码: $EXIT_CODE)${NC}"
    echo -e "${RED}══════════════════════════════════════════════════════${NC}"
fi

exit $EXIT_CODE
