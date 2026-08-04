# SectionGroup 字段与操作模型

## 项目定位

SectionGroup 是构建完整路径不可缺少的 Graph 原生对象，可包含 Section 和更多 SectionGroup。当前产品 CRUD 仍聚焦 Notebook、Section、Page；SectionGroup 在 MCP 中先作为只读结构节点，Graph 的创建能力不等于项目已经开放写工具。

## 标量字段

| 项目字段 | Graph 字段 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `id` | `id` | 必读 | 不写 | `R` | 树节点主键 |
| `name` | `displayName` | 必读 | 当前项目不写 | `R/C` | Graph 创建时可写，创建后不可更新 |
| `created` | `createdDateTime` | 必读 | 不写 | `R` | 只读 UTC 时间 |
| `modified` | `lastModifiedDateTime` | 必读 | 不写 | `R` | 只读 UTC 时间 |
| `sections_url` | `sectionsUrl` | 内部 | 不写 | `R` | 不公开 |
| `section_groups_url` | `sectionGroupsUrl` | 内部 | 不写 | `R` | 不公开 |
| `self_url` | `self` | 不读取 | 不写 | `R` | 不公开 |
| `created_by` | `createdBy` | 不读取 | 不写 | `R` | 排除身份信息 |
| `last_modified_by` | `lastModifiedBy` | 不读取 | 不写 | `R` | 排除身份信息 |

## 父关系

| 项目字段 | Graph 来源 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `notebook_id` | `parentNotebook.id` | 必读 | 不更新 | `R` | 所属 Notebook |
| `parent_section_group_id` | `parentSectionGroup.id` | 必读，可空 | 创建时由端点选择 | `R/C` | 创建后不能 reparent |
| `depth` | 本地计算 | Get Tree 必读 | 不写 | `D` | SectionGroup 嵌套深度 |

顶层 SectionGroup 的 `parent_section_group_id` 为 `null`。嵌套 SectionGroup 同时保留 `notebook_id` 和直接父组 ID。

## 子关系

| 项目关系 | Graph 关系 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `sections` | `sections` | 必读 | 当前项目不写 | `R/A` | Graph 可 List/Create |
| `section_groups` | `sectionGroups` | 必读 | 当前项目不写 | `R/A` | Graph 可递归 List/Create |

若未来开放创建，位置由端点选择：

```http
POST /me/onenote/notebooks/{notebook-id}/sectionGroups
POST /me/onenote/sectionGroups/{parent-group-id}/sectionGroups
```

请求体只写 `displayName`；同层名称唯一，最长 50 字符，并遵守官方字符限制。稳定 API 没有 SectionGroup PATCH、DELETE 或原生 Move。

## CRUD 操作支持

本节只列 SectionGroup 自身的基础 CRUD。状态沿用总览：`M` 为当前已实现，`G` 为 Graph 原生但 MCP 待实现，`X` 为 Graph 不支持或项目明确不提供。

| 类别 | 操作 | 状态 | Graph v1.0 支持 | 当前实现与待实现 |
| --- | --- | --- | --- | --- |
| `C` | 在 Notebook 下创建 SectionGroup | `G` | `POST /me/onenote/notebooks/{notebook-id}/sectionGroups` | 当前没有 SectionGroup 工具；待实现并接入写入开关、名称校验和规范化返回。 |
| `C` | 在 SectionGroup 下创建 SectionGroup | `G` | `POST /me/onenote/sectionGroups/{section-group-id}/sectionGroups` | 当前没有 SectionGroup 工具；待实现嵌套创建并校验直接父组。 |
| `R` | 列出 Notebook 的直属 SectionGroup | `G` | 支持 Notebook 下 List section groups | 待实现分页读取与父 Notebook 关系回填。 |
| `R` | 列出 SectionGroup 的直属 SectionGroup | `G` | 支持 SectionGroup 下 List section groups | 待实现分页读取；该操作只返回直接子组，不隐式递归整棵树。 |
| `R` | 获取 SectionGroup | `G` | 支持按 ID Get | 待实现，并规范化 `notebook_id` 与可空 `parent_section_group_id`。 |
| `R` | 查询 SectionGroup | `G` | 支持在 SectionGroup 集合上使用受支持的 OData 元数据条件 | 待实现结构化 `query_section_groups`；不得接受原始 OData 或 Graph URL。 |
| `U` | 重命名 SectionGroup | `X` | 稳定 v1.0 没有 SectionGroup PATCH | 不实现 Copy/重建式伪更新。 |
| `U` | 更新 SectionGroup 父级 | `X` | 稳定 v1.0 没有 Move 或 reparent | 不实现“重建子树并遗留源组”的伪移动。 |
| `D` | 删除 SectionGroup | `X` | 稳定 v1.0 没有 SectionGroup DELETE | 不实现 Drive 或 UI 自动化绕路。 |

## 规范化返回

```json
{
  "id": "section-group-id",
  "name": "项目",
  "created": "2026-01-01T00:00:00Z",
  "modified": "2026-01-02T00:00:00Z",
  "notebook_id": "notebook-id",
  "parent_section_group_id": null,
  "depth": 0
}
```
