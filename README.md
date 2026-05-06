# HCS LLD 管理系统 - 项目说明

[![CI/CD](https://img.shields.io/github/actions/workflow/status/zhou-xingxing/hcs-lld-management/ci.yml?branch=main&label=CI%2FCD&style=flat-square)](https://github.com/zhou-xingxing/hcs-lld-management/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat-square&logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3.5%2B-42b883?style=flat-square&logo=vue.js&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.4%2B-646CFF?style=flat-square&logo=vite&logoColor=white)
![Element Plus](https://img.shields.io/badge/Element%20Plus-2.8%2B-409EFF?style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-GHCR-2496ED?style=flat-square&logo=docker&logoColor=white)

## 代码行数统计

<!-- code-lines:start -->
| 分类 | 文件数 | 代码行 |
|---|---:|---:|
| 后端代码 | 61 | 3,947 |
| 后端测试 | 12 | 1,487 |
| 前端代码 | 29 | 2,929 |
| 前端测试 | 0 | 0 |
| 合计 | 102 | 8,363 |
<!-- code-lines:end -->

## 项目结构

```
./
├── backend/                              # Python FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI 应用入口 + CORS + 路由注册
│   │   ├── database.py                   # SQLAlchemy 引擎 + 会话工厂
│   │   ├── config.py                     # 配置 (数据库URL, CORS等)
│   │   ├── models/                       # SQLAlchemy ORM 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── region.py                 # Region 模型
│   │   │   ├── network_plane_type.py     # 网络平面类型模型
│   │   │   ├── region_network_plane.py   # Region-平面关联模型
│   │   │   └── change_log.py             # 变更日志模型
│   │   ├── schemas/                      # Pydantic 请求/响应验证
│   │   │   ├── __init__.py
│   │   │   ├── common.py                 # 通用响应 (PaginatedResponse)
│   │   │   ├── region.py                 # Region 相关 Schema
│   │   │   ├── network_plane_type.py     # 网络平面类型 Schema
│   │   │   ├── change_log.py             # 变更日志 Schema
│   │   │   ├── lookup.py                 # IP 查找 Schema
│   │   │   └── excel.py                  # Excel/统计 Schema
│   │   ├── routers/                      # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── regions.py                # Region + Region-平面关联 API
│   │   │   ├── network_plane_types.py    # 网络平面类型 API
│   │   │   ├── lookup.py                 # IP/CIDR 查找 API
│   │   │   ├── excel.py                  # Excel 导入/导出 API
│   │   │   ├── change_logs.py            # 变更日志查询 API
│   │   │   └── stats.py                  # 统计 API
│   │   ├── services/                     # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── change_log.py             # 变更日志记录工具
│   │   │   ├── region.py                 # Region 业务逻辑
│   │   │   ├── region_plane.py           # Region-平面关联逻辑
│   │   │   ├── network_plane_type.py     # 网络平面类型业务逻辑
│   │   │   └── excel.py                  # Excel 导入预览/确认逻辑
│   │   └── utils/                        # 工具函数
│   │       ├── __init__.py
│   │       ├── ip_utils.py               # IP/CIDR 解析、重叠检测
│   │       └── excel_utils.py            # Excel 模板生成、导入解析、导出构建
│   ├── alembic/                          # 数据库迁移
│   │   ├── env.py                        # Alembic 环境配置 (render_as_batch=True)
│   │   ├── script.py.mako                # 迁移脚本模板
│   │   └── versions/                     # 迁移版本文件
│   │       └── c9ce20c8a1b2_initial.py   # 初始迁移
│   ├── alembic.ini                       # Alembic 配置
│   ├── .env                              # 环境变量
│   ├── requirements.txt                  # Python 依赖
│   ├── pyproject.toml                    # Python 项目配置
│   ├── Makefile                          # make lint / make test / make check
│   ├── run_tests.sh                      # 测试运行脚本
│   ├── run_checks.sh                     # 代码检查脚本
│   ├── seed.py                           # 种子数据脚本
│   └── start.sh                          # 后端启动脚本
│
├── frontend/                             # Vue 3 前端
│   ├── public/
│   ├── src/
│   │   ├── main.js                       # 应用入口 (注册插件)
│   │   ├── App.vue                       # 根组件
│   │   ├── api/                          # Axios API 封装
│   │   │   ├── request.js                # Axios 实例 + 拦截器
│   │   │   ├── regions.js                # Region + 网络平面 API
│   │   │   ├── networkPlaneTypes.js      # 网络平面类型 API
│   │   │   ├── lookup.js                 # IP 查找 API
│   │   │   └── excel.js                  # Excel 导入/导出 + 统计 + 变更日志 API
│   │   ├── assets/styles/
│   │   │   └── main.css                  # 全局样式
│   │   ├── components/
│   │   │   └── layout/
│   │   │       ├── AppLayout.vue         # 布局组件 (侧边栏 + 顶栏 + 内容区)
│   │   │       └── SideMenu.vue          # 侧边导航菜单
│   │   ├── router/
│   │   │   └── index.js                  # 路由定义 (7条路由, 懒加载)
│   │   ├── stores/
│   │   │   └── app.js                    # Pinia 状态 (操作者名)
│   │   └── views/
│   │       ├── Dashboard.vue             # 仪表盘
│   │       ├── Regions.vue               # 区域管理
│   │       ├── RegionDetail.vue          # 区域详情 + 网络平面管理
│   │       ├── PlaneTypes.vue            # 网络平面类型管理
│   │       ├── Lookup.vue                # IP 查找
│   │       ├── ImportExport.vue          # 导入 / 导出
│   │       └── ChangeLogs.vue            # 变更历史
│   ├── index.html
│   ├── package.json                      # NPM 依赖
│   ├── vite.config.js                    # Vite 配置 (含 API 代理)
│   ├── .env.development                  # 开发环境变量
│   └── start.sh                          # 前端启动脚本
│
├── docker-compose.yml                    # Docker Compose 编排
├── SYSTEM_DESIGN.md                     # 系统架构设计文档
└── 项目使用说明.md                        # 本文件：项目使用说明

Docker 部署文件：
├── backend/
│   ├── Dockerfile                        # 后端 Docker 镜像 (Python 3.12-slim, 多阶段构建)
│   └── .dockerignore
├── frontend/
│   ├── Dockerfile                        # 前端 Docker 镜像 (Node 20 构建 + Nginx 运行)
│   ├── nginx.conf                        # Nginx 配置 (API 代理 + SPA 路由)
│   └── .dockerignore
```

## 启动方式

### 前提条件

- Python >= 3.12
- Node.js >= 18
- npm >= 9

### 步骤 1：启动后端

```bash
cd ./backend

# 创建并激活虚拟环境（首次运行）
python3 -m venv venv
source venv/bin/activate

# 安装依赖（首次运行）
pip install -r requirements.txt
pip install -e .

# 执行数据库迁移（首次运行）
alembic upgrade head

# 启动后端服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动验证：
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

### 步骤 2：启动前端

```bash
cd ./frontend

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm run dev
```

启动验证：访问 http://localhost:5173

> 前端 Vite 开发服务器已配置 API 代理，`/api` 请求自动转发到 `http://localhost:8000`。

### 步骤 3：初始化示例数据（可选）

```bash
cd ./backend
source venv/bin/activate
python seed.py
```

种子数据包含：
- 2 个 Region："HCS华北-北京"、"HCS华东-上海"
- 5 种网络平面类型：管理平面、业务平面、存储平面、内部通信平面、BMC平面
- 每个 Region 启用示例网络平面，并带有 CIDR、VLAN 和网关信息

## 快速启动脚本

```bash
# 后端
cd backend && bash start.sh

# 前端 (新终端窗口)
cd frontend && bash start.sh
```

## 运行测试 & 代码检查

### 代码检查

```bash
cd ./backend

# ruff → black --check → mypy（自动激活 venv）
bash run_checks.sh
# 或: make lint
```

### 运行全部测试

```bash
cd ./backend
source venv/bin/activate
python -m pytest tests/ -v
```

或使用测试脚本（会自动激活虚拟环境）：

```bash
cd ./backend
bash run_tests.sh
```

### 完整门禁

```bash
cd ./backend
make check       # lint + test 串联执行
```

### 运行单个测试文件

```bash
source venv/bin/activate
python -m pytest tests/test_regions.py -v
```

### 运行单个测试用例

```bash
source venv/bin/activate
python -m pytest tests/test_regions.py::test_create_region -v
```

### pre-commit 钩子（可选）

```bash
# 在项目根目录执行，提交时自动 ruff --fix + black 格式化
pre-commit install
```

### 测试覆盖说明

后端测试覆盖认证、备份、Excel、健康检查、IP 查找、网络平面类型、平面树和 Region CRUD：

| 测试文件 | 用例数 | 覆盖内容 |
|---|---|---|
| `test_health.py` | 2 | 健康检查端点 |
| `test_regions.py` | 7 | Region 创建/列表/搜索/更新/删除/重复检查/不存在 |
| `test_lookup.py` | 5 | IP 查找/精确CIDR/重叠CIDR/无匹配/无效查询 |
| `test_plane_tree.py` | 17 | 多级平面树 CRUD + CIDR/网关约束 + 级联删除 |
| `test_excel_utils.py` | 3 | 模板生成/空数据解析/有效数据解析 |

每个测试用例使用独立的内存 SQLite 数据库，互不干扰。

## API 文档

启动后端后访问 http://localhost:8000/docs 即可查看交互式 API 文档（Swagger UI），支持在线测试所有 API。

## 系统设计

详见 [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) 。

## 使用流程

1. 先创建**网络平面类型**（如管理平面、业务平面等）— 这是全局字典
2. 创建 **Region**（如 HCS华北-北京）
3. 进入 Region 详情页，为该 Region **启用**需要的网络平面类型，并填写 CIDR、VLAN ID、网关位置和网关 IP
4. 需要查重时使用 **IP 查找** 功能
5. 需要批量导入时使用 **导入** 功能（先下载模板填写后上传）
6. 所有操作在 **变更历史** 中可追溯

## Docker 部署

```bash
# 一键部署（推荐）
docker compose up -d
docker compose logs -f
```

更详细的部署说明（架构图、分别构建、配置要点）见 [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) 第 9 节「部署说明」。

## CI/CD

CI 配置见 `.github/workflows/ci.yml`，每次 push/PR 自动执行：

| Job | 内容 | 触发条件 |
|---|---|---|
| `lint` | ruff → black --check → mypy | 所有 push 和 PR |
| `test-backend` | pytest tests/ -v | 所有 push 和 PR |
| `build-frontend` | npm install → npm run build | 所有 push 和 PR |
| `build-and-push` | Docker 构建并推送到 GHCR | main 分支 push 或 tag 推送 |
