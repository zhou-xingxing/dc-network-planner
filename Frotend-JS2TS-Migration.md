# Frontend JS to TS 迁移记录

> 文件名按本次任务要求保留为 `Frotend-JS2TS-Migration.md`。

## 迁移目标

本次迁移目标是把前端从 JavaScript 渐进升级为 TypeScript，在不改变现有业务行为的前提下，为 API 契约、页面状态、表单、表格和路由等边界补充类型约束。

迁移原则：

- 保持现有技术栈不变：Vue 3 + Vite + Element Plus + Pinia + Axios。
- 不借 TypeScript 迁移重构业务流程、接口路径或字段命名。
- 前后端字段继续使用当前 API 的 `snake_case`，不额外引入字段映射层。
- 每一阶段完成后使用 `npm run type-check` 和 `npm run build` 验证。

## 分支

本次迁移在独立分支执行：

```bash
frontend-ts-migration
```

## 迁移前基线

迁移前先在 `frontend/` 下执行：

```bash
npm run build
```

结果：通过。

说明：

- Vite 仍提示部分 chunk 超过 500 kB，这是迁移前已有的构建提示，不是本次迁移引入的失败。
- npm update check 仍提示本机配置目录权限问题，不影响构建结果。

## 第 1 步：添加 TypeScript 基础设施

新增开发依赖：

```json
{
  "@vue/tsconfig": "^0.9.1",
  "typescript": "^6.0.3",
  "vue-tsc": "^3.3.4"
}
```

更新内容：

- `frontend/package.json`
  - 新增脚本：`type-check`
- `frontend/package-lock.json`
  - 锁定 TypeScript 相关依赖
- `frontend/tsconfig.json`
  - 基于 `@vue/tsconfig/tsconfig.dom.json`
  - 开启渐进迁移所需的 `allowJs`
  - 配置 `@/*` 路径别名
  - 保留 `ignoreDeprecations: "6.0"` 以兼容 TypeScript 6 对 `baseUrl` 的弃用提示
- `frontend/src/env.d.ts`
  - 增加 Vite / Vue 类型声明

验证：

```bash
npm run type-check
npm run build
```

结果：通过。

## 第 2 步：新增核心业务类型

新增目录：

```text
frontend/src/types/
```

新增类型文件：

```text
common.ts
region.ts
networkPlaneType.ts
user.ts
backup.ts
lookup.ts
excel.ts
changeLog.ts
stats.ts
index.ts
```

覆盖的主要类型：

- 通用类型：`EntityId`、`DateTimeString`、`PaginatedResponse<T>`、`MessageResponse`
- Region：`Region`、`RegionDetail`、`RegionPlane`
- 网络平面类型：`NetworkPlaneType`
- 用户：`User`、`CurrentUser`、`UserRole`、`LoginResponse`
- 备份：`BackupConfig`、`BackupRecord`、`BackupMethod`
- 查找：`LookupResult`、`LookupResponse`
- Excel：`ImportPreview`、`ImportResult`、`ImportErrorItem`
- 变更日志：`ChangeLog`
- 统计：`SystemStats`

类型来源主要参考后端 Pydantic schema 和现有前端 API 使用方式。

验证：

```bash
npm run type-check
npm run build
```

结果：通过。

## 第 3 步：迁移 API 层

将以下 API 文件从 `.js` 迁移为 `.ts`：

```text
frontend/src/api/request.js              -> request.ts
frontend/src/api/auth.js                 -> auth.ts
frontend/src/api/regions.js              -> regions.ts
frontend/src/api/networkPlaneTypes.js    -> networkPlaneTypes.ts
frontend/src/api/users.js                -> users.ts
frontend/src/api/backup.js               -> backup.ts
frontend/src/api/lookup.js               -> lookup.ts
frontend/src/api/excel.js                -> excel.ts
```

主要改动：

- API 函数增加请求参数类型和 `Promise<...>` 返回类型。
- Axios 响应类型使用当前拦截器语义：响应拦截器返回 `response.data`。
- `request.ts` 中补充 Axios 错误类型。
- 错误响应体使用 `unknown` + 类型收窄读取 `detail`，避免直接使用 `any`。
- 保持所有接口路径、HTTP 方法、请求字段和错误提示逻辑不变。

验证：

```bash
npm run type-check
npm run build
```

结果：通过。

## 第 4 步：迁移公共支撑层

迁移文件：

```text
frontend/src/main.js          -> main.ts
frontend/src/router/index.js  -> index.ts
frontend/src/stores/app.js    -> app.ts
frontend/src/utils/time.js    -> time.ts
frontend/vite.config.js       -> vite.config.ts
```

