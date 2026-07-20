# OneNote MCP 开发守则

## 代码与目录

- 使用 Python 3.10+、类型标注和 `async` HTTP 调用；业务逻辑放在 `onenote_mcp/`，根脚本仅用于兼容启动。
- Graph API 调用必须通过统一客户端，禁止在工具函数中直接拼接 Bearer token 或泄露响应正文。
- 保持 MCP 工具名稳定；接口破坏性变更必须在 README 和设计文档中说明。

## 认证与安全

- 只使用 Public Client + Device Code Flow。禁止读取、要求、保存或记录 `AZURE_CLIENT_SECRET`、token、refresh token、邮箱或 Client ID。
- 持久化令牌必须通过 `msal-extensions` 平台加密缓存；无法加密时仅允许会话内缓存，禁止明文降级。
- 写入工具默认关闭，只有 `ONENOTE_ENABLE_WRITES=true` 才可调用 Graph 写端点。
- 日志与 MCP 错误不得包含 Graph 原始响应体、认证材料或账号资料。

## 变更、测试与验收

- 每项功能变更都要有 Mock 单元测试；真实账号验证须在用户明确确认后进行。
- 真实写入只允许针对唯一命名的测试 Notebook，记录的资源 ID 不得写入仓库或日志。测试完成后恢复写入开关为 `false`。
- 创建 Notebook/Section 不能依赖 Graph 自动回滚；必须在文档中给出 OneNote/OneDrive 手动清理步骤。
- 不使用 `git reset --hard` 或覆盖用户既有改动；小而可审查的提交优先。

## 自我迭代与参考项目

- 每解决一个 non-trivial 问题，在 `docs/lessons/` 按主题记录问题、根因、方案与预防措施；必要时同步本文件。
- 参考对标项目固定为 [ZubeidHendricks/azure-onenote-mcp-server](https://github.com/ZubeidHendricks/azure-onenote-mcp-server)。它用于逆向分析创建 Notebook、Section 等 Graph 调用；其 Client Secret 认证方式不得迁入主项目。
- 初始化或更新参考目录时，在主项目根目录执行：`git clone https://github.com/ZubeidHendricks/azure-onenote-mcp-server.git`。若目录已存在，使用该目录自身的 Git 状态与提交记录进行分析，不重复 clone 或覆盖其中内容。
- clone 目标必须是主项目根目录下的 `azure-onenote-mcp-server/`，并由 `.gitignore` 忽略。可在设计文档记录参考 commit 与 API 行为，但不得复制、导入、暂存或提交其代码。
