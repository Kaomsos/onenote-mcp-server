# OneNote MCP Server

一个采用 Microsoft Device Code Flow 的本地 FastMCP 服务，用于读取和管理当前用户的 OneNote。创建与更新操作默认关闭，避免 Agent 意外改动笔记。

## 安全模型

- 仅需要 `AZURE_CLIENT_ID`；绝不配置 Client Secret。
- Token cache 默认启用，并由 `msal-extensions` 使用 Windows DPAPI、macOS Keychain 或 Linux LibSecret 加密。
- `ONENOTE_ENABLE_WRITES=false` 为默认值。需要创建 Notebook、Section 或 Page 时，必须显式改为 `true`。
- 不要把环境变量、token cache、MCP 客户端配置文件或测试输出提交到 Git。

## 环境与安装

需要 Python 3.10+、[uv](https://docs.astral.sh/uv/) 和一个全球 Azure / Microsoft 账户。

```powershell
git clone <your-fork-or-working-copy>
cd onenote-mcp-server
uv sync --all-groups
uv run pytest
```

在 Microsoft Entra App Registration 中创建或使用一个 **Public client** 应用：

1. 选择包含个人 Microsoft 账户的账户类型（如适用）。
2. 在 **Authentication → Advanced settings** 中启用 **Allow public client flows**。
3. 添加 Microsoft Graph **Delegated** 权限：`Notes.ReadWrite` 和 `User.Read`。
4. 记录 Application (client) ID。不要创建或配置 Client Secret。

`Notes.ReadWrite` 是本服务读取和写入用户 OneNote 的最小实用权限。企业租户若阻止 Device Code Flow，应由管理员先处理条件访问策略。

## 启动与配置

临时启动（默认不允许写入）：

```powershell
$env:AZURE_CLIENT_ID = "your-public-client-id"
$env:ONENOTE_ENABLE_WRITES = "false"
uv run onenote-mcp-server
```

Claude Desktop、Cursor 或任意支持 stdio MCP 的本地 Agent 都使用同一个服务定义；将下列对象加入该客户端的 MCP servers 配置，路径替换为本机绝对路径：

```json
{
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
```

Claude Desktop 的传统本地配置使用 `claude_desktop_config.json`；也可使用其本地 MCP/Extension 设置。Cursor 和其他本地 Agent 使用相同的 stdio 字段，只需放入各自的 MCP 配置文件。

## 首次认证与试用

1. 在 MCP 客户端调用 `start_authentication`。
2. 在返回的 `verification_uri` 打开浏览器，输入 `user_code` 并完成登录。
3. 调用 `complete_authentication`，随后使用 `check_authentication`。
4. 先调用 `list_notebooks`、`list_sections`、`list_pages` 验证只读访问。

进行创建验收前，必须先获得账号所有者的明确确认。确认后，把配置中的 `ONENOTE_ENABLE_WRITES` 设为 `true`，并只操作唯一命名的 `MCP-ACCEPTANCE-<timestamp>` 测试 Notebook：

1. `create_notebook(name)` 并记录返回的 ID。
2. `create_section(notebook_id, name)`。
3. `create_page(section_id, title, content_html)`。
4. 用 list/read 工具回读三层对象和页面内容。
5. 把 `ONENOTE_ENABLE_WRITES` 恢复为 `false`，随后在 OneNote/OneDrive 手动删除整个测试 Notebook。

Notebook 和 Section 不支持由本服务自动回滚；测试失败后同样应在 OneNote/OneDrive 中手动清理新建的测试资源。

## 工具接口

- `create_notebook(name: str)`：创建一个 Notebook。旧版的 `description` 参数已移除，因为 Microsoft Graph Notebook 创建接口不支持它。
- `create_section(notebook_id: str, name: str)`：在指定 Notebook 创建 Section。
- `create_page(section_id, title, content_html)`、`update_page_content`：保持原有功能，但受写入开关保护。
- `clear_token_cache`：删除本地加密 token cache，之后需要重新进行 Device Code Flow。
