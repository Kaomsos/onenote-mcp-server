# 初始化架构与创建能力逆向设计

## 当前基线

主项目原先为单个 FastMCP 脚本：MSAL Device Code Flow、手写 JSON token 文件和直接 `httpx` 调用混合在一起。当前 Git 历史的 `5853ef5` 已加入 `create_notebook` 与 `create_section`，因此本次不是重复添加功能，而是将其纳入可测试、安全的架构。

## 参考项目分析

参考项目 `ZubeidHendricks/azure-onenote-mcp-server`（本地参考 clone commit：`38b8f7bb8e671063b01fd4f950b6f630188ae213`）使用 `ClientSecretCredential`，不适用于本项目的个人 Device Code Flow。其可借鉴的逻辑只有资源层级与 Graph 调用：

- 创建 Notebook：`POST /me/onenote/notebooks`，正文为 `{"displayName": name}`。
- 创建 Section：`POST /me/onenote/notebooks/{notebook-id}/sections`，正文为 `{"displayName": name}`。

参考代码不进入主仓库，也不参与运行时依赖。

## 移植设计

`onenote_mcp/` 分为 `config`、`auth`、`graph`、`tools` 与 `server`：

- `auth` 维持 Public Client Device Code Flow，使用 `msal-extensions` 加密持久化 token cache；不保存或打印 token。
- `graph` 统一进行认证、超时、错误脱敏与请求 ID 提取；写请求不自动重试，避免网络不确定时重复创建。
- `tools` 提供稳定的 MCP 工具名。`create_notebook(name)` 移除未被 Graph 支持的 `description` 参数；`create_section(notebook_id, name)` 保持 ID + 名称接口。
- 资源名称在本地校验官方长度与非法字符；资源 ID 作为 URL path segment 编码。
- `ONENOTE_ENABLE_WRITES=false` 为默认值，创建和更新仅在显式启用后执行。

成功创建结果维持已有 `status`、`message`、`notebook` / `section` 结构；所有失败结果统一为不含敏感信息的 JSON 错误对象。

## 约束与后续方向

- 目标为全球 Microsoft Graph；世纪互联云不在本阶段范围内。
- Graph 支持删除 Page，但本服务不将 Notebook/Section 自动删除作为回滚机制。验收必须建立一次性测试 Notebook，并由用户在 OneNote/OneDrive 手动清理。
- 后续可评估分页、Section Group、受控的 Page 删除与 MCP Bundle 分发，但不能降低默认写入保护。
