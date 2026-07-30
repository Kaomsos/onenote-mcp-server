# Section 字段模型

## Graph 能力边界

Section 可直属 Notebook，也可位于任意嵌套 SectionGroup。Graph 提供 `parentNotebook` 和可选 `parentSectionGroup`，并允许创建、列出 Page 和异步复制 Section；稳定 v1.0 没有 Section PATCH 或 DELETE。

## 标量字段

| 项目字段 | Graph 字段 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `id` | `id` | 必读 | 不写 | `R` | Page 创建与 Section Copy 主键 |
| `name` | `displayName` | 必读 | 创建写 | `R/C` | 创建后不可原地重命名 |
| `created` | `createdDateTime` | 必读 | 不写 | `R` | 只读 UTC 时间 |
| `modified` | `lastModifiedDateTime` | 必读 | 不写 | `R` | 只读 UTC 时间 |
| `is_default` | `isDefault` | 建议读取 | 不写 | `R` | 默认 Section 标记 |
| `web_url` | `links.oneNoteWebUrl.href` | 选读 | 不写 | `R` | 仅用户导航 |
| `client_url` | `links.oneNoteClientUrl.href` | 选读 | 不写 | `R` | 仅用户导航 |
| `pages_url` | `pagesUrl` | 内部/兼容 | 不写 | `R` | 新接口使用 Section ID |
| `self_url` | `self` | 不读取 | 不写 | `R` | 不公开 |
| `created_by` | `createdBy` | 不读取 | 不写 | `R` | 排除身份信息 |
| `last_modified_by` | `lastModifiedBy` | 不读取 | 不写 | `R` | 排除身份信息 |

## 父关系

| 项目字段 | Graph 来源 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `notebook_id` | `parentNotebook.id` | 必读 | 不更新 | `R` | 始终保留所属 Notebook |
| `parent_section_group_id` | `parentSectionGroup.id` | 必读，可空 | 创建时由端点选择 | `R/C` | 创建后不能 PATCH |
| `path` | Graph 父关系 + 本地递归 | 路径查询必读 | 不写 | `R/D` | 必须包含全部 SectionGroup |

创建位置由端点而非请求字段决定：

```http
POST /me/onenote/notebooks/{notebook-id}/sections
POST /me/onenote/sectionGroups/{section-group-id}/sections
```

Section Copy 可以选择目标 Notebook 或 SectionGroup，但会创建新 Section，不能视为父关系更新或原生 Move。

## Page 聚合关系

| 项目关系 | Graph 关系 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `pages` | `pages` | 必读 | 聚合写 | `R/A` | 可 List/Create，Page 可 Update/Delete |
| `top_level_pages` | 无独立关系 | 树查询必读 | 不写 | `D` | 从 `level/order` 筛选 |
| `page_count` | 无稳定标量 | 选读 | 不写 | `D` | 完整分页后计算 |

Section 聚合更新包含创建、更新、删除直属 Page。稳定 API 不支持改变 Page 的缩进、顺序或父 Page，因此不能把页面树的任意变化都归为已支持。

## 规范化返回

```json
{
  "id": "section-id",
  "name": "OneNote MCP",
  "created": "2026-01-01T00:00:00Z",
  "modified": "2026-01-02T00:00:00Z",
  "is_default": false,
  "notebook_id": "notebook-id",
  "parent_section_group_id": "section-group-id",
  "web_url": null,
  "client_url": null
}
```
