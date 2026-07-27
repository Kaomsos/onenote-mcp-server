# Changelog

本项目遵循语义化版本。发布日期以实际提交或发布记录为准。

## Unreleased

- 新增显式 opt-in 的 Claude CLI pytest live case，在每次 Agent 调用前执行本机配置、长期安全开关、非 live Mock 测试、工具注册表、认证缓存和 Graph 只读前置检查。
- 真实工具验收改用权限为 `0600` 的临时严格 MCP 配置、逐阶段最小工具白名单和非持久 Claude 会话；原始 trace 仅用于内存中的实际工具覆盖验证。
- Agent 数据面拆分为 guard、Notebook、Section、Page 和内容更新五次独立调用；runner 并发读取 Claude `stream-json` 并实时显示脱敏的阶段、工具名和固定结果，同时保留完整内存 trace 供最终一次性验证。
- 同名 Notebook 检查、创建结果核验、可选 Page 删除、Notebook 测试上下文清理和保护开关验证改由本地测试代码执行，不向 Provider 发送敏感控制面数据。
- 为 live test 增加仅由本地控制面请求的 `Files.ReadWrite` 认证；经账号所有者授权复用生产 MCP 的平台加密 cache，生产 MCP scope、Claude/Codex 配置及 Agent 临时配置保持不含 Files 权限，也不暴露 Drive 或通用 Graph 工具。
- Notebook 上下文清理要求独立显式授权，仅接受保留前缀下精确命名、唯一、非远程的 OneNote DriveItem package；搜索命中后再按 ID 精确回读名称、类型和 eTag，并以 `If-Match` fail closed 地移入回收站，异常时保留人工清理与无 Agent 回查流程。
- Provider 数据传输、隔离 Notebook 写入、本地 Drive 清理和本地 Page 删除分别要求显式环境授权。
- Git 工作流简化为个人仓库单一 `origin`；移除原始项目上游与额外 `fork` remote 的维护约定。

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
