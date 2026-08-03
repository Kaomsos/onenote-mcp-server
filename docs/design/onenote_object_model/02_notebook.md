# Notebook 字段与操作模型

## Graph 能力边界

Notebook 可读取、创建、列出子 Section/SectionGroup 和异步复制。稳定 Graph v1.0 没有 Notebook PATCH 或 OneNote DELETE。

创建接口：`POST /me/onenote/notebooks`，请求体只提供 `displayName`。名称必须唯一，最长 128 字符，并遵守官方字符限制。

## 标量字段

| 项目字段 | Graph 字段 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `id` | `id` | 必读 | 不写 | `R` | Graph 生成的主键 |
| `name` | `displayName` | 必读 | 创建写 | `R/C` | 创建后没有稳定更新方法 |
| `created` | `createdDateTime` | 必读 | 不写 | `R` | 只读 UTC 时间 |
| `modified` | `lastModifiedDateTime` | 必读 | 不写 | `R` | 只读 UTC 时间 |
| `is_default` | `isDefault` | 建议读取 | 不写 | `R` | 默认 Notebook 标记 |
| `is_shared` | `isShared` | 建议读取 | 不写 | `R` | 共享状态 |
| `user_role` | `userRole` | 建议读取 | 不写 | `R` | `Owner/Contributor/Reader/None` |
| `web_url` | `links.oneNoteWebUrl.href` | 选读 | 不写 | `R` | 仅用于用户导航 |
| `client_url` | `links.oneNoteClientUrl.href` | 选读 | 不写 | `R` | 仅用于用户导航 |
| `sections_url` | `sectionsUrl` | 内部/兼容 | 不写 | `R` | 新接口不得依赖 |
| `section_groups_url` | `sectionGroupsUrl` | 内部 | 不写 | `R` | 新接口不得依赖 |
| `self_url` | `self` | 不读取 | 不写 | `R` | 不向 MCP 暴露 |
| `created_by` | `createdBy` | 不读取 | 不写 | `R` | 排除身份信息 |
| `last_modified_by` | `lastModifiedBy` | 不读取 | 不写 | `R` | 排除身份信息 |

## 关系字段

| 项目关系 | Graph 关系 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `sections` | `sections` | 必读 | 聚合写 | `R/A` | 可 List/Create，不能整体 PATCH |
| `section_groups` | `sectionGroups` | 树查询必读 | 当前 MCP 不写 | `R/A` | Graph 可 List/Create |
| `parent` | 无 | 无 | 无 | `X` | Notebook 是本项目树根 |

Notebook 聚合更新可通过子资源调用增加 Section 或 SectionGroup，并继续改变其 Page；由于 Section/SectionGroup 缺少删除和原地重命名，不能称为完整聚合 Update。

## 业务操作目录

下表从业务使用角度列出 Notebook 应考虑的操作。它既包含当前能力，也保留尚未实现或平台不支持的需求；“需要”不表示可以绕过 Graph 和项目安全边界实现。

