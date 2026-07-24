# DC Network Planner - 项目说明

[![CI/CD](https://img.shields.io/github/actions/workflow/status/zhou-xingxing/dc-network-planner/ci.yml?branch=main&label=CI%2FCD&style=flat-square)](https://github.com/zhou-xingxing/dc-network-planner/actions/workflows/ci.yml)
[![Backend Test Coverage](https://img.shields.io/badge/Backend%20Test%20Coverage-86%25-brightgreen?style=flat-square)](#测试覆盖率)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat-square&logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3.5%2B-42b883?style=flat-square&logo=vue.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-6.0%2B-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5.4%2B-646CFF?style=flat-square&logo=vite&logoColor=white)
![Element Plus](https://img.shields.io/badge/Element%20Plus-2.8%2B-409EFF?style=flat-square)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-GHCR-2496ED?style=flat-square&logo=docker&logoColor=white)

DC Network Planner 是面向数据中心网络平面地址规划的 Web 管理系统，用于集中维护 Region、网络平面类型、CIDR、VLAN、网关和变更历史等数据。随着当前数据中心建设规模日益增大，其涉及的 Region 数量和网络平面类型也逐渐增加，传统的本地 Excel 管理方式存在以下问题：

- 多个 Region 的数据分散在多个本地文件中，难以统一查询和管理
- 无法快速检查某 IP 段是否已被分配
- 多人协作困难
- 数据变更无版本追溯能力

本系统旨在提供一个统一的 Web 管理平台来解决上述问题。

## 使用流程

1. 先创建**网络平面类型**（如管理平面、业务平面等）— 这是全局字典
2. 创建 **Region**（如 北京数据中心）
3. 进入 Region 详情页，为该 Region **添加**需要的网络平面类型，并填写 CIDR、VLAN ID、网关位置和网关 IP
4. 需要查重时使用 **IP 查找** 功能
5. 需要批量导入时使用 **导入** 功能（先下载模板填写后上传）
6. 所有操作在 **变更历史** 中可追溯

## 系统设计

详见 [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) 。

## 部署约束

> **当前后端仅支持单实例部署。** 请勿通过 `docker compose up --scale backend=2` 或类似方式横向扩展后端。约束原因和未来多实例演进条件见 [SYSTEM_DESIGN.md 的「单实例部署约束」](SYSTEM_DESIGN.md#34-单实例部署约束)。

## 项目结构

```text
./
├── backend/                 # FastAPI 后端、数据库迁移、测试和运维脚本
├── frontend/                # Vue 3 前端和 Nginx 容器配置
├── scripts/                 # 仓库级辅助脚本
├── .github/workflows/       # GitHub Actions 工作流
├── docker-compose.yml       # 本地一键部署编排
├── README.md                # 快速使用说明
└── SYSTEM_DESIGN.md         # 系统设计决策
```

后端分层、前端目录职责和关键入口见 [SYSTEM_DESIGN.md 的「项目结构」](SYSTEM_DESIGN.md#33-项目结构)。

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

也可以手动执行以下步骤。后端命令请始终在 `backend/` 目录下运行；本地 SQLite 默认数据库为 `backend/dc_network_planner.db`，配置从 `backend/.env` 加载。`backend/.env` 不提交到仓库，首次运行可从 `backend/.env.example` 复制生成。

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
npm run dev -- --host 0.0.0.0
```

启动验证：
- 本机访问：http://localhost:5173 或 http://127.0.0.1:5173
- 局域网访问：使用 Vite 输出的 Network 地址

`bash start.sh` 已经内置上述启动参数，推荐优先使用脚本启动。

> 前端 Vite 开发服务器已配置 API 代理，`/api` 请求自动转发到 `http://localhost:8000`。

### 步骤 3：初始化示例数据（可选）

执行前请先完成后端依赖安装；脚本仅在当前数据库还没有 Region 时写入示例数据，已有数据时会自动跳过。

```bash
cd ./backend
source venv/bin/activate
python scripts/seed.py
```

种子数据包含：
- 2 个 Region："北京数据中心"、"上海数据中心"
- 5 种网络平面类型：管理平面、业务平面、存储平面、内部通信平面、BMC平面
- 每个 Region 启用示例网络平面，并带有彼此不重叠的 CIDR、VLAN 和网关信息

## 配置说明

后端配置从 `backend/.env` 加载。仓库只提交 `backend/.env.example`，本地运行时复制为 `backend/.env` 后按需修改：

```bash
cd ./backend
cp -n .env.example .env
```

生产部署前至少确认以下配置：

| 配置项 | 说明 |
|---|---|
| `JWT_SECRET_KEY` | JWT 签名密钥，生产环境必须改成高强度随机值 |
| `BOOTSTRAP_ADMIN_USERNAME` | 初始管理员用户名，仅在 `users` 表为空时自动创建 |
| `BOOTSTRAP_ADMIN_PASSWORD` | 初始管理员密码，仅在 `users` 表为空时自动创建 |
| `DATABASE_URL` | SQLAlchemy 数据库连接地址，本地默认使用 `backend/dc_network_planner.db` |
| `APP_TIMEZONE` | 应用业务时区，用于解释定时备份 cron 等业务时间 |
| `BACKUP_DEFAULT_LOCAL_PATH` | 本地备份默认目录；本地开发默认 `backend/backups`，Docker 默认 `/app/data/backups` |

导入预览缓存、日志轮转、CORS 和跨 Region CIDR/VLAN 重叠策略等可选配置见 [`backend/.env.example`](backend/.env.example)。完整字段和默认值以 [`backend/app/config.py`](backend/app/config.py) 中的 `Settings` 为准；配置覆盖优先级和启动期静态配置的设计见 [SYSTEM_DESIGN.md 的「后端配置加载策略」](SYSTEM_DESIGN.md#后端配置加载策略)。Docker 部署可以直接通过容器环境变量覆盖配置。

系统运行日志默认以 JSON Lines 写入 `backend/logs/app.log`，按大小轮转。HTTP 响应会返回 `X-Request-ID`，排障时可用文件搜索定位同一次调用链：

```bash
tail -f backend/logs/app.log
rg "request-id-from-response" backend/logs/
```

Docker Compose 部署时，SQLite 主库、系统日志和本地备份分别保存到 `/app/data/dc_network_planner.db`、`/app/data/logs` 和 `/app/data/backups`，统一由 `dc-network-planner-data` volume 持久化。

## API 文档

启动后端后可访问：

- http://localhost:8000/docs：Swagger UI，支持在线调试。
- http://localhost:8000/redoc：ReDoc，适合阅读和查阅接口定义。

文档仅展示 External API，并支持无外网环境访问。OpenAPI Schema 地址为 http://localhost:8000/api/external/v1/openapi.json。

## Docker 部署

需要 Docker >= 24.0 和 Docker Compose >= 2.0。

```bash
# 一键部署（推荐）
docker compose up -d
docker compose logs -f
```

后端持久化数据统一保存在 `dc-network-planner-data` volume 挂载的 `/app/data` 目录：

- SQLite 主库：`/app/data/dc_network_planner.db`
- 系统日志：`/app/data/logs`
- 本地备份：`/app/data/backups`

`docker compose down` 会保留该命名卷；`docker compose down -v` 会连同数据库、日志和本地备份一起删除。

部署拓扑、持久化和镜像设计见 [SYSTEM_DESIGN.md 的「部署说明」](SYSTEM_DESIGN.md#8-部署说明)。服务编排的实际配置以 [`docker-compose.yml`](docker-compose.yml) 为准。

## CI/CD

提交到 `main` 或发起针对 `main` 的 Pull Request 时会自动执行后端门禁、前端门禁和 Docker 镜像构建验证。精确触发条件与命令以 [`.github/workflows/ci.yml`](.github/workflows/ci.yml) 为准，流程设计和镜像发布策略见 [SYSTEM_DESIGN.md 的「CI/CD 设计」](SYSTEM_DESIGN.md#9-cicd-设计)。

## 开发与贡献

<details>
<summary><strong>展开查看测试、代码检查与 pre-commit 命令</strong></summary>

### 后端代码检查

```bash
cd ./backend

# ruff → black --check → mypy（自动激活 venv）
bash run_checks.sh
# 或: make lint
```

### 运行全部后端测试

```bash
cd ./backend
source venv/bin/activate
python -m pytest tests/ -v
```

也可以使用测试脚本自动激活虚拟环境：

```bash
cd ./backend
bash run_tests.sh
```

### 后端完整门禁

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

以下命令在 `backend/` 目录执行：

```bash
source venv/bin/activate
python -m pytest tests/test_regions.py -v
```

### 运行单个测试用例

以下命令在 `backend/` 目录执行：

```bash
source venv/bin/activate
python -m pytest tests/test_regions.py::test_create_region -v
```

### 前端完整门禁

```bash
cd ./frontend
npm run lint
npm run type-check
npm run build
```

### pre-commit 钩子（可选）

```bash
# 在项目根目录执行，提交时自动 ruff --fix + black 格式化
pre-commit install
```

</details>

## 代码行数统计

<!-- code-lines:start -->
| 分类 | 文件数 | 代码行 |
|---|---:|---:|
| 后端代码 | 74 | 7,700 |
| 后端测试 | 25 | 4,429 |
| 前端代码 | 49 | 5,766 |
| 前端测试 | 0 | 0 |
| 合计 | 148 | 17,895 |
<!-- code-lines:end -->

## 许可证与商业授权

本项目采用 [PolyForm Noncommercial License 1.0.0](LICENSE) 发布。该协议属于非商业源代码可见许可，并非 OSI 批准的开源许可证。个人学习、研究、测试、评估和其他非商业用途可免费使用；企业使用、生产环境部署、商业集成或作为商业产品/服务的一部分使用前，需获得项目权利人的单独书面商业授权。

商业授权边界详见 [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)。
