# OneNote MCP 完整验收指南

本指南用于在**不接触重要笔记**的前提下，验证 Device Code Flow、Notebook、Section 和 Page 创建能力。整个流程不会要求或使用 `AZURE_CLIENT_SECRET`。只有在账号所有者明确同意后，才可进入“受控写入验收”。

## 0. 验收边界与成功标准

验收对象仅限本流程新建的测试 Notebook，名称使用：

```text
MCP-ACCEPTANCE-YYYYMMDD-HHMMSS
```

成功标准：

1. MCP Server 能启动并显示认证、读取和写入工具。
2. Device Code Flow 能完成，且本地不会产生明文 token 文件。
3. 写入开关关闭时，创建工具被拒绝且没有 Graph 写请求。
4. 开关开启后，能依次创建 Notebook、Section、Page，并通过读取工具回读。
5. 验收结束后关闭写入开关，并由账号所有者在 OneNote/OneDrive 删除测试 Notebook。

禁止事项：不在配置、日志、截图、Issue 或 Git 提交中保存 device code、token、邮箱、Client ID 或资源 ID；不对已有重要 Notebook 执行创建、更新或测试操作。

## 1. 本地环境准备

### 1.1 软件依赖

- Windows、macOS 或 Linux。
- Python 3.10 或更高版本。
- [uv](https://docs.astral.sh/uv/)。
- Claude Desktop、Cursor 或任一支持 stdio MCP 的本地 Agent。
- 全球 Azure / Microsoft 账户。世纪互联云不属于本次验收范围。

在项目根目录执行：

```powershell
uv sync --all-groups
uv run pytest -q
```

预期结果为所有 Mock 测试通过。此步骤不需要 Azure 登录，也不会访问 OneNote。

### 1.2 配置审计

确认以下文件没有被提交或共享：

- `.env`、`.env.local`、`*.token`、`*.key`。
- Claude Desktop、Cursor 或本地 Agent 的个人配置文件。
- 平台加密 token cache 文件。

确认 `.gitignore` 包含 `azure-onenote-mcp-server/`，该参考项目只用于逻辑比对。

## 2. Azure 手动配置

以下操作在 Microsoft Entra 管理中心完成。

### 2.1 创建 Public Client 应用

1. 进入 **App registrations**，选择 **New registration**。
2. 设置一个清晰的本地名称，例如 `OneNote MCP Local Acceptance`。
3. 账户类型选择与实际账号匹配；若需个人 Microsoft 账户，选择支持个人 Microsoft 账户的选项。
4. 创建完成后，只复制 **Application (client) ID** 到本地 MCP 配置；它不是 Client Secret，但仍不得写入仓库。
5. 不创建 Client Secret，也不配置 `AZURE_CLIENT_SECRET`。

### 2.2 启用 Device Code Flow

1. 打开该应用的 **Authentication** 页面。
2. 在 **Advanced settings** 找到 **Allow public client flows**。
3. 选择 **Yes** 并保存。

该项目使用 Public Client 的 Device Code Flow；若组织条件访问策略阻止此流程，应由租户管理员先确认允许范围，不能绕过策略。

### 2.3 添加最小实用权限

在 **API permissions** 中添加 Microsoft Graph 的 **Delegated permissions**：

| 权限 | 用途 |
| --- | --- |
| `Notes.ReadWrite` | 列出、读取、创建和更新当前登录用户可访问的 OneNote 内容。 |
| `User.Read` | 保持现有登录用户基础权限兼容性。 |

不要添加 `Notes.ReadWrite.All`，除非有独立、已批准的组织范围需求。若租户要求管理员同意，应由管理员按最小权限原则执行。

## 3. MCP 客户端手动配置

以下示例以 Windows 项目路径为例。将 `your-public-client-id` 替换为本地保存的 Application (client) ID；不要把真实值提交到仓库。

```json
{
  "mcpServers": {
    "onenote": {
      "command": "uv",
      "args": [
        "--directory",
        "E:\\code\\MCP\\onenote-mcp-server",
        "run",
        "onenote-mcp-server"
      ],
      "env": {
        "AZURE_CLIENT_ID": "your-public-client-id",
        "ONENOTE_CACHE_TOKENS": "true",
        "ONENOTE_ENABLE_WRITES": "false"
      }
    }
  }
}
```

### 3.1 Claude Desktop

将 `onenote` 服务对象合并到 Claude Desktop 的本地 MCP 配置 `mcpServers` 中，保存后完全退出并重启 Claude Desktop。在连接器/开发者设置中确认 OneNote MCP Server 已连接并展示工具列表。

### 3.2 Cursor

在 Cursor 的 MCP 设置中添加同一份 stdio 服务定义，或将其合并到 Cursor 当前使用的 MCP JSON 配置。保存后重载 Cursor 窗口，并在 MCP 工具面板确认服务可用。

### 3.3 其他本地 Agent

只要客户端支持 stdio MCP，即使用相同的 `command`、`args` 和 `env`。客户端配置格式不同的情况下，只转换外层服务注册结构，内部三个字段保持不变。

## 4. 只读预检（无需写入确认）

保持 `ONENOTE_ENABLE_WRITES=false`，依次调用：

1. `check_authentication`：预期返回 `not_authenticated`（首次）或 `authenticated`（已有加密缓存）。
2. `start_authentication`：仅在当前 MCP 对话中查看 `verification_uri` 和 `user_code`，不要复制到日志或文档。
3. 在浏览器打开 `verification_uri`，输入 `user_code`，使用预定测试账号登录并完成同意。
4. `complete_authentication`：预期返回 `success`，不应返回用户名、邮箱或 token。
5. `check_authentication`：预期返回 `authenticated`，`token_caching` 为 `encrypted`；如为 `session_only`，停止验收并先排查本机安全存储。
6. `list_notebooks`：确认能读取列表。仅检查连通性，不复制列表内容到 Issue、日志或仓库。

### 4.1 写入保护验证

在写入开关仍为 `false` 时调用：

```text
create_notebook("MCP-ACCEPTANCE-BLOCKED")
```

预期返回：

```json
{
  "status": "error",
  "code": "writes_disabled"
}
```

确认 OneNote 中没有新增 Notebook。此验证通过后，才可请求账号所有者确认进入下一阶段。

## 5. 受控写入验收（必须先获得明确确认）

在得到账号所有者明确确认后，将 MCP 客户端配置中的：

```json
"ONENOTE_ENABLE_WRITES": "false"
```

改为：

```json
"ONENOTE_ENABLE_WRITES": "true"
```

重启 MCP 客户端，重新调用 `check_authentication` 确认仍为 `authenticated`。然后严格按下列顺序执行，所有名称均使用本次唯一时间戳：

### 5.1 创建并验证 Notebook

```text
create_notebook("MCP-ACCEPTANCE-20260720-153000")
```

预期：

- 返回 `status: success`。
- 返回的 `notebook.id` 和 `notebook.name` 均非空。
- 调用 `list_notebooks` 后能找到同名测试 Notebook。

只在当前会话中使用返回的 Notebook ID；不要将它粘贴到仓库文件。

### 5.2 创建并验证 Section

```text
create_section("<上一步的 notebook.id>", "MCP Acceptance Section")
```

预期：

- 返回 `status: success`。
- 返回的 `section.id` 和 `section.name` 均非空。
- 调用 `list_sections("<notebook.id>")` 后能找到该 Section。

### 5.3 创建并验证 Page

```text
create_page(
  "<上一步的 section.id>",
  "MCP Acceptance Page",
  "<p>OneNote MCP acceptance marker.</p>"
)
```

预期：

- 返回 `status: success`。
- 调用 `list_pages("<section.id>")` 后能找到该 Page。
- 调用 `get_page_content("<page.id>")`，返回 HTML 包含 `OneNote MCP acceptance marker.`。
- 在 OneNote 网页端或客户端中确认层级为：测试 Notebook → 测试 Section → 测试 Page。

### 5.4 异常处理

- `conflict`：名称已存在。不要改动已有资源；使用新的时间戳重新开始。
- `rate_limited`：停止请求，等待 Microsoft Graph 要求的时间后从“列出并确认状态”开始；不要盲目重发创建请求。
- 超时或网络错误：结果可能不确定。先通过 `list_notebooks`、`list_sections`、`list_pages` 确认是否已经创建，再决定是否使用新名称重试。
- `forbidden`：停止操作，检查是否为 Delegated `Notes.ReadWrite`、是否使用了正确账号，以及租户管理员策略。

## 6. 回滚、清理与验收记录

1. 将客户端配置立即恢复为 `ONENOTE_ENABLE_WRITES=false` 并重启客户端。
2. 在 OneNote/OneDrive 中手动删除本流程创建的整个 `MCP-ACCEPTANCE-...` Notebook；Notebook 和 Section 不使用 MCP 自动删除。
3. 在 OneNote/OneDrive 回收站中确认清理策略符合账号所有者要求。
4. 调用 `list_notebooks`，确认测试 Notebook 不再出现在列表中。
5. 验收记录只保留无敏感信息的结果：日期、操作者角色、客户端、通过/失败状态、错误码与是否完成手动清理。不得保存 user code、token、Client ID、邮箱或资源 ID。

建议使用以下脱敏记录模板：

```text
日期：YYYY-MM-DD
环境：本地 / 测试账号
只读预检：通过 / 未通过
写入保护：通过 / 未通过
Notebook 创建：通过 / 未通过
Section 创建：通过 / 未通过
Page 创建与回读：通过 / 未通过
人工清理：已完成 / 待完成
备注：仅记录错误码和处理动作
```

## 7. 退出与故障恢复

- 若需撤销本机登录状态，调用 `clear_token_cache`，然后关闭 MCP 客户端；下一次使用需要重新认证。
- 若加密缓存不可用，保持写入开关关闭并排查操作系统安全存储，不要改为明文缓存。
- 若任何步骤意外指向已有重要 Notebook，立即停止，不执行 Page 更新或任何进一步写操作，并由账号所有者检查 OneNote 回收站和版本历史。
