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

## 业务操作目录

下表覆盖 Section 的发现、组织、Page 聚合和生命周期操作。Section 可以管理 Page，并不表示 Section 自身具备完整 CRUD。

| 操作 | 业务语义 | Graph v1.0 边界 | 项目结论 |
| --- | --- | --- | --- |
| 列出全部 Section | 跨 Notebook/SectionGroup 发现当前用户的 Section | 支持 OneNote 根集合 List | 当前未实现统一入口；需要分页和父关系回填 |
| 列出父级直属 Section | 查看 Notebook 或 SectionGroup 的直接子 Section | 两类父级均支持 List sections | 当前 `list_sections` 只覆盖 Notebook 直属 Section；SectionGroup 入口待实现 |
| 获取 Section | 以 ID 读取元数据、父关系和必要导航信息 | 支持 Get，可展开父 Notebook/SectionGroup | 当前 `get_section` 已实现基础元数据；目标模型需补父关系 |
| 读取完整路径 | 返回 Notebook/SectionGroup 链到当前 Section 的路径 | 父关系可读；嵌套组路径需递归组合 | 候选本地操作；完整路径用于消歧，不得依赖原始 `self` URL |
| 查找与筛选 | 按名称、父路径、默认状态或修改时间定位 Section | 可集合读取后本地筛选 | 候选本地操作；同名 Section 必须结合父路径处理 |
| 读取 Page 列表 | 分页读取 Section 内全部 Page 元数据 | 支持 List pages，可请求 `pagelevel=true` | 当前 `list_pages` 已实现首批读取；页面树和准确计数要求完整分页 |
| 读取 Page 树 | 按 `level/order` 重建主 Page、Subpage、Subsubpage | Graph 只读返回层级/顺序，没有父 Page 关系 | 候选本地推导操作；需处理层级跳变、断链和稳定排序 |
| 汇总与统计 | 计算 Page 总数、顶层/子页面数和最近修改时间 | 无稳定 Section 计数字段 | 只能基于完整 Page 集合本地计算 |
| 创建 Section | 在 Notebook 或 SectionGroup 下新建 Section | 两类父级均支持 Create | 当前只实现 Notebook 下创建；SectionGroup 下创建待开放并受写入开关保护 |
| 原地重命名 | 修改名称并保持 Section/Page 身份不变 | 不支持 PATCH | 记录为业务需求但不可实现；Copy 的 `renameAs` 只命名副本 |
| 创建 Page | 在 Section 内新增 Page | 支持 Create page | 当前已实现，受写入开关和 HTML 校验约束 |
| 更新 Page | 修改 Page 标题或受控 HTML 元素 | 支持 Page 内容 PATCH，不支持任意整页替换 | 当前只实现固定追加；完整 `append/prepend/insert/replace` 仍需受限契约 |
| 删除 Page | 从 Section 中移除精确确认的 Page | 支持 Page DELETE | 当前已实现；必须保留双开关、标题确认和删除前回读 |
| 批量管理 Page | 批量创建、更新、复制或删除所选 Page | 无原生事务或批量 OneNote 语义 | 记录为业务需求；若未来提供，必须逐项确认、限量并明确部分成功，当前不提供 |
| 复制 Section 到 Notebook | 在目标 Notebook 创建 Section 副本，可 `renameAs` | 支持异步 `copyToNotebook` | 当前未实现；需 operation 轮询和副本状态验证 |
| 复制 Section 到 SectionGroup | 在目标组创建 Section 副本，可 `renameAs` | 支持异步 `copyToSectionGroup` | 当前未实现；同样不得盲目重试复制 POST |
| 移动或重新挂接 | 改变父 Notebook/SectionGroup，并尽量保持业务内容 | 无原生 Move/reparent，源 Section 也不可删除 | 仅可探索 `copy → verify → markAsDeleted` 的逻辑移动；墓碑持久化可靠前只能称 Copy |
| 排序 Section | 调整同一父级下的显示顺序 | 无稳定排序写接口 | 不可实现；本地排序结果不代表 OneNote 中顺序已修改 |
| 合并或拆分 Section | 把多组 Page 归并或分配到新 Section | 可组合创建与 Page Copy，但无事务、原生 Page Move 或源 Section Delete | 记录为高风险组合需求；不能保证身份、层级、顺序、附件和回滚，当前不提供 |
| 删除 Section | 删除整个 Section | OneNote API 无 DELETE，Section 也无可安全独立寻址的 DriveItem | 不可实现；不得通过重建 Notebook 或扩大 Drive 删除范围模拟 |
| 恢复 Section | 恢复被删除 Section 或历史状态 | 无 Delete/Restore | 不可实现；同名重建或 Copy 都会产生新 ID |
| 打开 Section | 跳转到 OneNote Web 或本机客户端 | 可读取 `links` | 可作为只读导航字段返回；不得把 URL 当作 Graph 调用入口 |
| 导出、备份、共享 | 导出单个 Section 或管理独立权限 | 无 Section 级稳定导出/权限方法 | 超出当前 MCP 范围；Section Copy 不等于可移植备份或权限复制 |

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
