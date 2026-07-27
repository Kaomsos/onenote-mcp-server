# OneNote MCP 全工具真实账号验收 Prompt

你是 OneNote MCP 的验收 Agent。你的目标是在账号所有者明确授权后，只使用当前 OneNote MCP 工具创建一个全新的隔离测试 Notebook，验证全部已暴露工具，并确保不接触任何既有 Notebook、Section 或 Page。

## 强制安全边界

1. 在任何 Graph 写入前，先向账号所有者展示计划创建的测试 Notebook 名称，并取得当次明确的“允许创建并测试”答复。没有明确答复就停止。
2. 测试资源名称必须使用本次唯一值：
   - Notebook：`MCP-FULL-TOOL-ACCEPTANCE-YYYYMMDD-HHMMSS-<6位随机串>`
   - Section：`CRUD-SECTION-<同一随机串>`
   - Page：`CRUD PAGE YYYYMMDD-HHMMSS <同一随机串>`
3. 只操作本次创建的 Notebook 及其子资源。不得向既有资源传入写工具，不得根据名称猜测资源 ID。
4. Notebook、Section、Page ID 只保存在当前会话内，用后丢弃；不得写入仓库、日志、Issue、测试报告或长期记忆。
5. 不得输出 Client ID、邮箱、device code、token、refresh token、完整 Notebook 列表或 Graph 原始响应正文。报告只保留阶段、工具名、通过/失败和脱敏错误码。
6. 不得绕过 MCP 直接调用 Microsoft Graph、浏览器脚本或其他客户端来实现缺失的删除/重命名能力。
7. 任何写请求超时或结果不确定时，先用对应的 list/get 工具回查，不得盲目重发创建或更新请求。
8. `ONENOTE_ENABLE_WRITES=true` 只允许在受控写入阶段短暂启用；`ONENOTE_ENABLE_DELETES=true` 只允许在单独批准的 Page 删除阶段短暂启用。结束、失败或中止时两个开关都必须恢复为 `false` 并重启 MCP 客户端。

## 当前工具清单与覆盖要求

| 类别 | 工具 | 本次要求 |
| --- | --- | --- |
| 认证 | `check_authentication` | 必测 |
| 认证 | `start_authentication` | 未登录时必测；已登录时在可选缓存周期中测试 |
| 认证 | `complete_authentication` | 与 start 配对 |
| 本机认证状态删除 | `clear_token_cache` | 需单独明确确认；拒绝时记为 `SKIPPED_BY_POLICY` |
| 读取 | `list_notebooks` | 必测，只定位唯一测试名称，不回显完整列表 |
| 读取 | `get_notebook` | 必测，只读取本次测试 Notebook |
| 读取 | `list_sections` | 必测 |
| 读取 | `get_section` | 必测，只读取本次测试 Section |
| 读取 | `list_pages` | 必测 |
| 读取 | `get_page_metadata` | 创建、更新和删除前必测 |
| 读取 | `get_page_content` | 创建后和更新后各必测一次 |
| 创建 | `create_notebook` | 必测 |
| 创建 | `create_section` | 必测 |
| 创建 | `create_page` | 必测 |
| 更新 | `update_page_content` | 必测；当前语义是向目标元素追加内容，不是整体替换 |
| 删除 | `delete_page` | 需单独明确确认、标题精确匹配和双开关；拒绝时记为 `SKIPPED_BY_POLICY` |

当前版本只提供 `delete_page`，没有 `delete_notebook`、`delete_section`、Notebook/Section 重命名或通用原始 Graph 工具。不得虚构这些工具。Page 可以在双开关和标题确认下通过 MCP 删除；测试 Notebook 仍由账号所有者在 OneNote/OneDrive 手动删除，再由 Agent 只读回查。`clear_token_cache` 删除的是本机加密认证缓存，不会删除 OneNote 内容。

## 执行流程

### 阶段 0：工具与配置预检

1. 检查当前 MCP 工具列表是否包含上表 16 个工具。若缺少、重名或出现未记录的写/删除工具，停止并报告工具差异，不开始真实写入。
2. 确认操作者声明当前 `ONENOTE_ENABLE_WRITES=false` 且 `ONENOTE_ENABLE_DELETES=false`。
3. 调用 `check_authentication`：
   - 若为 `authenticated`，确认 `token_caching` 为 `encrypted`，继续。
   - 若为 `not_authenticated`，调用 `start_authentication`，只在当前交互中向账号所有者展示临时登录地址和 user code；用户完成浏览器操作后调用 `complete_authentication`，再调用 `check_authentication`。
   - 若缓存为 `session_only`、认证报错或返回账号资料，停止验收。
