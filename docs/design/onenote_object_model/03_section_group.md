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
| `depth` | 本地计算 | 树查询必读 | 不写 | `D` | SectionGroup 嵌套深度 |

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

## 业务操作目录

SectionGroup 是组织结构层，而不是只有字段的被动节点。下表列出路径浏览、结构维护和生命周期方面应考虑的操作，并明确当前只读定位与 Graph 原生能力之间的差异。

| 操作 | 业务语义 | Graph v1.0 边界 | 项目结论 |
| --- | --- | --- | --- |
| 列出顶层 SectionGroup | 查看某 Notebook 的直属分组 | 支持 Notebook 下 List section groups | 当前未实现；目标读取必须统一分页 |
| 列出子 SectionGroup | 查看某分组的直接子组 | 支持 SectionGroup 下 List section groups | 当前未实现；递归树查询应建立在该直接关系上 |
| 获取 SectionGroup | 以 ID 读取元数据、父关系和必要子关系 | 支持 Get | 当前未实现；应规范化父 Notebook 与可空父组 ID |
| 读取祖先路径 | 从当前组回溯到 Notebook，形成稳定面包屑路径 | Graph 提供 `parentNotebook`、`parentSectionGroup`；完整路径需递归读取 | 候选本地组合操作；需检测环、断链和深度上限 |
| 读取子树 | 递归返回子组与 Section，可选 Page 摘要 | 支持逐层列出；没有单次完整树端点 | 候选聚合读操作；需分页、深度/节点数限制，默认不带 Page HTML |
| 查找与筛选 | 按名称、父路径或修改时间定位分组 | 可列出后本地筛选 | 候选本地操作；同名组必须用完整路径消歧 |
| 汇总与统计 | 计算直接/递归子组、Section 和 Page 数量 | 无统一计数端点 | 只能在完整遍历结果上本地计算，并标注直接或递归口径 |
| 创建顶层 SectionGroup | 在 Notebook 下建立分组 | 支持 Create section group | Graph 可做，当前 MCP 未开放；应受普通写入开关保护 |
| 创建嵌套 SectionGroup | 在现有组下建立子组 | 支持 Create section group | Graph 可做，当前 MCP 未开放；创建前需确认直接父组 |
| 创建直属 Section | 在组内新增 Section | 支持 Create section | Graph 可做，当前 `create_section` 只支持 Notebook 直属位置 |
| 原地重命名 | 修改名称并保持组 ID 与子树不变 | 不支持 PATCH | 记录为业务需求但不可实现 |
| 复制 SectionGroup | 复制整个组及其后代 | 无原生 Copy | 当前不提供；逐项复制不是原子操作，且源/副本身份、顺序和失败恢复难以保证 |
| 移动或重新挂接 | 在同一/不同 Notebook 内改变父组 | 无原生 Move/reparent | 当前不提供；不能把“重建子树并遗留源组”称为移动 |
| 排序 SectionGroup | 调整同层显示顺序 | 无稳定排序写接口 | 不可实现；本地返回顺序不得伪装成 OneNote 客户端顺序已改变 |
| 合并或拆分分组 | 批量重组下属 Section/SectionGroup | 无原生 Merge/Split，且组本身不可删除 | 记录为组合业务需求；无法保证原子性、回滚和源清理，当前不提供 |
| 删除 SectionGroup | 删除组及其后代，或仅移除空组 | 无 DELETE | 不可实现；不得通过扩大到 Drive 或 UI 自动化绕过 |
| 恢复 SectionGroup | 撤销删除或重建原身份 | 无 Delete/Restore | 不可实现；重新创建同名组会产生新 ID，不是恢复 |
| 导出、备份、共享 | 导出子树或单独管理组权限 | 无 SectionGroup 级导出/权限方法 | 超出当前产品范围；可读树快照不等于可恢复备份 |

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
