# Page、内容与资源字段模型

## Graph 能力边界

主 Page、Subpage 与 Subsubpage 都是同一个 `onenotePage` 类型。Graph 只提供 `parentNotebook`、`parentSection`、只读 `level` 和只读 `order`，不提供 `parentPage` 或 `children` relationship。

Page 可创建、读取元数据与 HTML、受控更新 HTML、删除和异步复制到 Section。只有 Page 标题和部分 HTML 元素有稳定的创建后更新能力。

## 基础元数据

| 项目字段 | Graph 字段 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `id` | `id` | 必读 | 不写 | `R` | Graph 生成的主键 |
| `title` | `title` | 必读 | 创建写、更新写 | `R/C/U` | 创建 HTML `<title>`；更新用 title target |
| `created` | `createdDateTime` | 必读 | 当前项目不写 | `R` | 按只读字段处理 |
| `modified` | `lastModifiedDateTime` | 必读 | 不写 | `R` | Graph 自动维护 |
| `created_by_app_id` | `createdByAppId` | 不读取/内部 | 不写 | `R` | 核心业务不需要 |
| `content_url` | `contentUrl` | 内部/兼容 | 不写 | `R` | 新内容工具使用 Page ID |
| `web_url` | `links.oneNoteWebUrl.href` | 选读 | 不写 | `R` | 用户导航 |
| `client_url` | `links.oneNoteClientUrl.href` | 选读 | 不写 | `R` | 用户导航 |
| `self_url` | `self` | 不读取 | 不写 | `R` | 不公开 |

Page 标题更新使用：

```json
[
  {
    "target": "title",
    "action": "replace",
    "content": "新标题"
  }
]
```

项目应提供专用 `rename_page`，而不是让调用者提交任意 change-object。

## 官方父关系与本地层级

| 项目字段 | Graph 来源 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `notebook_id` | `parentNotebook.id` | 必读 | 不更新 | `R` | 官方父关系 |
| `section_id` | `parentSection.id` | 必读 | 创建时由端点选择 | `R/C` | 创建后不能 PATCH |
| `graph_level` | `level` | 树查询必读 | 不写 | `R` | 只读；需 `pagelevel=true` |
| `order` | `order` | 树查询必读 | 不写 | `R` | 只读；Section 内顺序 |
| `parent_page_id` | 无 | 树查询必读 | 不写 | `D` | 本地层级栈推导 |
| `depth` | 无 | 树查询必读 | 不写 | `D` | 标准化相对深度 |
| `has_children` | 无 | 建议读取 | 不写 | `D` | 完整列表后计算 |
| `children` | 无 | 后代查询必读 | 不写 | `D` | 本地树重建 |

Page 创建时通过 `POST /me/onenote/sections/{section-id}/pages` 选择目标 Section。`copyToSection` 创建新 Page，原 Page 保留，不能视为 `section_id` 更新。

Graph 不支持写入 `level`、`order`、`parent_page_id`，因此不能创建子 Page、缩进、提升、重新挂接或排序。

## HTML 内容

| 项目字段 | Graph 来源 | 项目读性 | 项目写性 | Graph 支持 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `content_html` | `/pages/{id}/content` | 显式读取 | 创建写、受控更新写 | `R/C/U` | 不进入 List/树默认结果 |
| `preview_text` | `/pages/{id}/preview` | 搜索结果选读 | 不写 | `R` | 页面短摘要 |
| `element_ids` | `content?includeIDs=true` | 元素更新时内部读取 | 不写 | `R` | Graph 生成 ID |
| `data_id` | HTML `data-id` | 更新时内部读取 | 创建/更新时可提供 | `C/U` | 稳定的调用者定义 target |

支持的 change action：

| Action | 项目需求 | Graph 限制 |
| --- | --- | --- |
| `append` | 需要 | 只适用于 body、特定 div、ol、ul |
| `prepend` | 需要 | 同 append 的元素限制 |
| `insert` | 需要 | 作为目标元素的前后 sibling |
| `replace` | 需要 | title 或支持替换且通常需要生成 ID 的元素 |

`body` 不支持整体 `replace`。本项目不得承诺任意整页覆盖，也不得暴露通用 Graph PATCH。具体元素更新前应读取 `content?includeIDs=true` 并校验 target、action、position 与 HTML。

官方说明：[更新 OneNote Page 内容](https://learn.microsoft.com/en-us/graph/onenote-update-page)。

## 规范化元数据返回

```json
{
  "id": "page-id",
  "title": "分页协议",
  "created": "2026-01-01T00:00:00Z",
  "modified": "2026-01-02T00:00:00Z",
  "notebook_id": "notebook-id",
  "section_id": "section-id",
  "graph_level": 2,
  "order": 30,
  "parent_page_id": "parent-page-id",
  "depth": 2,
  "has_children": false,
  "relationship_source": "derived"
}
```

## Page 内部图片与附件

图片和附件不是 Notebook 树节点。Graph 不支持获取 Page resource 集合；必须从 Page HTML 的 `img` 或 `object` 元素解析资源 URL，再按资源 ID 读取二进制。

若以后实现附件能力，使用独立模型：

| 项目字段 | 项目读性 | 项目写性 | 来源/限制 |
| --- | --- | --- | --- |
| `resource_id` | 必读 | 不写 | 从受验证的 Page HTML 资源 URL 解析 |
| `page_id` | 必读 | 创建时隐式绑定 | 本地上下文 |
| `resource_kind` | 必读 | 创建时决定 | `image` 或 `attachment` |
| `file_name` | 选读 | 创建时可提供 | `data-attachment` |
| `media_type` | 必读 | 创建时提供 | HTML/multipart MIME |
| `content` | 显式读取 | 创建/更新写 | 二进制流，不进入普通 JSON 元数据 |
| `content_url` | 内部 | 不写 | 不公开为任意请求入口 |

资源能力不属于当前 Notebook/Section/Page 基础 CRUD，不能因解析 HTML 而自动扩大数据返回范围。
