# Device Code Flow 的账号受众与令牌版本

## 问题

在 Claude Code 中，OneNote MCP 已经成功连接，但调用 `start_authentication` 时无法取得 `user_code` 和 `verification_uri`。绕过 MCP 的通用错误提示检查 MSAL 结果后，发现 Microsoft Entra 返回：

```text
AADSTS50059: No tenant-identifying information found
```

当尝试把 Azure APP 的 `signInAudience` 从单租户改为同时支持组织账号和个人 Microsoft 账号时，Entra 又拒绝保存，提示应用必须接受 Access Token Version 2。

最终验收环境为个人 Microsoft 账号；故障期间没有执行 OneNote 写入，也没有把 Client ID、Tenant ID、device code、token、邮箱或资源 ID 写入仓库。

## 根因

三个配置彼此不匹配：

- Azure APP 的账号受众是 `AzureADMyOrg`，即仅允许单个 Microsoft Entra 组织租户。
- 实际登录的是个人 Microsoft 账号。
- MCP 使用 `https://login.microsoftonline.com/common` 发起 Device Code Flow。

单租户应用不能为个人 Microsoft 账号完成该认证流程，因此错误发生在 `initiate_device_flow` 阶段，尚未进入用户登录、Graph 权限或 token cache 验证。

此外，允许个人 Microsoft 账号的 `AzureADandPersonalMicrosoftAccount` 受众必须使用 v2 访问令牌。原应用的 `requestedAccessTokenVersion` 为 `null` 或默认 v1，所以直接修改 `signInAudience` 会触发第二个校验错误。

`common` 本身没有被 Microsoft 废弃。它仍适用于同时支持组织账号和个人 Microsoft 账号的应用；问题是 authority、应用受众和实际账号类型没有保持一致。

## 无效处理与误判

- 清理 token cache 无法修复此问题，因为失败发生在 token 生成之前。
- 重启或重新注册 MCP 不能改变 Azure APP 的账号受众。
- 不能仅凭 `AADSTS50059` 就认定必须把 `common` 改成 Tenant ID、`organizations` 或 `consumers`；应先核对实际账号类型与 `signInAudience`。
- 不应让 Agent 通过命令行输出完整 MSAL 原始响应来长期诊断，其中可能包含 Client ID、关联 ID 或其他不应进入对话和日志的信息。

## 解决方式

在 Microsoft Entra 管理中心打开：

```text
Microsoft Entra ID → 应用注册 → 目标 APP → 清单
```

按顺序修改并分别保存：

1. 在 Microsoft Graph 格式清单的 `api` 对象中，将 `requestedAccessTokenVersion` 设置为 `2`。旧格式清单则修改已有的 `accessTokenAcceptedVersion`；不要同时新增两种字段。
2. 将 `signInAudience` 从 `AzureADMyOrg` 改为 `AzureADandPersonalMicrosoftAccount`。
3. 在“身份验证 → 高级设置”确认“启用以下移动和桌面流”为“是”。
4. 确认 Microsoft Graph 权限使用 Delegated `Notes.ReadWrite` 和 `User.Read`，且没有 Client Secret。

修改账号受众不会改变 Application Client ID，因此本地 MCP 配置无需更换 ID。完全退出并重新启动 Claude Code 后，在同一个 MCP 会话中依次执行：

1. `start_authentication`。
2. 在浏览器输入临时 user code，并使用个人 Microsoft 账号完成登录。
3. `complete_authentication`。
4. `check_authentication`，确认状态为 `authenticated` 且 `token_caching` 为 `encrypted`。
5. 保持 `ONENOTE_ENABLE_WRITES=false`，调用 `list_notebooks` 完成只读验证。

本次按上述步骤完成认证，并成功读取 OneNote Notebook 列表。

## 账号受众映射

| 实际目标账号 | `signInAudience` | authority |
| --- | --- | --- |
| 单个组织租户 | `AzureADMyOrg` | `https://login.microsoftonline.com/<tenant-id>` |
| 任意组织租户 | `AzureADMultipleOrgs` | `https://login.microsoftonline.com/organizations` |
| 组织账号和个人账号 | `AzureADandPersonalMicrosoftAccount` | `https://login.microsoftonline.com/common` |
| 仅个人 Microsoft 账号 | `PersonalMicrosoftAccount` | `https://login.microsoftonline.com/consumers` |

## 预防措施

- 创建 Azure APP 时先确定实际 OneNote 账号类型，再选择“支持的帐户类型”，不要默认选择单租户。
- 验收前同时检查 `signInAudience`、v2 访问令牌、Public Client Flow 和 Delegated Graph 权限。
- Application Client ID 可保存在 Claude Code `local` scope、被忽略的 `.codex/config.toml` 等本机实际配置中，但不得出现在根目录共享 `.mcp.json`、示例、提交、截图、Issue、日志或 Agent 输出中。
- Client Secret、token、refresh token、邮箱和平台加密 token cache 始终按敏感认证材料管理；实际本机配置必须由客户端私有 scope 或 `.gitignore` 隔离。
- 诊断顺序固定为：MCP 连接状态 → Client ID 是否加载 → APP 账号受众 → authority → Public Client Flow → Graph 权限 → token cache。
- 后续应为认证失败增加脱敏错误分类，例如把 MSAL 的租户配置错误映射为 `tenant_configuration_error`，保留安全错误码而不传播原始响应正文。
- 后续应评估通过环境变量安全选择 `common`、`organizations`、`consumers` 或特定 Tenant ID，避免把租户配置硬编码进源码。

## 参考

- [Microsoft Entra：修改应用程序支持的帐户类型](https://learn.microsoft.com/zh-cn/entra/identity-platform/howto-modify-supported-accounts)
- [Microsoft Entra：Microsoft Graph 格式应用清单](https://learn.microsoft.com/zh-cn/entra/identity-platform/reference-microsoft-graph-app-manifest)
- [Microsoft Entra：身份验证和授权错误代码](https://learn.microsoft.com/zh-cn/entra/identity-platform/reference-error-codes)
