# 完整层级与树查询契约

## Graph 原生结构

Notebook 有两类直属子 relationship：`sections` 与 `sectionGroups`。SectionGroup 又能包含 `sections` 和 `sectionGroups`，因此完整结构遍历必须处理任意深度的 SectionGroup。

Section 的 Graph 父关系是：

- 必有 `parentNotebook`；
- 位于 SectionGroup 内时有 `parentSectionGroup`；
- 直属 Notebook 时 `parentSectionGroup` 为空。

Page 的 Graph 父关系只有 `parentNotebook` 和 `parentSection`。Page 的缩进父节点不是 relationship，必须从同一 Section 的完整页面序列推导。

## 规范化节点

```json
{
  "resource_type": "page",
  "id": "page-id",
  "label": "分页协议",
  "created": "2026-01-01T00:00:00Z",
  "modified": "2026-01-02T00:00:00Z",
  "depth": 4,
  "relationship_source": "derived"
}
```

`relationship_source` 表示当前节点与前一个路径节点之间的关系来源：

- Notebook → SectionGroup、SectionGroup → SectionGroup、Notebook/SectionGroup → Section：`graph`；
- Section → 顶层 Page：`graph`；
- Page → Subpage、Subpage → Subsubpage：`derived`。

## 路径查询

路径结果从 Notebook 开始并包含目标自身：

```json
{
  "target": {"resource_type": "page", "id": "target-page-id"},
  "path": [
    {"resource_type": "notebook", "id": "notebook-id", "label": "工作笔记", "depth": 0, "relationship_source": "graph"},
    {"resource_type": "section_group", "id": "group-id", "label": "项目", "depth": 1, "relationship_source": "graph"},
    {"resource_type": "section", "id": "section-id", "label": "OneNote MCP", "depth": 2, "relationship_source": "graph"},
    {"resource_type": "page", "id": "root-page-id", "label": "设计", "depth": 3, "relationship_source": "graph"},
    {"resource_type": "page", "id": "target-page-id", "label": "分页协议", "depth": 4, "relationship_source": "derived"}
  ],
  "complete": true
}
```

路径构建规则：

1. Notebook 路径只包含自身。
2. SectionGroup 沿 `parentSectionGroup` 递归回溯，直到 `parentNotebook`。
3. Section 先回溯可选 SectionGroup 链，再追加自身。
4. Page 先构建 Section 路径，再完整读取所在 Section 页面列表并推导父 Page 链。

任何父资源缺失、SectionGroup 循环、分页未完成或 Page 层级不一致都必须令 `complete=false`，并返回固定脱敏错误码；不得猜测缺失节点。

## 子节点查询

本项目约定：

- Notebook：只返回直属 Section 与直属 SectionGroup；
- SectionGroup：只返回直属 Section 与直属 SectionGroup，供内部递归；
- Section：只返回顶层 Page；
- Page：返回该 Page 的全部后代，包括 Subpage 与 Subsubpage。

Page 后代结果应同时包含：

| 字段 | 含义 |
| --- | --- |
| `graph_level` | Graph 返回的原始 `level` |
| `depth` | 相对于查询 Page 的本地深度，直接子 Page 为 1 |
| `parent_page_id` | 本地推导的直接父 Page ID |
| `has_children` | 本地计算 |
| `relationship_source` | 固定为 `derived` |

## Page 树重建

必须对 Section 页面集合请求 `pagelevel=true`，完成所有分页后再处理。Graph 文档说明 `level`、`order` 只在 Section 页面集合或单 Page 使用 `pagelevel=true` 时返回。

重建流程：

1. 校验每条记录有非空 `id`、整数 `level`、整数 `order`。
2. 完成全部分页后，按可靠的 Section 内顺序处理；不得使用默认的最后修改时间顺序重建树。
3. 使用层级栈记录最近的各级 Page。
4. 当前 Page 层级比前一条最多深一层；跳级时返回 `hierarchy_level_jump`。
5. 层级回退时弹出栈直到对应层级。
6. 同一 Section 内 `order` 缺失或冲突时返回 `hierarchy_order_invalid`。
7. 生成 `parent_page_id`、标准化 `depth` 和 `has_children`。

OneNote 客户端通常允许两层 Subpage，即主 Page、Subpage、Subsubpage三层。实现应保留原始 `graph_level`，不要把本地 `depth` 冒充 Graph 值；遇到超出预期但结构自洽的数据可保留，遇到不自洽数据则安全失败。

Graph 的 `level` 与 `order` 只读，因此树结构可读但不可写：不能通过稳定 API 创建子 Page、缩进、提升、重新挂接或排序。

## 分页与完整性

集合请求默认可能只返回首批结果。公开 List 应返回不透明 `next_cursor`；树重建与路径查询则必须内部完成全部相关分页后才允许 `complete=true`。

```json
{
  "items": [],
  "next_cursor": null,
  "has_more": false,
  "complete": true
}
```

不透明游标只封装已验证的 `/me/onenote/` 后续路径，不向 MCP 调用者暴露或接受任意 nextLink。

## 本地字段访问矩阵

| 字段 | Graph 支持 | 项目读性 | 项目写性 |
| --- | --- | --- | --- |
| `resource_type` | `D` | 必读 | 不写 |
| `label` | `D`，映射 `name/title` | 必读 | 不写 |
| `depth` | `D` | 必读 | 不写 |
| `relationship_source` | `D` | 必读 | 不写 |
| `path` | `D`，依赖 Graph 父关系 | 路径查询必读 | 不写 |
| `parent_page_id` | `D` | Page 树必读 | 不写 |
| `has_children` | `D` | 建议读取 | 不写 |
| `complete` | `D` | 必读 | 不写 |
| `next_cursor` | `D`，封装 Graph 分页 | 分页读取 | 只允许原样续传 |

## 安全失败码

建议固定使用：

- `hierarchy_incomplete`
- `hierarchy_parent_missing`
- `hierarchy_parent_cycle`
- `hierarchy_level_jump`
- `hierarchy_order_invalid`
- `pagination_invalid`

错误不得包含 Graph 原始响应、资源 ID 列表、HTML 或账号资料。
