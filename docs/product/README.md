# 产品信息

## 产品定位

OneNote MCP Server 是一个在本机运行的 FastMCP 服务。它通过 Microsoft Graph 和 Device Code Flow，让 MCP 客户端以受控方式读取并管理当前登录用户的 OneNote 内容。

产品服务于希望让 Agent 或自动化工作流安全使用个人 OneNote 的开发者与知识工作者。它优先保证最小权限、明确确认和可验证的操作边界，而不是提供任意 Microsoft Graph 或 OneDrive 访问能力。

## 当前范围

| 维度 | 当前产品承诺 |
| --- | --- |
| 数据范围 | 仅当前登录用户的 `/me/onenote/`；不提供 Group、Site、Drive 或通用 Graph 数据面。 |
| 认证 | Public Client + Device Code Flow；令牌缓存只使用平台加密存储，无法加密时只保留会话内缓存。 |
| 读取 | 可列出和获取 Notebook、Notebook 下的 Section、Section 下的 Page 元数据，以及显式读取 Page HTML。 |
| 创建 | 可创建 Notebook、Notebook 下的 Section 和 Section 下的 Page；默认关闭，需显式启用写入开关。 |
| 更新 | 当前只提供受限的 Page 内容追加；完整的 Page 内容变更和 Page 重命名仍在设计中。 |
| 删除 | 仅支持 Page 删除，且需要独立删除开关、标题确认和删除前回读；不提供 Notebook、Section 或 SectionGroup 删除。 |

## 产品原则与边界

- 默认只读。`ONENOTE_ENABLE_WRITES=false` 和 `ONENOTE_ENABLE_DELETES=false` 是默认安全状态。
- 不请求生产 `Files.ReadWrite` 权限，也不通过 Drive 模拟 Notebook 或 Section 删除、移动或重命名。
- 不暴露任意 Graph URL、原始 OData 表达式或通用 Graph 调用；公开工具只接收经过校验的资源 ID 和结构化参数。
- 不返回或记录身份字段、认证材料、原始 Graph 响应、Page 正文或其他敏感内容。
- Page 正文 Search 尚未交付。未来首期仅考虑 Section 或 SectionGroup 范围，并在读取正文前受候选 Page 数硬限制；完整约束见对象模型设计。

## 能力状态的权威来源

产品信息只描述当前交付状态。对象层级的 Graph 支持、MCP 实现状态和待实现工作，以 [OneNote 对象模型总览](../design/onenote_object_model/00_overview.md) 为准；活动探索以 [TODO 索引](../todos/README.md) 为准。

安装、环境变量、认证步骤和用户验收见根目录 [README](../../README.md) 与 [验收指南](../acceptance_guide_zh.md)。

## 调研报告

- [Merge Agent Handler OneNote 工具调研](merge_onenote_agent_handler.md)：按 Notebook、SectionGroup、Section、Page 层级对照 Merge 公开工具目录与本项目对象模型；记录调研范围、证据和不可直接迁移的安全边界。
- [本地 OneNote COM MCP 调研与 Graph 路线互补评估](local_onenote_com_mcp_research.md)：对照两个 Windows COM MCP，重点评估本地正文搜索、复制、移动、排序、层级写入和删除对 Graph 缺口的补充价值。
