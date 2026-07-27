# OneNote MCP 开发守则

## 代码与目录

- 使用 Python 3.10+、类型标注和 `async` HTTP 调用；业务逻辑放在 `onenote_mcp/`，根脚本仅用于兼容启动。
- Graph API 调用必须通过统一客户端，禁止在工具函数中直接拼接 Bearer token 或泄露响应正文。
- 保持 MCP 工具名稳定；接口破坏性变更必须在 README 和设计文档中说明。

## 认证与安全

- 只使用 Public Client + Device Code Flow。Application Client ID 是公开配置标识，可保存在被 Git 忽略的本机实际配置（如 `.codex/config.toml` 或 Claude Code `local` scope）中，但不得出现在示例、提交、截图、Issue、日志或 Agent 输出中。
- 禁止读取、要求、保存或记录 `AZURE_CLIENT_SECRET`、token、refresh token 或邮箱；自动迁移 Client ID 时只能在本机配置之间传递并全程避免打印其值。
- 持久化令牌必须通过 `msal-extensions` 平台加密缓存；无法加密时仅允许会话内缓存，禁止明文降级。
- 写入工具默认关闭，只有 `ONENOTE_ENABLE_WRITES=true` 才可调用 Graph 写端点。
- 删除工具必须额外要求 `ONENOTE_ENABLE_DELETES=true`，并在删除前校验调用者提供的资源确认信息；普通写入开关不得隐式授权删除。
- 日志与 MCP 错误不得包含 Graph 原始响应体、认证材料或账号资料。

## 变更、测试与验收

- 每项功能变更都要有 Mock 单元测试；真实账号验证须在用户明确确认后进行。
- Claude CLI 全工具验收必须通过 `tests/test_agent_acceptance_live.py`；禁止临时拼接 Agent Prompt 绕过 pytest case。每个 Agent 子进程前必须完成本机配置、长期双开关、非 live Mock 测试、工具注册表、认证缓存、Graph 只读访问和阶段临时配置检查。
- 同名资源检查、资源状态核验、Page 删除、Notebook 测试上下文清理和保护开关验证由本地 pytest 控制面直接执行，不得交给外部 Agent、被调用的 Agent 或其子进程决定和执行。
- 生产 `SCOPES`、MCP Server、Claude/Codex 配置和 Agent 临时 MCP 配置严禁请求或注入 `Files.ReadWrite`；即使 Azure App Registration 已授予该权限，普通 MCP 进程也只能请求 OneNote 所需的 scope，且生产 Graph 客户端必须保持 `/me/onenote/` endpoint allowlist。不得新增 Drive MCP 工具、通用 Graph 工具或向 Agent 暴露 DriveItem 数据。
- `Files.ReadWrite` 仅允许由 `tests/test_agent_acceptance_live.py` 的本地控制平面临时请求。经账号所有者明确授权，控制平面可复用生产 MCP 的平台加密 MSAL cache 和账号会话以减少重复认证；生产 MCP 自身仍只能请求生产 `SCOPES`，并受 `/me/onenote/` endpoint allowlist 限制。严禁把 cache、access token、DriveItem ID/eTag、搜索结果或删除响应发送给 Provider、Agent、被调用的 Agent、日志或测试报告；严禁使用 `Files.ReadWrite.All`。
- 每次使用本地 Drive 清理都必须由账号所有者显式设置 `ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1`。目标必须同时满足保留的 `MCP-FULL-TOOL-ACCEPTANCE-` 前缀、搜索精确名称、唯一非远程 `package.type=oneNote`，再按候选 ID 精确回读并复核名称、类型、ID 与 eTag，最后使用 `If-Match`；分页、重复、类型不符、OneNote/Drive 视图不一致或身份字段缺失时必须 fail closed，不得让 Agent 选择候选。
- Drive 清理只用于 live test 启动前清除精确同名遗留上下文，以及结束后的同一测试 Notebook 回收；删除是移入 OneDrive 回收站而非永久擦除。失败时只报告脱敏错误码和人工清理所需的唯一测试名称，不得扩大搜索或删除范围。
- 测试期结束后，可由账号所有者从 Azure App 移除或撤销 delegated `Files.ReadWrite`。因为 cache 与生产 MCP 共享，禁止由清理流程自动删除 cache；若要求立即清除全部本地认证状态，必须另行明确授权并接受 OneNote MCP 也需要重新认证。
- 将 MCP 原始工具结果发送给外部 Provider、创建/更新隔离 Notebook、本地 Drive 清理和删除测试 Page 必须分别取得显式授权；Agent trace 只允许在进程内存中核验，不得持久化或原样输出。
- 真实写入只允许针对唯一命名的测试 Notebook，记录的资源 ID 不得写入仓库或日志。测试完成后恢复写入开关为 `false`。
- 自动清理不属于 MCP 的产品能力；分发包和非 live 流程仍必须给出 OneNote/OneDrive 手动清理步骤。
- 不使用 `git reset --hard` 或覆盖用户既有改动；小而可审查的提交优先。

