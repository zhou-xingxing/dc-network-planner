# OpenAPI 文档第三方静态资源

这些文件随 DC Network Planner 后端一起发布，使 Swagger UI 和 ReDoc 在无外网环境中也能使用。

| 资源 | 固定版本 | 来源 | 本地文件 |
| --- | --- | --- | --- |
| Swagger UI JavaScript | `swagger-ui-dist@5.32.11` | `https://www.npmjs.com/package/swagger-ui-dist/v/5.32.11` | `swagger-ui/swagger-ui-bundle.js` |
| Swagger UI CSS | `swagger-ui-dist@5.32.11` | `https://www.npmjs.com/package/swagger-ui-dist/v/5.32.11` | `swagger-ui/swagger-ui.css` |
| Swagger UI favicon | `swagger-ui-dist@5.32.11` | `https://www.npmjs.com/package/swagger-ui-dist/v/5.32.11` | `favicon.png` |
| ReDoc JavaScript | `redoc@2.5.3` | `https://www.npmjs.com/package/redoc/v/2.5.3` | `redoc/redoc.standalone.js` |
| ReDoc 页脚图标 | `redoc@2.5.3` 配套资源 | `https://cdn.redoc.ly/redoc/logo-mini.svg` | `redoc/logo-mini.svg` |

各文件的 SHA-256 统一记录在 `SHA256SUMS`，后端测试会自动核对清单、文件集合和实际内容。上游许可证、NOTICE 和打包生成的 license 文件保存在对应子目录中。ReDoc 原始 bundle 中的页脚图标地址已替换为 `/static/api-docs/redoc/logo-mini.svg`，因此 JavaScript 校验值不同于 npm 原始文件。升级资源时必须重新执行该替换，同时更新版本、许可证和 `SHA256SUMS`，并验证两个文档页面不发起外部静态资源请求。
