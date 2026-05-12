#!/bin/bash
# 启动前端开发服务器，便于通过 localhost 或 127.0.0.1 访问。
cd "$(dirname "$0")"

# 首次运行时安装依赖。
if [ ! -d "node_modules" ]; then
    npm install
fi

npm run dev -- --host 0.0.0.0
