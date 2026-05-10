# HCS LLD 管理系统 - 项目说明

[![CI/CD](https://img.shields.io/github/actions/workflow/status/zhou-xingxing/hcs-lld-management/ci.yml?branch=main&label=CI%2FCD&style=flat-square)](https://github.com/zhou-xingxing/hcs-lld-management/actions/workflows/ci.yml)
[![Backend Test Coverage](https://img.shields.io/badge/Backend%20Test%20Coverage-86%25-brightgreen?style=flat-square)](#测试覆盖率)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat-square&logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3.5%2B-42b883?style=flat-square&logo=vue.js&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.4%2B-646CFF?style=flat-square&logo=vite&logoColor=white)
![Element Plus](https://img.shields.io/badge/Element%20Plus-2.8%2B-409EFF?style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-GHCR-2496ED?style=flat-square&logo=docker&logoColor=white)

HCS（华为云Stack）是企业内部部署的私有云平台。LLD（Low Level Design）是部署 HCS 所需的详细设计文档，通常以 Excel 文件形式记录部署云平台所需的各类网络平面（Network Plane）地址段规划。随着管理的云平台数量增多，传统的本地 Excel 管理方式存在以下问题：

- 多个 Region 的数据分散在多个文件中，难以统一查询
- 无法快速检查某 IP 段是否已被分配
- 数据变更无版本追溯能力
- 多人协作困难

本系统旨在提供一个 Web 管理平台来解决上述问题。

## 使用流程

1. 先创建**网络平面类型**（如管理平面、业务平面等）— 这是全局字典
2. 创建 **Region**（如 HCS华北-北京）
3. 进入 Region 详情页，为该 Region **添加**需要的网络平面类型，并填写 CIDR、VLAN ID、网关位置和网关 IP
4. 需要查重时使用 **IP 查找** 功能
5. 需要批量导入时使用 **导入** 功能（先下载模板填写后上传）
6. 所有操作在 **变更历史** 中可追溯

## 系统设计

详见 [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) 。


## 项目结构

```
./
├── backend/                              # Python FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI 应用入口 + CORS + 路由注册
│   │   ├── config.py                     # 应用配置与 backend/.env 加载
│   │   ├── database.py                   # SQLAlchemy 引擎 + 会话工厂
│   │   ├── dependencies.py               # 认证、权限和 DB 依赖
│   │   ├── exceptions.py                 # 业务异常定义
│   │   ├── models/                       # SQLAlchemy ORM 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── region.py                 # Region 模型
│   │   │   ├── network_plane_type.py     # 网络平面类型模型
│   │   │   ├── region_network_plane.py   # Region 网络平面实例模型
│   │   │   ├── change_log.py             # 变更日志模型
│   │   │   ├── user.py                   # 本地用户、角色和 Region 授权模型
│   │   │   └── backup.py                 # 备份配置与备份记录模型
│   │   ├── schemas/                      # Pydantic 请求/响应验证
│   │   │   ├── __init__.py
│   │   │   ├── common.py                 # 通用响应 (PaginatedResponse)
│   │   │   ├── region.py                 # Region 相关 Schema
│   │   │   ├── network_plane_type.py     # 网络平面类型 Schema
│   │   │   ├── change_log.py             # 变更日志 Schema
│   │   │   ├── lookup.py                 # IP 查找 Schema
│   │   │   ├── excel.py                  # Excel/统计 Schema
│   │   │   ├── user.py                   # 用户、角色和权限 Schema
│   │   │   └── backup.py                 # 备份配置和记录 Schema
│   │   ├── routers/                      # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                   # 登录和当前用户 API
│   │   │   ├── regions.py                # Region + Region-平面关联 API
│   │   │   ├── network_plane_types.py    # 网络平面类型 API
│   │   │   ├── lookup.py                 # IP/CIDR 查找 API
│   │   │   ├── excel.py                  # Excel 导入/导出 API
│   │   │   ├── change_logs.py            # 变更日志查询 API
│   │   │   ├── stats.py                  # 统计 API
│   │   │   ├── users.py                  # 用户管理 API
│   │   │   └── backup.py                 # 备份配置和执行 API
│   │   ├── services/                     # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── change_log.py             # 变更日志记录工具
│   │   │   ├── region.py                 # Region 业务逻辑
│   │   │   ├── region_plane.py           # Region 网络平面实例逻辑
│   │   │   ├── network_plane_type.py     # 网络平面类型业务逻辑
│   │   │   ├── lookup.py                 # IP/CIDR 查找逻辑
│   │   │   ├── excel.py                  # Excel 导入预览/确认逻辑
│   │   │   ├── auth.py                   # 本地账号、密码和 JWT 逻辑
│   │   │   ├── backup.py                 # 备份配置、校验和执行逻辑
│   │   │   └── backup_scheduler.py       # 后台备份调度器
│   │   └── utils/                        # 工具函数
│   │       ├── __init__.py
│   │       ├── ip_utils.py               # IP/CIDR 解析、重叠检测
│   │       ├── excel_utils.py            # Excel 模板生成、导入解析、导出构建
│   │       └── time_utils.py             # UTC 存储与应用时区转换
│   ├── alembic/                          # 数据库迁移
│   │   ├── env.py                        # Alembic 环境配置 (render_as_batch=True)
│   │   ├── script.py.mako                # 迁移脚本模板
│   │   └── versions/                     # 迁移版本文件（初始表、认证、备份、平面树、scope 等）
│   ├── alembic.ini                       # Alembic 配置
│   ├── .env.example                      # 后端环境变量示例，复制为 .env 后使用
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
│   │   │   ├── auth.js                   # 登录和当前用户 API
│   │   │   ├── regions.js                # Region + 网络平面 API
│   │   │   ├── networkPlaneTypes.js      # 网络平面类型 API
│   │   │   ├── lookup.js                 # IP 查找 API
│   │   │   ├── excel.js                  # Excel 导入/导出 + 统计 + 变更日志 API
│   │   │   ├── users.js                  # 用户管理 API
│   │   │   └── backup.js                 # 备份配置和执行 API
│   │   ├── assets/styles/
│   │   │   └── main.css                  # 全局样式
│   │   ├── components/
│   │   │   └── layout/
│   │   │       ├── AppLayout.vue         # 布局组件 (侧边栏 + 顶栏 + 内容区)
│   │   │       └── SideMenu.vue          # 侧边导航菜单
│   │   ├── router/
│   │   │   └── index.js                  # 路由定义（登录 + 9 个业务页面，懒加载）
│   │   ├── stores/
│   │   │   └── app.js                    # Pinia 状态（登录态、当前用户、侧边栏）
│   │   ├── utils/
│   │   │   └── time.js                   # 前端时间格式化
│   │   └── views/
│   │       ├── Login.vue                 # 登录页
│   │       ├── Dashboard.vue             # 仪表盘
│   │       ├── Regions.vue               # 区域管理
│   │       ├── RegionDetail.vue          # 区域详情 + 网络平面管理
│   │       ├── PlaneTypes.vue            # 网络平面类型管理
│   │       ├── Lookup.vue                # IP 查找
│   │       ├── ImportExport.vue          # 导入 / 导出
│   │       ├── ChangeLogs.vue            # 变更历史
│   │       ├── BackupConfig.vue          # 备份配置
│   │       └── Users.vue                 # 用户管理
│   ├── index.html
│   ├── package.json                      # NPM 依赖
│   ├── package-lock.json                 # NPM 锁定依赖
│   ├── vite.config.js                    # Vite 配置 (含 API 代理)
│   ├── .env.development                  # 开发环境变量
│   ├── run_build.sh                      # 前端构建脚本
│   └── start.sh                          # 前端启动脚本
│
├── scripts/
│   └── count_code_lines.py               # README 代码行统计脚本
├── .pre-commit-config.yaml               # pre-commit 配置
├── .gitignore
├── AGENTS.md                             # Agent 工作约定
├── CLAUDE.md                             # Claude 工作约定
├── TODO.md                               # 待办事项
├── SYSTEM_DESIGN.md                      # 系统架构设计文档
└── README.md                             # 项目说明
```

Docker 部署文件：

```
./
├── docker-compose.yml                    # Docker Compose 编排
├── backend/
│   ├── Dockerfile                        # 后端 Docker 镜像
│   └── .dockerignore
└── frontend/
    ├── Dockerfile                        # 前端 Docker 镜像
    ├── nginx.conf                        # Nginx 配置 (API 代理 + SPA 路由)
    └── .dockerignore
```

## 启动方式

### 前提条件

- Python >= 3.12
- Node.js >= 20
- npm >= 9

### 步骤 1：启动后端

推荐使用后端启动脚本，它会自动进入 `backend/` 目录、准备虚拟环境、执行迁移并启动服务：

```bash
cd ./backend
cp -n .env.example .env  # 首次运行时复制，可按需修改
bash start.sh
```

也可以手动执行以下步骤。后端命令请始终在 `backend/` 目录下运行；本地 SQLite 默认数据库为 `backend/hcs_lld.db`，配置从 `backend/.env` 加载。`backend/.env` 不提交到仓库，首次运行可从 `backend/.env.example` 复制生成。

```bash
cd ./backend

# 复制环境变量示例（首次运行）
cp -n .env.example .env

# 创建虚拟环境（首次运行）
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖（首次运行）
pip install -r requirements.txt
pip install -e .

# 执行 / 更新数据库迁移
alembic upgrade head

# 启动后端服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动验证：
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

首次启动时，后端会自动创建初始管理员账户：
- 用户名：`admin`
- 密码：`admin`

生产环境请在 `backend/.env` 中修改初始管理员用户名、密码和 `JWT_SECRET_KEY` 配置。

### 步骤 2：启动前端

推荐使用前端启动脚本：

```bash
cd ./frontend
bash start.sh
```

也可以手动执行以下步骤。

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

执行前请先完成后端依赖安装；脚本仅在当前数据库还没有 Region 时写入示例数据，已有数据时会自动跳过。

```bash
cd ./backend
source venv/bin/activate
python seed.py
```

种子数据包含：
- 2 个 Region："HCS华北-北京"、"HCS华东-上海"
- 5 种网络平面类型：管理平面、业务平面、存储平面、内部通信平面、BMC平面
- 每个 Region 启用示例网络平面，并带有 CIDR、VLAN 和网关信息

## 配置说明

后端配置从 `backend/.env` 加载。仓库只提交 `backend/.env.example`，本地运行时复制为 `backend/.env` 后按需修改：

```bash
cd ./backend
cp -n .env.example .env
```

常用配置项：

| 配置项 | 说明 |
|---|---|
| `DATABASE_URL` | SQLAlchemy 数据库连接地址，本地默认使用 `backend/hcs_lld.db` |
| `APP_TIMEZONE` | 应用业务时区，用于解释定时备份 cron 等业务时间 |
| `JWT_SECRET_KEY` | JWT 签名密钥，生产环境必须改成高强度随机值 |
| `BOOTSTRAP_ADMIN_USERNAME` | 初始管理员用户名，仅在 `users` 表为空时自动创建 |
| `BOOTSTRAP_ADMIN_PASSWORD` | 初始管理员密码，仅在 `users` 表为空时自动创建 |
| `BOOTSTRAP_ADMIN_DISPLAY_NAME` | 初始管理员显示名，仅在 `users` 表为空时自动创建 |
| `BACKUP_DEFAULT_LOCAL_PATH` | 本地备份默认目录 |
| `BACKUP_SCHEDULER_INTERVAL_SECONDS` | 后台备份调度扫描周期 |

Docker 部署时也可以通过环境变量覆盖这些配置；Compose 默认将后端数据库写入持久化 volume。

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

### 测试覆盖率

最近一次本地统计：后端行覆盖率 **85.54%**（终端摘要四舍五入显示为 86%）。统计命令为
`cd backend && make coverage`，数字来自 `backend/coverage.xml` 中的 `line-rate=0.8554`。

```bash
cd ./backend
make coverage
```

覆盖率报告会输出到终端，并生成 `backend/htmlcov/index.html` 和 `backend/coverage.xml`。

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

## API 文档

启动后端后访问 http://localhost:8000/docs 即可查看交互式 API 文档（Swagger UI），支持在线测试所有 API。

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

## 代码行数统计

<!-- code-lines:start -->
| 分类 | 文件数 | 代码行 |
|---|---:|---:|
| 后端代码 | 61 | 4,257 |
| 后端测试 | 12 | 1,797 |
| 前端代码 | 29 | 3,209 |
| 前端测试 | 0 | 0 |
| 合计 | 102 | 9,263 |
<!-- code-lines:end -->

## 许可证与商业授权

本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE) 发布。该协议属于非商业源代码可见许可，并非 OSI 批准的开源许可证。个人学习、研究、测试、评估和其他非商业用途可免费使用；企业使用、生产环境部署、商业集成或作为商业产品/服务的一部分使用前，需获得项目权利人的单独书面商业授权。

商业授权边界详见 [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)。
