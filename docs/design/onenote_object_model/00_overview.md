# OneNote 对象层级与字段访问模型

## 目的与范围

本文档集定义本项目在 Microsoft Graph v1.0 上使用的 OneNote 对象模型、字段命名、读写边界和树查询语义。生产范围固定为当前登录用户的 `/me/onenote/`，不把 Group、Site、Drive 或通用 Graph 资源纳入 MCP 数据面。

本设计区分三种事实：

1. Graph 原生对象、字段和 relationship；
2. 本项目为 MCP 返回值规范化的字段；
3. 为 Page 层级和统一路径而由本地代码推导的字段。

推导字段不得描述成 Graph 原生 relationship。

## 文档索引

- [完整层级与树查询契约](01_hierarchy_and_queries.md)
- [Notebook 字段模型](02_notebook.md)
- [SectionGroup 字段模型](03_section_group.md)
- [Section 字段模型](04_section.md)
- [Page、内容与资源字段模型](05_page.md)

## 完整层级

```text
OneNoteContext (/me/onenote)
└── Notebook
    ├── Section
    │   └── Page
    │       ├── Subpage
    │       └── Subpage
    │           └── Subsubpage
    └── SectionGroup
        ├── Section
        │   └── Page...
        └── SectionGroup
            ├── Section...
            └── SectionGroup...
```

`SectionGroup` 是可递归嵌套的 Graph 原生对象。Subpage 和 Subsubpage 不是新的 Graph 类型；它们仍是 `onenotePage`，只通过 Section 页面集合上的只读 `level` 与 `order` 表达缩进和顺序。Graph 不提供 `parentPage` relationship。

官方资源定义：

- [notebook](https://learn.microsoft.com/en-us/graph/api/resources/notebook?view=graph-rest-1.0)
- [sectionGroup](https://learn.microsoft.com/en-us/graph/api/resources/sectiongroup?view=graph-rest-1.0)
- [onenoteSection](https://learn.microsoft.com/en-us/graph/api/resources/onenotesection?view=graph-rest-1.0)
- [onenotePage](https://learn.microsoft.com/en-us/graph/api/resources/page?view=graph-rest-1.0)
- [获取 OneNote 内容和结构](https://learn.microsoft.com/en-us/graph/onenote-get-content)

## 访问能力标记

各分文档使用以下 Graph 能力标记：

| 标记 | 含义 |
| --- | --- |
| `R` | Graph 可直接读取 |
| `C` | 仅能在创建资源时写入，创建后不能 PATCH |
| `U` | 创建后可通过稳定 API 更新 |
| `A` | 通过对子资源调用 API 改变聚合集合，不是字段 PATCH |
| `D` | Graph 不返回，由本地代码推导 |
| `X` | 稳定 Graph v1.0 不支持 |

项目需求使用：`必读`、`选读`、`内部`、`不读取`、`创建写`、`更新写`、`聚合写`、`不写`。

字段没有标为只读并不等于存在更新能力。是否可更新必须同时有稳定 v1.0 方法或内容 PATCH 端点作为证据。

## 统一公共字段

所有树节点使用以下公共视图；具体资源仍保留 `name` 或 `title`：

| 项目字段 | 来源 | 写性 | 说明 |
| --- | --- | --- | --- |
| `resource_type` | 本地常量 | 不写 | `notebook`、`section_group`、`section`、`page` |
| `id` | Graph `id` | 不写 | 资源主键 |
| `label` | `name` 或 `title` 映射 | 不写 | 仅用于统一展示 |
| `created` | Graph `createdDateTime` | 不写 | ISO 8601 UTC |
| `modified` | Graph `lastModifiedDateTime` | 不写 | ISO 8601 UTC |
| `depth` | 本地计算 | 不写 | 当前路径或子树中的相对深度 |
| `relationship_source` | 本地判定 | 不写 | `graph` 或 `derived` |

`label` 不是资源自身的写入字段。Notebook、SectionGroup、Section 的业务名称字段是 `name`；Page 是 `title`。

## 总体写入结论

| 对象 | 创建时可写 | 创建后可直接更新 | 可聚合更新 | 不可写的关键字段 |
| --- | --- | --- | --- | --- |
| Notebook | `name` | 无 | 添加 Section、SectionGroup，以及经子资源改变 Page | ID、时间、默认/共享状态、角色、父关系 |
| SectionGroup | `name`、创建位置 | 无 | Graph 可添加 Section 和子 SectionGroup；当前 MCP 不开放 | ID、时间、父关系 |
| Section | `name`、创建位置 | 无 | 创建、更新、删除 Page | ID、时间、默认状态、父关系 |
| Page | `title`、HTML、目标 Section | `title` 和受控 HTML 元素 | 删除、复制 | ID、时间、`level`、`order`、推导父关系 |

Notebook、SectionGroup、Section 的 `displayName` 没有稳定更新方法；Copy 的 `renameAs` 创建副本，不是原地重命名。Page 标题可用内容 PATCH 的 `target: "title"` 与 `action: "replace"` 更新。

## 安全与兼容原则

- 不返回 `createdBy`、`lastModifiedBy` 或其他账号身份字段。
- 不把 Graph 原始响应体、认证材料或账号资料写入日志、文档或 MCP 错误。
- `self`、`sectionsUrl`、`sectionGroupsUrl`、`pagesUrl`、`contentUrl` 不是调用授权；HTTP 层必须使用资源 ID 和 `/me/onenote/` allowlist 构造请求。
- 当前工具已有的 `sections_url`、`pages_url`、`content_url` 可暂时兼容，但新树和路径接口不得依赖这些 URL。
- Page HTML 只由显式内容工具返回，List、搜索、路径和树查询不得默认返回完整 HTML。
- 生产 MCP 不请求 `Files.ReadWrite`，不通过 Drive 模拟 Notebook 或 Section 产品级 CRUD。

## 当前实现差距

当前 `onenote_mcp/tools.py` 只映射：

- Notebook：`id`、`name`、`created`、`modified`；精确读取额外返回 `sections_url`；
- Section：`id`、`name`、`created`、`modified`；精确读取额外返回 `pages_url`；
- Page：`id`、`title`、`created`、`modified`、`content_url`，以及独立 HTML 读取；
- SectionGroup：尚未实现。

目标模型还需补充父 relationship、SectionGroup、`pagelevel=true`、分页完成性以及 Page 本地树推导。本文档只固定设计，不表示这些字段已经由 MCP 工具实现。