| 操作 | 业务语义 | Graph v1.0 边界 | 项目结论 |
| --- | --- | --- | --- |
| 列出 Notebook | 分页读取当前用户全部 Notebook，并可按名称、时间、默认/共享状态筛选 | 支持 List；集合可能分页 | 当前 `list_notebooks` 已实现首批读取；需统一跟随 `@odata.nextLink` 后才能称为完整列表 |
| 获取 Notebook | 以 ID 读取元数据和必要关系 | 支持 Get，可展开 `sections`、`sectionGroups` | 当前 `get_notebook` 已实现基础元数据；完整关系仍走独立集合/树查询 |
| 获取最近使用 | 返回用户最近访问的 Notebook | 支持 Get recent notebooks | 业务有价值但当前未实现；结果不能代替完整 Notebook 列表 |
| 按名称或路径定位 | 用用户可理解的名称/层级找到唯一 Notebook | 可 List 后筛选；Graph 另有基于 Web URL 的读取，但原始 URL 不应成为调用授权 | 应提供规范化查找并处理重名/零匹配；不得接收任意 Graph URL |
| 读取完整结构树 | 一次查看 Section、SectionGroup、嵌套组和 Page 摘要 | 可组合多个集合读取；Page 层级需本地推导 | 候选聚合读操作；必须分页完整、限制深度/结果量且默认不返回 Page HTML |
| 汇总与统计 | 计算 Section、SectionGroup、Page 数量、最近修改时间等 | 无统一汇总端点 | 可在完整分页结果上本地计算；不得把不完整首批结果当作准确计数 |
| 创建 Notebook | 用唯一名称创建顶层 Notebook | 支持 Create | 当前 `create_notebook` 已实现并受写入开关保护 |
| 原地重命名 | 修改现有 Notebook 名称且保持 ID/链接不变 | 不支持 PATCH | 记录为业务需求但不可实现；Copy 的 `renameAs` 不是重命名 |
| 新建直属 Section | 在 Notebook 下增加 Section | 支持 Create section | 当前 `create_section` 已实现 Notebook 直属创建 |
| 新建直属 SectionGroup | 在 Notebook 下增加 SectionGroup | 支持 Create section group | Graph 可做，当前 MCP 未开放 |
| 管理后代 Page | 经 Section 创建、更新、复制或删除 Page | 由各子资源端点支持，能力不对称 | 属于 Notebook 聚合操作；必须沿用 Page 的写入/删除确认和内容校验，不得提供无边界批量写 |
| 复制 Notebook | 创建完整副本，可为副本指定新名称 | 支持异步 Copy，返回 operation 位置 | 当前未实现；需受控轮询、幂等风险说明和副本状态回查 |
| 移动或跨位置迁移 | 将 Notebook 改挂到其他用户、Group、Site 或存储位置 | `/me/onenote/` 范围内无原生 Move | 本项目不提供；不能用复制后 Drive 删除冒充安全移动 |
| 清空或合并 Notebook | 批量迁移/复制内容后保留一个业务容器 | 无原生事务或 Merge | 只能视为高风险组合需求；Section 无 Delete，无法保证原子性或完整回滚，当前不提供 |
| 删除 Notebook | 移除整个 Notebook | OneNote API 不支持；Drive package 删除需要 `Files.ReadWrite` | 生产 MCP 明确不提供；Drive 路径仅限获授权的本地 live-test 控制面 |
| 恢复 Notebook | 撤销删除或恢复历史版本 | OneNote API 无 Restore | 产品数据面不提供；测试控制面删除进入 OneDrive 回收站也不构成 MCP 恢复能力 |
| 打开 Notebook | 跳转到 OneNote Web 或本机客户端 | 可读取 `links` | 可作为只读导航字段返回；不得由 URL 扩大 Graph 请求范围 |
| 导出、备份、导入 | 生成/恢复可移植 Notebook 包 | OneNote Graph v1.0 无统一 Notebook 导入导出端点 | 记录为业务需求但超出当前 MCP 范围；不得承诺副本等同可移植备份 |
| 共享与权限管理 | 邀请协作者、查看或修改权限 | 不属于 OneNote Notebook 方法，通常涉及 Drive/Site 与身份数据 | 因 `/me/onenote/` allowlist、Files scope 和身份信息边界不提供 |

## 规范化返回

```json
{
  "id": "notebook-id",
  "name": "工作笔记",
  "created": "2026-01-01T00:00:00Z",
  "modified": "2026-01-02T00:00:00Z",
  "is_default": false,
  "is_shared": false,
  "user_role": "Owner",
  "web_url": null,
  "client_url": null
}
```

## Copy 与名称

`copyNotebook` 的 `renameAs` 只命名新副本，不能视为 `name` 更新：

```text
源 Notebook 保留 + 创建一个具有新名称的 Notebook
```

生产 MCP 不通过 Drive package 删除来模拟重命名或移动。
