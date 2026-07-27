# 使用第三方 Agent 验收需要认证的 MCP

## 问题

需要真实账号认证的 MCP 不能只靠 Mock 测试，也不能简单地把“把全部工具跑一遍”交给第三方 Agent。实践中会同时遇到四类风险：

- Agent 能调用工具，不代表它理解认证、scope、token cache 与用户同意之间的差异。
- 一个长 Prompt 容易让 Agent 提前结束、跳过工具、重复写入，或者把失败原因压缩成没有诊断价值的笼统结论。
- MCP Tool result 可能包含资源 ID、正文或账号上下文；直接转发完整实时输出会把调试变成新的泄露通道。
- 创建、更新和清理具有真实副作用。目标选择、删除确认与回滚不能依赖概率性的模型行为。

本项目最终把真实验收实现为 pytest 编排的本地控制面，加上多个只处理数据面的短 Agent 调用。这个结构比某个 Provider 或某个具体 MCP 更通用。

## 核心模型：三个边界

### 1. 认证边界

App Registration 中登记 delegated permission，只表示应用可以请求该权限，不会自动修改已有 access token。相同 Client ID、authority、配置和 cache，也不意味着新 scope 已经出现在可用 token 中。

本次经验是：

1. 生产 `AuthManager` 只请求产品所需 scope。
2. 测试控制面可以在账号所有者明确授权后复用同一平台加密 MSAL cache，但必须显式请求测试 scope。
3. 分别验证生产 session 和控制 session。生产 session 为真、控制 session 为假，是 scope 不匹配或静默续期失败，不是配置路径必然不同。
4. `acquire_token_silent` 无法取得扩大 scope 的 token，或者返回 `invalid_grant` 时，需要一次本地交互认证。Device Code、token 和账号信息不得交给 Agent。
5. cache 共享不等于权限共享：生产 MCP 仍必须维持固定 scope、固定工具注册表和 endpoint allowlist。

不要把 `has_valid_session()` 理解为“用户是否登录”。它实际回答的是“当前 AuthManager 能否为它请求的完整 scopes 取得 access token”。诊断时只输出布尔状态、cache 类型和安全错误码，不输出 token、账号或 Client ID。

## 2. 控制面与数据面边界

第三方 Agent 适合验证它是否能按 MCP 协议发现和调用业务工具，不适合拥有测试环境的最终控制权。

本地 pytest 控制面负责：

- 读取被忽略的本机配置并进行权限检查。
- 验证长期写入/删除开关保持关闭。
- 验证工具注册表和 destructive annotations。
- 准备唯一测试名称、检查或清理精确同名上下文。
- 执行需要额外 scope 的管理操作。
- 在 Agent 后独立回读并验证真实状态。
- 在成功、失败、超时和中止路径中执行 finally 清理。

Agent 数据面只负责：

- 使用当前阶段白名单内的 MCP 工具。
- 操作 pytest 指定的唯一隔离资源。
- 不修改本机配置，不处理认证材料，不决定清理目标。
- 用固定协议返回成功或安全失败原因。

涉及删除时，不能因为搜索精确命中就直接删除。本项目的 Drive 清理先验证保留前缀、精确名称、唯一非远程 OneNote package，再按候选 ID 精确 GET，复核名称、类型、ID 与 eTag，最后携带 `If-Match` 删除。搜索结果不含 eTag 时应补一次精确读取，而不是放宽确认。

## 3. Provider 可见性边界

“最终回答不打印敏感数据”不能代替 Provider 数据传输授权。Agent 调用 MCP 时，Provider 通常已经能看到 Tool result，因此真实验收必须单独取得以下授权：

- 将 MCP 结果发送给 Provider。
- 创建或更新隔离测试资源。
- 本地管理控制面的清理操作。
- 可选的破坏性业务工具测试。

这些授权应使用独立开关，不能用一个笼统的 `LIVE=true` 同时代表所有权限。

## 避免 Agent 黑箱

### 实时读取，但只显示脱敏事件

使用 Claude `stream-json` 时，不要调用一个完全 `capture_output=True`、直到结束才返回的黑箱 runner。可使用并发管道读取：

1. stdout 逐行解析 JSON，stderr 同时排空，避免任一 pipe 填满导致死锁。
2. 完整 stdout/stderr 只保存在进程内存，供结束后的 trace 验证。
3. 实时终端只显示固定格式事件：

```text
AGENT_PHASE_START=section
AGENT_TOOL_CALL=list_sections
AGENT_TOOL_CALL=create_section
AGENT_RESULT=section:FAIL:target_not_visible
AGENT_PHASE_FAIL=section:agent_section_reported_target_not_visible
```

