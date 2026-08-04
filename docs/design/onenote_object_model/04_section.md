# Section 字段与操作模型

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
| `path` | Graph 父关系 + 本地递归 | Get Path 必读 | 不写 | `R/D` | 必须包含全部 SectionGroup |

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
| `top_level_pages` | 无独立关系 | Get Tree 必读 | 不写 | `D` | 从 `level/order` 筛选 |
| `page_count` | 无稳定标量 | 选读 | 不写 | `D` | 完整分页后计算 |

Section 聚合更新包含创建、更新、删除直属 Page。稳定 API 不支持改变 Page 的缩进、顺序或父 Page，因此不能把页面树的任意变化都归为已支持。

## CRUD 操作支持

本节只列 Section 自身的基础 CRUD；Page 的 CRUD 在 Page 章节单独描述。状态沿用总览：`M` 为当前已实现，`G` 为 Graph 原生但 MCP 待实现，`X` 为 Graph 不支持或项目明确不提供；`M（部分）` 表示工具已存在但契约尚未完整。

| 类别 | 操作 | 状态 | Graph v1.0 支持 | 当前实现与待实现 |
| --- | --- | --- | --- | --- |
| `C` | 在 Notebook 下创建 Section | `M` | `POST /me/onenote/notebooks/{notebook-id}/sections` | `create_section` 已实现，并受 `ONENOTE_ENABLE_WRITES` 保护。 |
| `C` | 在 SectionGroup 下创建 Section | `G` | `POST /me/onenote/sectionGroups/{section-group-id}/sections` | 待扩展 `create_section` 的受控父级参数，并复用写入开关、名称校验和规范化返回。 |
| `R` | 列出全部 Section | `G` | 支持 OneNote 根级 Section 集合 | 待实现统一入口、分页和父关系回填。 |
| `R` | 列出 Notebook 的直属 Section | `M（部分）` | 支持 Notebook 下 List sections | `list_sections` 已实现首批基础字段；待统一分页和规范化字段。 |
| `R` | 列出 SectionGroup 的直属 Section | `G` | 支持 SectionGroup 下 List sections | 待实现分页读取，并明确只返回直接子 Section。 |
| `R` | 获取 Section | `M（部分）` | 支持按 ID Get，可读取父 Notebook 与可选父 SectionGroup | `get_section` 已实现基础字段；待补齐父关系和规范化字段。 |
| `R` | 查询 Section | `G` | 支持在 Section 集合上使用受支持的 OData 元数据条件 | 待实现结构化 `query_sections`；不得接受原始 OData 或 Graph URL。 |
| `U` | 重命名 Section | `X` | 稳定 v1.0 没有 Section PATCH | 不实现 Copy 的 `renameAs` 伪装成原地重命名。 |
| `U` | 更新 Section 父级 | `X` | 稳定 v1.0 没有 Move 或 reparent | Section Copy 会创建新 ID，不能作为更新原对象交付。 |
| `D` | 删除 Section | `X` | 稳定 v1.0 没有 Section DELETE | 不通过重建 Notebook、Drive 或 UI 自动化模拟。 |

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
