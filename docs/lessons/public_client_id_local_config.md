# Public Client ID 的本机配置边界

## 问题

OneNote MCP 通过 `AZURE_CLIENT_ID` 选择 Azure Public Client 应用。最初为避免任何标识进入文件，Codex 配置只使用 `env_vars = ["AZURE_CLIENT_ID"]` 转发父进程变量。终端可能通过 shell 启动脚本获得变量，但 Finder 启动的桌面应用不会读取同一套 shell 环境，导致 Codex Desktop、CLI 和 MCP 子进程得到不一致的认证入口。

Claude Code 的实际配置最初位于项目根 `.mcp.json`。该路径属于可共享、可提交的 `project` scope，不适合保存个人机器上的实际 Client ID；把文件简单移动到 `.claude/` 又不会被 Claude Code 自动当作 MCP 配置加载。

## 根因

- `env_vars` 只允许并转发父进程已经存在的变量，不负责定义变量。
- macOS GUI 应用和交互 shell 的父进程不同，环境变量继承不可作为稳定的跨客户端配置来源。
- Application Client ID 是 Public Client 的公开标识，不是 Client Secret；把它与 token、refresh token 使用完全相同的“禁止本机保存”规则，会迫使客户端依赖脆弱的进程环境。
- Claude Code 的 `.mcp.json` 是团队共享的 `project` scope，而个人项目配置应使用 `local` scope。

## 解决方式

- Codex：在被 `.gitignore` 排除的 `.codex/config.toml` 中，通过 `[mcp_servers.onenote.env]` 直接定义 `AZURE_CLIENT_ID`，并把实际文件权限设置为 `0600`。提交内容只保留 `.codex/config.example.toml` 占位符。
- Claude Code：使用 `claude mcp add-json --scope local` 保存当前用户、当前项目专属的 MCP 定义；删除根目录实际 `.mcp.json`。仓库只在 `.claude/mcp.example.json` 保存脱敏示例。
- 两个客户端都保持 `ONENOTE_CACHE_TOKENS=true` 和 `ONENOTE_ENABLE_WRITES=false`。
- 自动迁移允许在本机配置之间传递 Client ID，但不得把值打印到终端、Agent 输出或日志。

## 验证

- `claude mcp list` 应显示 OneNote 为 `Connected`。
- `codex mcp list` 应显示 OneNote 为 `enabled`，环境变量值只显示掩码。
- 项目根不存在实际 `.mcp.json`，`.codex/config.toml` 被 Git 忽略且权限为 `0600`。
- 发布 ZIP 只包含 `.claude/mcp.example.json` 和 `.codex/config.example.toml`，凭据模式扫描必须通过。

## 预防措施

- 区分公开应用标识和真正的认证材料：Client ID 可以进入被忽略的本机实际配置；Client Secret、token、refresh token 和邮箱始终禁止保存或记录。
- 不依赖 GUI 应用继承 shell 环境来提供 MCP 必需配置。
- 不把 Claude Code `local` scope 与根目录 `project` scope 混用。
- 示例文件只使用明确占位符；实际配置变更后同时检查 Git 忽略规则、客户端健康状态和发布包内容。
