# OneNote MCP 完整验收指南

## 自动化优先

开发目录提供显式 opt-in 的 `tests/test_agent_acceptance_live.py`。需要通过 Claude Code Agent 覆盖工具时，必须使用该 pytest case，不要每次把整份流程临时交给 Agent 自行规划。运行源码 ZIP 按安全发布规则不包含 `tests/`，分发包环境继续使用下文人工流程。

测试控制面复用现有 OneNote MCP 的平台加密 MSAL cache 和账号会话，并在本地临时请求 `Files.ReadWrite`。先运行以下无 Agent test；它会优先静默复用现有会话，只有 Microsoft 要求交互确认时，Device Code 登录提示才直接写入 TTY，不进入 pytest 捕获输出：

```bash
ONENOTE_LIVE_CONTROL_AUTH=1 \
uv run pytest -q -m live \
  tests/test_agent_acceptance_live.py::test_files_control_scope_authentication_live -s
```

随后运行 Agent 数据面验收：

```bash
ONENOTE_RUN_LIVE_AGENT_ACCEPTANCE=1 \
ONENOTE_PROVIDER_DATA_APPROVED=1 \
ONENOTE_LIVE_WRITES_APPROVED=1 \
ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1 \
uv run pytest -q -m live \
  tests/test_agent_acceptance_live.py::test_claude_agent_onenote_tools_live -s
```

只有在账号所有者另行允许 Page 删除时，才增加 `ONENOTE_LIVE_PAGE_DELETE_APPROVED=1`。删除由本地 pytest 进程直接调用受保护的 `delete_page`，不会把资源 ID 或删除响应发送给 Claude Provider。

live test 会在任何 Agent CLI 调用前检查本机私有配置、长期双开关、锁文件、全部非 live Mock 测试、16 工具注册表、MCP 连接、加密认证缓存和 Graph 只读访问；每个 Agent 阶段前还会重新验证临时配置与精确工具白名单。数据面拆为 guard、Notebook、Section、Page、内容更新五次独立 Claude 调用。runner 实时读取 `stream-json`，但终端只显示阶段、OneNote 工具名和固定结果；完整输出只在内存中用于最终覆盖验证。它会在 Agent 启动前和退出后，通过本地控制面清理精确同名的测试 Notebook；Agent 不参与目标选择、Drive 查询或删除。