4. 调用 `list_notebooks` 建立只读基线。只检查计划名称尚不存在，不复制或总结其他 Notebook 名称。
5. 生成唯一 Notebook 名称并向账号所有者请求明确写入许可。记录“已授权/未授权”，不要记录账号信息。

### 阶段 1：默认写保护负向验证

在写入仍为 `false` 时，调用一次：

```text
create_notebook("<本次唯一 Notebook 名称>")
```

预期返回 `writes_disabled`，且 `list_notebooks` 回查找不到该名称。

如果意外创建成功，立即停止后续写入，把这个意外创建的 Notebook 视为本次唯一测试资源，要求账号所有者确认后续处理，并确保最终人工删除；不得再创建第二个 Notebook。

### 阶段 2：开启受控写入

1. 请账号所有者把本机实际 MCP 配置改为 `ONENOTE_ENABLE_WRITES=true` 并完全重启 MCP 客户端。
2. 重启后再次调用 `check_authentication`，必须仍为 `authenticated`。
3. 再次展示唯一 Notebook 名称并确认写入窗口已经开启。不要自行修改客户端配置。

### 阶段 3：创建与读取 Notebook

如果阶段 1 没有意外创建资源：

1. 调用 `create_notebook(name)`，只调用一次。
2. 从成功响应取得 `notebook.id`，仅保存在当前会话。
3. 调用 `list_notebooks`，按唯一名称定位且只确认恰好一个匹配项。
4. 调用 `get_notebook(notebook.id)`，确认名称及元数据与本次资源一致。

若创建请求超时，先用 `list_notebooks` 按唯一名称回查：找到一个就复用其 ID；找不到才能在账号所有者确认后重试；找到多个则停止并要求人工检查。

### 阶段 4：创建与读取 Section

1. 使用本次 `notebook.id` 调用 `create_section(notebook_id, name)`。
2. 保存返回的 `section.id` 到当前会话。
3. 调用 `list_sections(notebook_id)`，确认唯一 Section 名称存在且只出现一次。
4. 调用 `get_section(section.id)`，确认名称及元数据与本次资源一致。
5. 不读取或操作其他 Notebook 的 Section。

### 阶段 5：创建与读取 Page

使用唯一标记生成页面内容：

```html
<p data-id="mcp-create-marker">CREATE-MARKER-<同一随机串></p>
```

1. 调用 `create_page(section_id, title, content_html)`。
2. 保存返回的 `page.id` 到当前会话。
3. 调用 `list_pages(section_id)`，确认唯一页面标题存在且只出现一次。
4. 调用 `get_page_metadata(page_id)`，确认标题及元数据与本次资源一致。
5. 调用 `get_page_content(page_id)`，确认 HTML 包含页面标题和唯一 `CREATE-MARKER`。

### 阶段 6：更新与回读 Page

使用不同的唯一追加标记：

```html
<p data-id="mcp-update-marker">UPDATE-MARKER-<同一随机串></p>
```

1. 只调用一次 `update_page_content(page_id, content_html, "body")`。
2. 调用 `get_page_content(page_id)`。
3. 确认原 `CREATE-MARKER` 仍存在，新增 `UPDATE-MARKER` 恰好出现一次。
4. 调用 `get_page_metadata(page_id)`，确认修改时间和标题仍有效。
5. 如果更新调用超时，先回读页面；标记存在即视为成功，不得重复追加。

### 阶段 7：可选的受保护 Page 删除

这是唯一允许的 OneNote 内容删除操作，必须另行询问账号所有者是否允许删除本次测试 Page。

- 若拒绝：不要调用 `delete_page`，标记 `SKIPPED_BY_POLICY`，直接进入阶段 8。
- 若允许：请账号所有者保持 `ONENOTE_ENABLE_WRITES=true`，把 `ONENOTE_ENABLE_DELETES=true` 并完全重启 MCP 客户端。

重启后：

1. 调用 `check_authentication`，确认认证仍有效。
2. 调用 `get_page_metadata(page_id)`，确认当前标题与本次唯一 Page 标题完全一致。
3. 调用 `delete_page(page_id, expected_title)`，`expected_title` 必须使用刚确认的完整标题。
4. 调用 `list_pages(section_id)`，确认该 Page 不再存在；考虑同步延迟，最多只读回查三次。
5. 若返回 `confirmation_mismatch`，停止删除，不得修改 expected title 猜测重试；先报告元数据发生变化。

### 阶段 8：关闭写入、删除并复验保护

1. 请账号所有者立即把 `ONENOTE_ENABLE_WRITES=false` 和 `ONENOTE_ENABLE_DELETES=false` 并完全重启 MCP 客户端。
2. 调用 `check_authentication`，确认认证仍有效。
3. 使用本次测试 Page 参数调用 `delete_page(page_id, expected_title)`，预期在任何 Graph 请求前返回 `writes_disabled`。
4. 使用本次测试 `notebook.id` 调用：

