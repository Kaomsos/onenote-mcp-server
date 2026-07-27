# OneNote MCP Server

一个采用 Microsoft Device Code Flow 的本地 FastMCP 服务，用于读取和管理当前用户的 OneNote。创建与更新操作默认关闭，避免 Agent 意外改动笔记。

## 安全模型

- 仅需要 `AZURE_CLIENT_ID`；绝不配置 Client Secret。
- Token cache 默认启用，并由 `msal-extensions` 使用 Windows DPAPI、macOS Keychain 或 Linux LibSecret 加密。
- `ONENOTE_ENABLE_WRITES=false` 为默认值。需要创建 Notebook、Section 或 Page 时，必须显式改为 `true`。
- `ONENOTE_ENABLE_DELETES=false` 独立控制 Page 删除；即使写入已开启，删除仍默认被拒绝。
- Application Client ID 不是密钥，可保存在被 Git 忽略的本机实际 MCP 配置中；不得放入示例、提交、截图、Issue、日志或 Agent 输出。
- Client Secret、token、refresh token、邮箱、token cache 和实际 MCP 配置不得提交到 Git。

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
$env:ONENOTE_ENABLE_DELETES = "false"
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
      "ONENOTE_ENABLE_WRITES": "false",
      "ONENOTE_ENABLE_DELETES": "false"
    }
  }
}
```

Claude Code 的脱敏示例位于 `.claude/mcp.example.json`。包含实际 Client ID 的个人项目配置应通过 `claude mcp add-json --scope local` 注册；`local` scope 会自动加载且不会在项目根生成可共享的 `.mcp.json`。根目录 `.mcp.json` 属于可提交的 `project` scope，不应用来保存实际 Client ID。Claude Desktop、Cursor 和其他本地 Agent 使用相同的 stdio 字段，只需放入各自被忽略的本机配置。

### Codex 项目级 dev 接入

Codex 桌面端、CLI 和 IDE 共用 MCP 配置。受信任项目可以使用仓库内的 `.codex/config.toml`；Codex 只会在项目被信任后加载它。仓库提交的是脱敏示例 `.codex/config.example.toml`，实际 `.codex/config.toml` 已被 Git 忽略。

本项目开发机上的实际配置直接运行当前工作目录，不安装发布包：

```toml
[mcp_servers.onenote]
command = "/opt/homebrew/bin/uv"
args = [
  "--directory",
  "/absolute/path/to/onenote-mcp-server",
  "run",
  "--frozen",
  "onenote-mcp-server",
]
startup_timeout_sec = 30
tool_timeout_sec = 60
enabled = true

[mcp_servers.onenote.env]
AZURE_CLIENT_ID = "YOUR_AZURE_CLIENT_ID_HERE"
ONENOTE_CACHE_TOKENS = "true"
ONENOTE_ENABLE_WRITES = "false"
ONENOTE_ENABLE_DELETES = "false"
```

接入步骤：

1. 复制 `.codex/config.example.toml` 为 `.codex/config.toml`，填写 `uv`、仓库绝对路径和 Application Client ID。
2. 确认实际 `.codex/config.toml` 被 Git 忽略；Client ID 只保存在该本机文件中，使 Finder 启动的 Codex Desktop 和 CLI 都能稳定注入变量。
3. 在 Codex 中信任该项目，然后完全重启 Codex；已有任务不会动态重载新配置。
4. 用 `codex mcp list` 或 Codex 中的 `/mcp` 确认 `onenote` 已启用并连接。
5. 调用 `check_authentication`。同一 macOS 用户和 Client ID 通常会复用 Keychain 加密的 MSAL 缓存；若返回未认证，再依次调用 `start_authentication` 和 `complete_authentication`。
6. 调用 `list_notebooks` 做只读验收，并确认 `ONENOTE_ENABLE_WRITES=false`、`ONENOTE_ENABLE_DELETES=false`。

不要把实际 Client ID 写进 `.codex/config.example.toml`、`.claude/mcp.example.json`、日志或提交内容，也不要配置 Client Secret。

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

开发仓库中的完整真实账号工具验收使用 [tests/prompts/onenote_full_tool_acceptance_zh.md](tests/prompts/onenote_full_tool_acceptance_zh.md)；运行源码 ZIP 按发布规则不携带 `tests/`，分发包用户使用包内 `docs/acceptance_guide_zh.md`。该 prompt 要求 Agent 创建唯一隔离 Notebook，覆盖当前全部 16 个工具，并在独立确认和双开关保护下选择是否删除测试 Page。当前版本不提供 Notebook/Section 删除工具，因此最终仍必须由账号所有者人工删除整个测试 Notebook，再由 Agent 只读回查。

## 工具接口

- `create_notebook(name: str)`：创建一个 Notebook。旧版的 `description` 参数已移除，因为 Microsoft Graph Notebook 创建接口不支持它。
- `get_notebook(notebook_id: str)`、`get_section(section_id: str)`、`get_page_metadata(page_id: str)`：精确读取单个资源的元数据。
- `create_section(notebook_id: str, name: str)`：在指定 Notebook 创建 Section。
- `create_page(section_id, title, content_html)`、`update_page_content`：保持原有功能，但受写入开关保护。
- `delete_page(page_id, expected_title)`：删除前回读并精确匹配标题；必须同时开启写入和独立删除开关。Notebook/Section 不支持 MCP 删除。
- `clear_token_cache`：删除本地加密 token cache，之后需要重新进行 Device Code Flow。

## 构建 2.1.0 运行源码包

发布前先运行测试，再执行标准库构建脚本：

```bash
uv run pytest -q
uv run python scripts/build_release.py
```

构建结果位于 `dist/`：

- `onenote-mcp-server-2.1.0.zip`
- `onenote-mcp-server-2.1.0.zip.sha256`

脚本从 `pyproject.toml` 读取版本，使用显式允许列表、固定时间戳和固定权限生成可复现 ZIP。包内只包含运行代码、锁文件、许可证、用户文档和脱敏客户端配置示例，不包含测试、开发缓存、实际 MCP 配置或认证材料。

## 使用分发包

1. 校验 ZIP 的 SHA-256，并解压到本机固定目录。
2. 进入解压后的 `onenote-mcp-server-2.1.0/`，运行 `uv sync --frozen --no-dev`。
3. 复制适合客户端的脱敏配置示例，填写本机绝对路径，并只在被忽略的本机实际配置中填写 `AZURE_CLIENT_ID`。
4. 保持 `ONENOTE_ENABLE_WRITES=false` 和 `ONENOTE_ENABLE_DELETES=false`，重启客户端并完成 MCP 连接或认证。
5. 依次运行 `check_authentication` 和 `list_notebooks` 完成只读验收。

macOS 可在 ZIP 所在目录执行：

```bash
shasum -a 256 -c onenote-mcp-server-2.1.0.zip.sha256
```