## 使用第三方 Agent 验收认证 MCP

- 第三方 Agent 只承担 MCP 数据面动作；认证 bootstrap、scope 提升、目标选择、同名清理、最终状态核验和权限恢复属于本地 pytest 控制面。不得用长 Prompt 把完整控制权交给 Agent。
- 相同 Client ID、配置文件和 token cache 不代表新增 scope 已可用。先分别验证生产 scope 与测试控制 scope；静默取 token 返回 `invalid_grant` 时，按 MSAL 规则执行一次本地交互认证，不得让 Agent 处理 Device Code 或看到认证材料。
- live 流程必须拆为单一资源层级或单一 mutation 的短阶段；每个阶段使用独立、非持久 Agent 调用和最小工具白名单。阶段间需要等待最终一致性时，由本地代码执行有界只读回查，不让 Agent 盲目重试写入。
- Claude `stream-json` 必须边读边保留在内存供最终覆盖验证；终端只允许实时显示阶段、已注册工具名和白名单内的固定结果码。Tool result、输入参数、资源 ID、HTML、stderr 和认证信息不得实时打印或持久化。
- 成功不能只看 Agent 自述，必须从 trace 证明 required tool calls 全部发生，再由本地代码验证真实资源状态。失败使用 `PHASE_RESULT=<phase>:FAIL:<safe_code>`；未列入白名单的原因码不得原样输出。
- 认证 MCP 的 Agent 验收设计与排障清单见 `docs/lessons/authenticated_mcp_agent_acceptance.md`；修改 harness 时必须同步其 Mock 测试、README 和 Agent Prompt。

## Git 远程与个人更新

- 本地仓库只保留一个 remote：`origin`，仓库身份固定为 GitHub 上的 `Kaomsos/onenote-mcp-server`，同时用于 fetch 和 push。传输方式服从当前机器的凭据配置，可使用 HTTPS 或 SSH，不得把 URL 写死为某一种协议。
- 不添加、恢复或引用原始项目的上游 remote，不维护 `fork` remote，也不设计双远程同步流程。需要研究外部实现时使用浏览器或被 `.gitignore` 忽略的参考目录，不改变主仓库 remote。
- 更新个人代码前先检查工作树、运行相关测试并创建本地提交；使用 `git push origin main:main` 推送。
- Agent 操作 Git 前必须先运行 `git remote -v`；如果存在 `origin` 之外的 remote，或将 HTTPS/SSH URL 规范化后 `origin` 不指向上述个人仓库，应停止推送并先按本节恢复单一 origin。不得仅因另一台机器使用不同协议而改写其有效 remote。

## 自我迭代与参考项目

- 每解决一个 non-trivial 问题，在 `docs/lessons/` 按主题记录问题、根因、方案与预防措施；必要时同步本文件。
- Git 单一远程的原因和维护规则记录在 `docs/lessons/single_origin_remote.md`。
- 参考对标项目固定为 [ZubeidHendricks/azure-onenote-mcp-server](https://github.com/ZubeidHendricks/azure-onenote-mcp-server)。它用于逆向分析创建 Notebook、Section 等 Graph 调用；其 Client Secret 认证方式不得迁入主项目。
- 初始化或更新参考目录时，在主项目根目录执行：`git clone https://github.com/ZubeidHendricks/azure-onenote-mcp-server.git`。若目录已存在，使用该目录自身的 Git 状态与提交记录进行分析，不重复 clone 或覆盖其中内容。
- clone 目标必须是主项目根目录下的 `azure-onenote-mcp-server/`，并由 `.gitignore` 忽略。可在设计文档记录参考 commit 与 API 行为，但不得复制、导入、暂存或提交其代码。