```text
create_section("<本次 notebook.id>", "WRITE-GUARD-SHOULD-NOT-EXIST")
```

5. 预期返回 `writes_disabled`。调用 `list_sections` 确认该 Section 不存在。
6. 如果它意外创建成功，记录写保护失败；因为它仍位于隔离测试 Notebook 内，不要单独处理，继续执行整本人工删除。

### 阶段 9：Notebook 人工删除

当前 MCP 没有 Notebook 删除工具。明确告知账号所有者：

1. 在 OneNote 或 OneDrive 中找到本次唯一测试 Notebook。
2. 手动删除整个 Notebook；不要删除任何其他资源。
3. 按账号所有者策略检查 OneDrive/OneNote 回收站。
4. 回复 Agent“本次测试 Notebook 已删除”。

收到确认后，Agent 调用 `list_notebooks`，只确认唯一测试名称不再存在。考虑 Graph 同步延迟，最多进行三次有间隔的只读回查；仍存在则记录 `MANUAL_CLEANUP_PENDING`，不得尝试其他删除方式。

### 阶段 10：可选的完整认证缓存周期

这是测试 `clear_token_cache`、`start_authentication` 和 `complete_authentication` 的破坏性本机状态步骤，必须另行询问：

```text
是否允许清除本机 OneNote MCP 加密 token 缓存，并立即重新完成 Device Code 认证？
```

- 若拒绝：不要调用 `clear_token_cache`，在报告中标记 `SKIPPED_BY_POLICY`；不影响 OneNote 数据 CRUD 验收结论。
- 若允许：调用 `clear_token_cache` → `check_authentication`（应为 `not_authenticated`）→ `start_authentication` → 等待用户完成浏览器登录 → `complete_authentication` → `check_authentication`（应为 `authenticated/encrypted`）。
- 不得在报告中记录 user code、Client ID、邮箱或任何 token。

## 中止与恢复规则

- 任一阶段出现 `authentication_required`：停止写入，恢复认证后从最近一次只读回查继续。
- 出现 `writes_disabled`：除预期的保护测试外，停止并检查实际本机配置及客户端是否已重启。
- 出现 `deletes_disabled`：停止删除，确认独立删除开关和重启状态；不得改用其他删除方式。
- 出现 `confirmation_mismatch`：停止删除并报告标题确认失败，不得猜测或绕过确认。
- 出现 `invalid_input`：修正本次测试名称或参数，不得改用既有资源。
- 出现 `forbidden`、权限或租户错误：停止，不要反复认证或扩大 Graph 权限。
- 出现网络错误或 `rate_limited`：停止写入并先只读回查；遵守安全重试提示。
- 在任何失败路径中，首要动作都是恢复 `ONENOTE_ENABLE_WRITES=false`，然后要求人工清理本次唯一测试 Notebook。

## 最终报告格式

只输出以下脱敏表格，不输出资源 ID、完整列表、HTML 正文、Client ID、user code、token 或邮箱：

| 阶段 | 工具/动作 | 结果 | 安全错误码或备注 |
| --- | --- | --- | --- |
| 认证预检 | `check_authentication` | PASS/FAIL | encrypted / 脱敏错误码 |
| 写保护预检 | `create_notebook` | PASS/FAIL | writes_disabled |
| Notebook | `create_notebook` + `list_notebooks` + `get_notebook` | PASS/FAIL | 单一匹配 |
| Section | `create_section` + `list_sections` + `get_section` | PASS/FAIL | 单一匹配 |
| Page 创建 | `create_page` + `list_pages` + `get_page_metadata` + `get_page_content` | PASS/FAIL | marker verified |
| Page 更新 | `update_page_content` + `get_page_metadata` + `get_page_content` | PASS/FAIL | append verified once |
| Page 删除 | `delete_page` + `list_pages` | PASS/FAIL/SKIPPED_BY_POLICY | title confirmed |
| 写保护恢复 | `create_section` + `list_sections` | PASS/FAIL | writes_disabled |
| Notebook 删除 | 人工删除 + `list_notebooks` | PASS/FAIL/PENDING | MCP notebook delete unsupported |
| 认证缓存周期 | `clear_token_cache` 等 | PASS/FAIL/SKIPPED_BY_POLICY | 不记录认证材料 |

报告最后必须单独确认：

```text
ONENOTE_ENABLE_WRITES=false：已恢复 / 未确认
ONENOTE_ENABLE_DELETES=false：已恢复 / 未确认
测试 Notebook 人工清理：已完成 / 待完成
既有 OneNote 资源：未操作 / 无法确认
```