4. 不实时显示 Tool input/result、资源名称、ID、HTML、stderr 或模型自由文本。
5. 工具名必须来自已知注册表；结果 phase、status 和 code 必须经过白名单验证。模型生成的未知原因码只显示为 `failure_code_invalid`。

这样既保留最终一次性覆盖校验，也能在运行中知道 Agent 卡在认证、列表、创建还是精确回读。

### 不相信 Agent 自述成功

每个阶段同时验证两类证据：

- 行为证据：`stream-json` 中确实出现 required `tool_use`。
- 状态证据：Agent 后由本地 Graph/工具代码回读唯一资源和内容标记。

只有两者都满足才算通过。Agent 输出 `PASS` 但缺少必需工具调用，仍必须失败。

### 使用安全失败协议

Agent 失败时不应只输出 `FAIL`，也不能自由复述 Graph 响应。使用固定协议：

```text
PHASE_RESULT=<phase>:FAIL:<safe_code>
```

本项目允许的原因码只描述失败类别，例如：

- `authentication_required`
- `target_exists`
- `target_missing`
- `target_not_visible`
- `write_rejected`
- `content_mismatch`
- `tool_error`
- `unexpected_result`

原因码不能包含资源名称、ID、账号信息或服务端正文。pytest 应优先报告合法的 Agent 原因码；非法原因码统一映射为固定错误，不原样输出。

## 拆分长程 Agent 任务

一次 Agent 调用同时承担十几个工具时，常见现象包括：创建 Notebook 后提前结束、创建 Section 后跳过 `get_section`、读取页面后漏掉更新。即使工具和 API 正常，这种编排仍具有模型随机性。

拆分原则：

- 一个阶段只覆盖一个资源层级或一个 mutation。
- 一个创建阶段最多暴露一个创建工具。
- 创建阶段不拥有后续更新或删除工具。
- 每个阶段使用独立非持久会话和独立临时 MCP 配置。
- 每个阶段开始前重新验证配置、认证、注册表和 allowlist。
- 阶段通过精确名称重新定位资源，不依赖跨 Agent 会话记忆。
- 写请求超时或 Graph 尚不可见时，先进行有界只读回查；不要自动重发 mutation。

本项目最终采用：guard、Notebook、Section、Page、内容更新五个阶段。若某一层仍受到最终一致性影响，可继续拆为“创建”和“延迟只读核验”，并由本地控制面负责等待条件，而不是增加 Prompt 长度。

## 推荐的测试分层

1. 纯 Mock：端点、字段映射、scope、endpoint allowlist、拒绝路径、实时脱敏 parser。
2. 本机前置检查：依赖、锁文件、私有配置权限、长期开关、工具注册表、MCP 连接。
3. 无 Agent live：生产认证、测试 scope、Graph 只读、上下文清理 helper。
4. Agent 分阶段 live：最小工具白名单、实时脱敏进度、内存 trace 覆盖验证。
5. 本地后置验证：真实资源层级、内容 marker、安全开关和 finally 清理。

live test 必须默认 skip，并要求数据传输、写入、管理清理和可选删除分别显式 opt-in。

## 排障顺序

遇到失败时按以下顺序定位，避免直接扩大权限或重跑写入：

1. 认证：cache 是否存在且加密；生产 scope 与测试 scope 分别是否可取 token。
2. 配置：Client ID 来源是否一致；长期写入/删除开关是否关闭。
3. MCP：连接是否成功；工具注册表和 annotations 是否完全匹配。
4. Agent：从实时工具序列确定最后一个已调用工具；检查安全失败码。
5. 状态：由本地控制面按精确名称回读，判断是 Agent 漏调用还是 Graph 最终一致性。
6. 清理：finally 优先处理唯一隔离上下文；任何歧义都 fail closed 并转人工。

## 预防清单

- 新工具同步更新注册表、阶段 allowlist、Prompt、required calls 和 Mock。
- 不把 Client Secret、token、原始 trace 或 Graph response 写入日志。
- 不允许 Agent、子 Agent 或 Provider 持有管理 scope 的调用入口。
- 不因测试方便添加通用 Graph 工具。
- 不用 Agent 最终自然语言代替 tool trace 与本地状态验证。
- 不把多个写操作塞入一次长程 Agent 调用。
- 不在失败后盲目重跑；先只读确认是否已产生副作用。
- 不因搜索结果字段缺失而降低删除确认标准；增加精确读取补足证据。
