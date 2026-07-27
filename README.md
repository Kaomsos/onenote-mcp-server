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

只有开发者要运行下述 pytest Notebook 上下文自动清理时，才在同一 App Registration 额外添加 Delegated `Files.ReadWrite`。生产 MCP 仍不会请求该 scope；禁止添加权限更大的 `Files.ReadWrite.All`，也不得把 Files 权限提供给 Agent。

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

Notebook 和 Section 不支持由 MCP 工具自动回滚；普通客户端和分发包验收仍应在 OneNote/OneDrive 中手动清理。下节开发仓库的 live test 另有一个严格隔离、不会暴露给 Agent 的本地控制面清理机制。

开发仓库中的真实账号工具验收规则记录在 [tests/prompts/onenote_full_tool_acceptance_zh.md](tests/prompts/onenote_full_tool_acceptance_zh.md)；运行源码 ZIP 按发布规则不携带 `tests/`，分发包用户使用包内 `docs/acceptance_guide_zh.md`。Agent 只处理唯一隔离 Notebook 内的非敏感数据面工具；同名清理、资源核验、可选 Page 删除和安全开关验证由本地 pytest 控制面执行。MCP 仍不暴露 Notebook/Section 删除工具。

### Claude CLI 自动化全工具验收

`tests/test_agent_acceptance_live.py` 是显式 opt-in 的 pytest live test，不再提供独立运行脚本。测试从被忽略且权限受限的 `.codex/config.toml` 内部取得 Application Client ID，为每个 Agent 阶段生成权限为 `0600` 的临时严格 MCP 配置，子进程退出后立即删除。

测试控制面复用现有 OneNote MCP 的平台加密 MSAL cache 和账号会话，并在本地临时请求 `Files.ReadWrite`。先运行以下无 Agent test：若现有 refresh token 能静默取得新增 scope，它会直接通过；只有 Microsoft 要求交互确认时，才把登录地址和临时代码直接写入 TTY，不进入 pytest 捕获输出：

```bash
ONENOTE_LIVE_CONTROL_AUTH=1 \
uv run pytest -q -m live \
  tests/test_agent_acceptance_live.py::test_files_control_scope_authentication_live -s
```

运行 Agent CRUD 验收：

```bash
ONENOTE_RUN_LIVE_AGENT_ACCEPTANCE=1 \
ONENOTE_PROVIDER_DATA_APPROVED=1 \
ONENOTE_LIVE_WRITES_APPROVED=1 \
ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1 \
uv run pytest -q -m live \
  tests/test_agent_acceptance_live.py::test_claude_agent_onenote_tools_live -s
```

若另行授权 Page 删除，由本地 pytest 进程直接调用受双开关和标题确认保护的 `delete_page`，Page ID 和删除结果不会发送给 Claude Provider：

```bash
ONENOTE_RUN_LIVE_AGENT_ACCEPTANCE=1 \
ONENOTE_PROVIDER_DATA_APPROVED=1 \
ONENOTE_LIVE_WRITES_APPROVED=1 \
ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1 \
ONENOTE_LIVE_PAGE_DELETE_APPROVED=1 \
uv run pytest -q -m live \
  tests/test_agent_acceptance_live.py::test_claude_agent_onenote_tools_live -s
```

每次 Agent 启动前，live test 都会检查锁文件、全部非 live Mock 测试、OneNote MCP 连接、16 工具注册表、删除 annotations、Claude/Codex 长期双开关、加密认证缓存、Graph 只读访问、临时配置权限和阶段工具白名单。数据面拆为 guard、Notebook、Section、Page、内容更新五个最小 Agent 阶段。runner 会实时读取 Claude `stream-json`，终端只显示阶段、OneNote 工具名和固定结果标记；完整 stdout/stderr 仍只保留在进程内存供最终覆盖验证，不打印 Tool result、ID、HTML 或认证信息。测试在 Agent 前后都由本地控制面清理精确同名 Notebook，不会把 Drive 权限、DriveItem 信息或清理决策交给 Provider。

这套机制背后的通用经验，包括认证复用与增量 scope、控制面/数据面分离、Agent 可观测性、阶段拆分、最终一致性和安全失败协议，记录在 [认证 MCP 的第三方 Agent 验收经验](docs/lessons/authenticated_mcp_agent_acceptance.md)。

OneNote Graph v1.0 只为普通 OneNote 内容提供受支持的 [Page 删除接口](https://learn.microsoft.com/en-us/graph/api/page-delete?view=graph-rest-1.0)，没有普通 Notebook/Section 删除接口。测试控制面利用 OneNote Notebook 在 OneDrive 中表现为 [`package.type=oneNote`](https://learn.microsoft.com/en-us/graph/api/resources/package?view=graph-rest-1.0) 的事实，并使用 OneDrive [`driveItem` 删除](https://learn.microsoft.com/en-us/graph/api/driveitem-delete?view=graph-rest-1.0)。它先按保留前缀和精确名称取得唯一非远程 package，再按 ID 精确回读并复核名称、类型、ID 和 eTag，最后携带 `If-Match` 移入回收站；分页、重复、类型不符、视图不一致或身份不完整都会 fail closed。

`Files.ReadWrite` 不在生产 `SCOPES` 中，只由 live-control AuthManager 临时请求；它与生产 MCP 复用平台加密 cache，但 Claude MCP、Codex MCP 和 Agent 临时配置本身都不会请求 Files scope。生产 Graph 客户端还强制执行 `/me/onenote/` endpoint allowlist，Agent 不获得 Drive 工具或通用 Graph 入口。每次清理必须单独设置 `ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1`。只有清理失败时才需要人工处理，并可用纯本地 test 回查：

```bash
ONENOTE_VERIFY_CLEANUP_NAME="MCP-FULL-TOOL-ACCEPTANCE-..." \
uv run pytest -q -m live \
  tests/test_agent_acceptance_live.py::test_manual_notebook_cleanup_verified_live -s
```

测试期结束后，可在 Azure App Registration 中移除或撤销不再需要的 delegated `Files.ReadWrite`。不要由验收代码自动删除共享 cache；如果需要立即清除全部本地认证状态，必须另行授权，并在清除后重新完成普通 OneNote MCP 认证。

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