同步更新：

- `frontend/index.html`
  - 入口从 `/src/main.js` 改为 `/src/main.ts`

主要改动：

- `stores/app.ts`
  - `currentUser` 改为 `CurrentUser | null`
  - `setSession`、`setCurrentUser`、`canManageRegionBusiness` 增加类型
  - 读取 localStorage 的用户信息时增加 JSON 解析保护
- `router/index.ts`
  - 增加 `RouteMeta` 类型声明
  - 路由表使用 `RouteRecordRaw[]`
  - 登录 redirect 参数做数组场景收窄
- `utils/time.ts`
  - `formatDateTime` 增加入参类型

验证：

```bash
npm run type-check
npm run build
```

结果：通过。

## 第 5 步：迁移 Vue 页面脚本

将所有页面和布局组件的脚本切换为：

```vue
<script setup lang="ts">
```

涉及文件：

```text
frontend/src/components/layout/AppLayout.vue
frontend/src/components/layout/SideMenu.vue
frontend/src/views/Login.vue
frontend/src/views/Profile.vue
frontend/src/views/Dashboard.vue
frontend/src/views/Users.vue
frontend/src/views/PlaneTypes.vue
frontend/src/views/BackupConfig.vue
frontend/src/views/Regions.vue
frontend/src/views/RegionDetail.vue
frontend/src/views/Lookup.vue
frontend/src/views/ImportExport.vue
frontend/src/views/ChangeLogs.vue
```

主要类型修复：

- 把 `ref([])` 改为明确数组类型，避免 TypeScript 推断为 `never[]`。
- 给 Element Plus 表单实例增加 `FormInstance` 类型。
- 给上传文件增加 `UploadFile` 类型。
- 给表格行数据、树节点、筛选参数、导入预览结果、导入确认结果补充类型。
- 对路由 query、可空 ID、可空 API 响应字段做必要类型收窄。
- Region 详情页中区分创建和更新 payload：
  - 创建网络平面时 `cidr` 必填
  - 更新网络平面时字段可选
- Dashboard 和 ChangeLogs 中的展示映射使用 `Record<string, string>`，避免字符串索引报错。

保持不变的内容：

- 页面模板结构不变。
- API 调用路径不变。
- 表单字段不变。
- 用户可见文案基本不变。
- 权限判断逻辑不变。
- 导入导出、Region 管理、网络平面管理等业务流程不变。

验证：

```bash
npm run type-check
npm run build
```

结果：通过。

## 第 6 步：同步文档和 CI

更新文件：

```text
AGENTS.md
README.md
SYSTEM_DESIGN.md
.github/workflows/ci.yml
```

主要更新：

- 前端技术栈更新为 Vue 3 + TypeScript + Vite + Element Plus。
- 前端验证命令更新为：

```bash
npm run type-check
npm run build
```

- README 项目结构更新为 `.ts` 文件路径。
- SYSTEM_DESIGN 增加 TypeScript 选型说明和 `types/` 目录职责。
- GitHub Actions 的 `build-frontend` job 增加：

```bash
npm run type-check
```

## 最终验证

最终执行：

```bash
cd frontend
npm run type-check
npm run build
```

结果：全部通过。

浏览器烟测：

- 启动开发服务器：

```bash
npm run dev -- --host 127.0.0.1
```

- 打开：

```text
http://127.0.0.1:5173/
```

结果：

- 页面自动跳转到 `/login?redirect=/dashboard`
- `#app` 正常渲染
- 登录页内容正常出现
- 未发现前端应用控制台错误

## 已知非阻断提示

以下提示在验证中出现，但不阻断迁移：

- Vite chunk size warning：部分产物超过 500 kB，迁移前已有。
- npm update check failed：本机 npm 配置目录权限提示，不影响 `type-check` 或 `build`。

## Review 关注点

建议后续 review 时重点看：

- API 类型是否与后端 Pydantic schema 保持一致。
- 页面迁移是否只补类型，没有夹带业务逻辑重构。
- `RegionDetail.vue` 中创建/更新网络平面 payload 的类型区分是否合理。
- `ImportExport.vue` 中上传文件、预览结果、导入结果的空值处理是否符合原交互。
- `stores/app.ts` 中 localStorage 用户信息解析失败时清理缓存的行为是否可接受。
- CI 新增 `npm run type-check` 后是否符合团队期望。

## 未完成事项

本次迁移没有新增前端单元测试或 E2E 测试。当前保障方式是：

- TypeScript 类型检查
- Vite 生产构建
- 本地浏览器烟测

如后续继续增强前端质量，可以考虑补充关键页面的 Playwright 冒烟测试。
