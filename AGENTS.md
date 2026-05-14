# AGENTS.md

面向 AI Agents 的仓库入口提示词。这里只保留容易影响实现方向的高信号约束；项目的背景说明、系统设计、运行方式按需阅读 `README.md`、`SYSTEM_DESIGN.md` 和源码。

## 项目定位

DC Network Planner 是用于管理数据中心 Region 网络平面地址规划的 Web 应用，替代 Excel 手工维护。界面语言为中文（zh-CN）。

- 后端：Python 3.12 + FastAPI + SQLAlchemy + SQLite
- 前端：Vue 3 + Vite + Element Plus

## 最高优先级约束

- 代码注释和 git 提交信息尽量用中文编写（技术专用术语除外）。
- 更新关键代码实现逻辑后，必须同步更新 `SYSTEM_DESIGN.md` 中对应设计内容。
- 做后端功能改动时，默认用 `cd backend && make check` 作为完整门禁；需要覆盖率视图时再跑 `cd backend && make coverage`。
- 做前端改动时，默认至少跑 `cd frontend && npm run build`。
- 只有用户要求规划后续工作时再阅读 `TODO.md`，不要把 TODO 当作当前任务来源。

## 后端实现约束

- 分层保持 `routers/ -> services/ -> models/`：Router 处理 HTTP 和依赖注入，Service 承载业务逻辑并直接访问 SQLAlchemy Model，Schema 只做 Pydantic v2 API 请求/响应定义。
- Service 层禁止调用 `db.commit()` / `db.rollback()`；HTTP 请求路径由 `get_db()` 统一提交或回滚。Service 只在需要获取 ID、触发约束或保证同事务内可见时使用 `db.flush()`。非 HTTP 入口（启动初始化、后台调度任务等）必须在入口函数显式管理事务。
- 业务违规使用自定义业务异常，Service 层 `raise`，Router 层转换为 `HTTPException`；不要用 `ValueError` 表达业务异常，也不要用 `None` 表示校验失败。查找不到场景允许返回 `None`。
- 校验分层保持清晰：Router / Schema 负责请求形状、字段长度、枚举和数值范围；Service 先执行不依赖数据库的纯输入校验，再执行依赖数据库上下文的业务校验；数据变更和审计日志写入只发生在强校验通过后。
- 所有数据变更审计由 Service 在 mutate 后显式调用 `log_change()`，不要改成 SQLAlchemy events。
- CIDR/IP 判断统一使用 `app/utils/ip_utils.py` 和标准库 `ipaddress`；SQLite 没有原生 CIDR 类型，当前设计是在 Python 内存中做重叠与归属检测。
- Python 公共函数/类保持类型注解和 Google 风格 docstring；格式化与导入排序交给 black、ruff 和现有脚本。
- 更细设计按需查 `SYSTEM_DESIGN.md` 和现有源码。

## 前端实现约束

- 全项目使用 Vue 3 Composition API（`<script setup>`）和 Element Plus 中文界面。
- 业务数据由各 view 自行 fetch，不放入 Pinia 做全局缓存。
- 新增 API 调用、路由和页面状态时沿用 `frontend/src` 下现有组织方式。
- 更细设计按需查 `SYSTEM_DESIGN.md` 和现有源码。

## 测试与验证

- 后端测试使用独立内存 SQLite（`StaticPool`），在 `conftest.py` 中 override `get_db`。
- 后端业务逻辑改动必须补 pytest；重点回归 auth、backup、regions、lookup、plane tree、network plane types 等核心路径。

## 按需阅读

- 系统设计、数据模型、认证权限、备份、时区、导入导出语义：读 `SYSTEM_DESIGN.md`。
- 项目目录说明、部署运行方式：读 `README.md`。
