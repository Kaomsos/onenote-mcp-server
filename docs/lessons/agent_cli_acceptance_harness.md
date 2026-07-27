# Agent CLI 验收不应依赖临时人工编排

需要把本方案迁移到其他带认证 MCP 时，先阅读更通用的 [使用第三方 Agent 验收需要认证的 MCP](authenticated_mcp_agent_acceptance.md)。

## 问题

全工具真实账号验收过去主要依赖把长 Prompt 交给某次 Agent 会话。每次执行都需要重新选择工具、确认阶段、处理安全开关和整理结果，容易出现前置条件尚未满足就启动 Agent、权限范围过大、模型只报告成功却没有覆盖规定工具、或把原始 MCP 结果写进终端和会话记录的问题。

## 根因

- Prompt 描述了流程，但没有代码级的执行顺序和 fail-closed 门禁。
- Claude Provider 可看到 MCP 原始 Tool 结果；仅要求 Agent 在最终回答中脱敏，不能代替数据传输授权。
- 长期 MCP 配置与测试阶段开关耦合，人工修改后可能忘记恢复。
- 只检查 Agent 最终文字，无法证明它确实调用了所有规定工具。

## 解决方式

使用显式 opt-in 的 `tests/test_agent_acceptance_live.py`，不再维护独立运行脚本：

1. 在任何 Agent 进程前检查 Python、`uv`、Claude CLI、锁文件、全部非 live Mock 测试、MCP 连接、16 工具注册表、删除 annotations、加密认证缓存和 Graph 只读访问。
2. 要求长期 `.codex/config.toml` 权限受限，且写入、删除开关始终为 `false`；Client ID 只在进程内部读取，不打印或进入命令行。
3. 本地 Graph 控制面先检查精确测试 Notebook 名称；若存在遗留上下文，只能由独立的 Drive 控制面按严格条件清理，不让 Agent 处理清理、查看候选或决定目标。
4. 为 guard、Notebook、Section、Page、内容更新五个 Agent 阶段分别生成权限为 `0600` 的临时严格 MCP 配置，退出后自动删除。每个创建阶段只拥有当前层级的一个创建工具，避免单轮工具链过长时 Agent 提前结束；每个 Claude 子进程使用非持久会话、禁用内置工具并只允许该阶段所需的 OneNote MCP 工具。
5. 并发读取 Claude stdout/stderr，把完整 `stream-json` 保留在内存用于最终 `tool_use` 覆盖和固定结果标记校验；运行中只实时打印阶段、OneNote 工具名和固定结果，不输出 Tool result、ID、HTML、stderr 或认证内容。
6. Agent 完成后，由本地 Graph 直接确认唯一 Notebook、Section、Page 和内容标记。若单独设置 Page 删除授权，则由 pytest 进程直接调用受双开关及标题确认保护的 `delete_page`，不把资源 ID 或删除响应发送给 Provider。
7. Provider 数据传输、隔离 Notebook 写入、本地 Drive 清理和本地 Page 删除分别使用显式环境授权。
8. 普通 Notebook/Section 没有受支持的 OneNote Graph v1.0 删除接口；官方只提供 [Page 删除](https://learn.microsoft.com/en-us/graph/api/page-delete?view=graph-rest-1.0)。测试代码因此把 OneDrive [`driveItem` 删除](https://learn.microsoft.com/en-us/graph/api/driveitem-delete?view=graph-rest-1.0)限制为本地控制面能力：控制面可复用现有平台加密 cache，但只有它临时请求 `Files.ReadWrite`，该 scope 绝不进入生产或 Agent MCP 请求。
9. Drive 控制面只接受保留前缀、精确名称和唯一非远程 [`package.type=oneNote`](https://learn.microsoft.com/en-us/graph/api/resources/package?view=graph-rest-1.0)，再按候选 ID 精确回读并复核名称、类型、ID 与 eTag；删除携带 `If-Match` 并移入回收站。搜索结果可能不返回 eTag，禁止因此放宽确认；任何分页、歧义、详情不一致或字段缺失都会中止并退回人工清理。

## 预防措施

- 新工具必须同步更新 `EXPECTED_TOOLS`、阶段白名单、Agent Prompt 和 Mock 测试；注册表不完全一致时禁止启动 Agent。
- 任何新增 Agent 阶段都必须从 `execute_agent_phase` 进入，确保前置检查先于子进程调用。
- 涉及目标选择、同名清理、资源删除或权限恢复的控制面逻辑优先放入本地 pytest fixture/helper，不授权第三方 Agent 自主执行。
- 生产 `SCOPES`、Claude/Codex MCP 与 Agent 临时配置不得包含 Files scope；不得新增 Drive MCP 工具或通用 Graph 入口，也不得使用 `Files.ReadWrite.All`。
- Files 控制面可复用 MCP 的平台加密 cache，但必须要求 `ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1`；生产 AuthManager 仍只请求生产 scope。不得把 cache、token、Drive 搜索结果、ID/eTag 或删除响应交给 Agent、被调用的 Agent 或 Provider，也不得由验收代码自动删除共享 cache。
- 不把 Client ID、Tool trace、资源 ID 或 Claude 原始错误写入测试报告、异常文本或持久会话。
- Agent 最终结果必须使用固定 PASS 或白名单 FAIL 原因码；未知原因码不得原样打印。工具覆盖仍以 `stream-json` 的真实 `tool_use` 为准，不能由 Agent 自述代替。
- 测试开关只存在于临时配置；长期配置一旦不是 `false/false`，整个流程立即中止。
