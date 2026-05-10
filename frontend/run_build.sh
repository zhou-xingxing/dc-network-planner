#!/usr/bin/env bash
# =============================================================================
# DC Network Planner - 前端编译检查脚本
# 用法: bash run_build.sh
# 说明: 验证前端代码能否正常编译
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   DC Network Planner - 前端编译检查                   ${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠ 未检测到 node_modules，正在安装依赖...${NC}"
    npm install
    echo ""
fi

echo -e "${BLUE}► 执行编译...${NC}"
echo ""

if npm run build 2>&1; then
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   ✅ 前端编译通过!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
else
    echo ""
    echo -e "${RED}══════════════════════════════════════════════════════${NC}"
    echo -e "${RED}   ❌ 前端编译失败${NC}"
    echo -e "${RED}══════════════════════════════════════════════════════${NC}"
    exit 1
fi