OneNote Graph v1.0 只提供受支持的 [Page 删除接口](https://learn.microsoft.com/en-us/graph/api/page-delete?view=graph-rest-1.0)，不支持删除普通 Notebook/Section。本地测试控制面依据 Notebook 的 [`package.type=oneNote`](https://learn.microsoft.com/en-us/graph/api/resources/package?view=graph-rest-1.0) 特征使用 OneDrive [driveItem 删除](https://learn.microsoft.com/en-us/graph/api/driveitem-delete?view=graph-rest-1.0)：先要求保留前缀、精确名称和唯一非远程 package，再按候选 ID 精确回读并复核名称、类型、ID/eTag，最后使用 `If-Match`；分页、歧义、详情或视图不一致一律停止。操作只会把条目移入回收站。

`Files.ReadWrite` 只由测试专用 AuthManager 临时请求；它复用生产 MCP 的平台加密 cache，但生产 MCP scope、Claude/Codex 配置及 Agent 临时配置本身都不含该权限，生产 Graph 客户端还限定为 `/me/onenote/` endpoint。测试不提供 Drive MCP 工具或通用 Graph 入口，也不向 Agent、被调用的 Agent、Provider、日志或报告传递 cache、token、DriveItem ID/eTag、搜索结果或删除响应。每次调用还必须由账号所有者单独设置 `ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1`，不得使用 `Files.ReadWrite.All`。

自动清理失败或人工流程结束后，可运行纯本地回查 test：

```bash
ONENOTE_VERIFY_CLEANUP_NAME="<pytest 输出的唯一测试 Notebook 名称>" \
uv run pytest -q -m live \
  tests/test_agent_acceptance_live.py::test_manual_notebook_cleanup_verified_live -s
```

测试期结束后，可从 Azure App Registration 移除或撤销不再需要的 delegated `Files.ReadWrite`。验收代码不得自动删除共享 cache；如果需要立即清除全部本地认证状态，必须另行授权，并接受普通 OneNote MCP 也要重新认证。

以下章节保留为人工排障、非 Claude 客户端和流程审计参考。

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
5. 验收结束后关闭写入开关；自动化开发验收由本地控制面回收测试 Notebook，人工/分发包流程由账号所有者在 OneNote/OneDrive 删除。

禁止事项：不在可提交配置、示例、日志、截图、Issue 或 Git 提交中保存 device code、token、邮箱、实际 Client ID 或资源 ID；实际 Client ID 只允许保存在被忽略的本机配置或客户端私有 scope 中。不对已有重要 Notebook 执行创建、更新或测试操作。

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

Application Client ID 是 Public Client 的公开标识，不按 Client Secret 管理，但包含实际值的配置仍必须使用客户端私有 scope 或 Git 忽略规则。Claude Code 应使用 `local` scope；Codex 应使用被忽略的 `.codex/config.toml`。

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
        "ONENOTE_ENABLE_WRITES": "false",
        "ONENOTE_ENABLE_DELETES": "false"
      }
    }
  }
}
```

### 3.1 Claude Desktop

将 `onenote` 服务对象合并到 Claude Desktop 的本地 MCP 配置 `mcpServers` 中，保存后完全退出并重启 Claude Desktop。在连接器/开发者设置中确认 OneNote MCP Server 已连接并展示工具列表。

Claude Code 使用 `.claude/mcp.example.json` 作为脱敏参考，并通过 `claude mcp add-json --scope local` 保存当前用户、当前项目专属的实际配置。不要把实际值放入根目录 `.mcp.json`；该文件属于可共享的 `project` scope。

### 3.2 Cursor

在 Cursor 的 MCP 设置中添加同一份 stdio 服务定义，或将其合并到 Cursor 当前使用的 MCP JSON 配置。保存后重载 Cursor 窗口，并在 MCP 工具面板确认服务可用。

### 3.3 其他本地 Agent

只要客户端支持 stdio MCP，即使用相同的 `command`、`args` 和 `env`。客户端配置格式不同的情况下，只转换外层服务注册结构，内部三个字段保持不变。

## 4. 只读预检（无需写入确认）

保持 `ONENOTE_ENABLE_WRITES=false` 和 `ONENOTE_ENABLE_DELETES=false`，依次调用：

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
- 调用 `get_notebook("<notebook.id>")` 后名称和元数据一致。

只在当前会话中使用返回的 Notebook ID；不要将它粘贴到仓库文件。

### 5.2 创建并验证 Section

```text
create_section("<上一步的 notebook.id>", "MCP Acceptance Section")
```

预期：

- 返回 `status: success`。
- 返回的 `section.id` 和 `section.name` 均非空。
- 调用 `list_sections("<notebook.id>")` 后能找到该 Section。
- 调用 `get_section("<section.id>")` 后名称和元数据一致。

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
- 调用 `get_page_metadata("<page.id>")` 后标题和元数据一致。
- 调用 `get_page_content("<page.id>")`，返回 HTML 包含 `OneNote MCP acceptance marker.`。
- 在 OneNote 网页端或客户端中确认层级为：测试 Notebook → 测试 Section → 测试 Page。

### 5.4 可选 Page 删除验收

Page 删除需要第二次明确确认。获得确认后，保持写入开启，并将：

```json
"ONENOTE_ENABLE_DELETES": "false"
```

临时改为：

```json
"ONENOTE_ENABLE_DELETES": "true"
```

重启 MCP 客户端后先调用 `get_page_metadata("<page.id>")`，确认标题仍为 `MCP Acceptance Page`，再调用：

```text
delete_page("<page.id>", "MCP Acceptance Page")
```

预期返回 `status: success`，随后 `list_pages("<section.id>")` 不再包含该 Page。若返回 `confirmation_mismatch`，立即停止，不得猜测标题或绕过确认。无论成功、失败或跳过，随后都必须把删除开关恢复为 `false`。

### 5.5 异常处理

- `conflict`：名称已存在。不要改动已有资源；使用新的时间戳重新开始。
- `rate_limited`：停止请求，等待 Microsoft Graph 要求的时间后从“列出并确认状态”开始；不要盲目重发创建请求。
- 超时或网络错误：结果可能不确定。先通过 `list_notebooks`、`list_sections`、`list_pages` 确认是否已经创建，再决定是否使用新名称重试。
- `forbidden`：停止操作，检查是否为 Delegated `Notes.ReadWrite`、是否使用了正确账号，以及租户管理员策略。
- `deletes_disabled`：停止删除，确认独立删除开关与客户端重启状态。
- `confirmation_mismatch`：停止删除，重新进行只读元数据核对；不得尝试其他删除方式。

## 6. 回滚、清理与验收记录

1. 将客户端配置立即恢复为 `ONENOTE_ENABLE_WRITES=false`、`ONENOTE_ENABLE_DELETES=false` 并重启客户端。
2. 对本章人工/分发包流程，在 OneNote/OneDrive 中手动删除本流程创建的整个 `MCP-ACCEPTANCE-...` Notebook；Notebook 和 Section 不使用 MCP 自动删除。开发仓库的 `MCP-FULL-TOOL-ACCEPTANCE-...` live test 应优先使用前述独立本地控制面清理。
3. 在 OneNote/OneDrive 回收站中确认清理策略符合账号所有者要求。
4. 调用 `list_notebooks`，确认测试 Notebook 不再出现在列表中。
5. 验收记录只保留无敏感信息的结果：日期、操作者角色、客户端、通过/失败状态、错误码与是否完成手动清理。不得保存 user code、token、实际 Client ID、邮箱或资源 ID。

建议使用以下脱敏记录模板：

```text
日期：YYYY-MM-DD
环境：本地 / 测试账号
只读预检：通过 / 未通过
写入保护：通过 / 未通过
Notebook 创建：通过 / 未通过
Section 创建：通过 / 未通过
Page 创建与回读：通过 / 未通过
Page 删除：通过 / 未通过 / 已跳过
测试上下文清理：本地控制面已完成 / 人工已完成 / 待完成
备注：仅记录错误码和处理动作
```

## 7. 退出与故障恢复

- 若需撤销本机登录状态，调用 `clear_token_cache`，然后关闭 MCP 客户端；下一次使用需要重新认证。
- 若加密缓存不可用，保持写入开关关闭并排查操作系统安全存储，不要改为明文缓存。
- 若任何步骤意外指向已有重要 Notebook，立即停止，不执行 Page 更新或任何进一步写操作，并由账号所有者检查 OneNote 回收站和版本历史。
