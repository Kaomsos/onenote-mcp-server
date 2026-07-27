# Changelog

本项目遵循语义化版本。发布日期以实际提交或发布记录为准。

## 2.1.0

### 变更

- 新增 `get_notebook`、`get_section` 和 `get_page_metadata` 精确读取工具。
- 新增 `delete_page(page_id, expected_title)`，删除前强制回读标题并精确匹配。
- Page 删除必须同时开启 `ONENOTE_ENABLE_WRITES=true` 和独立的 `ONENOTE_ENABLE_DELETES=true`；两个开关默认均为关闭。
- `delete_page` 标记为 destructive、非只读且非幂等 MCP 工具，便于客户端执行额外确认。
- 真实账号验收 Prompt 扩展至 16 个工具，并继续要求 Notebook 在 OneNote/OneDrive 人工清理。
- 参考本地 `azure-onenote-mcp-server` commit `38b8f7b` 的端点组织方式，但不迁入 Client Secret 认证、原始错误输出、Notebook/Section 删除或未经验证的搜索实现。

## 2.0.0

### 变更

- 将单文件实现拆分为配置、认证、Graph 客户端、工具和服务入口模块。
- 使用 Public Client Device Code Flow 和 `msal-extensions` 平台加密缓存；不再明文持久化 token。
- 默认关闭创建与更新工具，只有 `ONENOTE_ENABLE_WRITES=true` 时才允许 Graph 写请求。
- 统一 Graph 超时、错误分类、请求 ID 提取和敏感响应脱敏。
- 校验 OneNote 资源名称并对 URL path 中的资源 ID 编码。
- `create_notebook` 移除 Graph 不支持的 `description` 参数，这是相对于 1.x 的接口破坏性变化。
- 增加 Claude Code、Codex 和其他 stdio MCP 客户端的本地接入说明。
- 明确 Public Client ID 可保存在被忽略的本机配置中；Claude Code 实际配置使用 `local` scope，脱敏示例归档在 `.claude/`。
- 增加版本化、可复现的运行源码 ZIP 和 SHA-256 校验文件构建流程。
- 记录单租户 Azure APP 与个人 Microsoft 账号不匹配时的 Device Code Flow 排障经验。
- 增加可直接交给 Agent 的全工具真实账号验收 prompt，并用 pytest 校验其覆盖当前全部 MCP 工具及隔离、写保护和人工清理约束。
