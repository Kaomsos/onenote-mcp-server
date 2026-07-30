# Notebook 字段模型

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
