# OneNote 对象层级、字段与操作模型

## 目的与范围

本文档集定义本项目在 Microsoft Graph v1.0 上使用的 OneNote 对象模型、字段命名、业务操作、读写边界和树查询语义。生产范围固定为当前登录用户的 `/me/onenote/`，不把 Group、Site、Drive 或通用 Graph 资源纳入 MCP 数据面。

本设计区分三种事实：

1. Graph 原生对象、字段和 relationship；
2. 本项目为 MCP 返回值规范化的字段；
3. 为 Page 层级和统一路径而由本地代码推导的字段。

推导字段不得描述成 Graph 原生 relationship。

## 文档索引

- [完整层级与树查询契约](01_hierarchy_and_queries.md)
- [Notebook 字段与操作模型](02_notebook.md)
- [SectionGroup 字段与操作模型](03_section_group.md)
- [Section 字段与操作模型](04_section.md)
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

操作矩阵另使用以下交付状态；它描述的是“业务需要怎样操作对象”，不能替代字段能力标记：

| 标记 | 含义 |
| --- | --- |
| `M` | 当前 MCP 已开放；若带“部分”，表示语义或完整性仍有限制 |
| `G` | 稳定 Graph v1.0 原生支持，但当前 MCP 尚未开放 |
| `C` | 需要多个 Graph 调用、本地推导或项目级状态组合，尚未形成稳定工具契约 |
| `X` | 稳定 Graph v1.0 不支持，或因本项目安全/产品边界明确不提供 |
| `—` | 对该层级不适用 |

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

## 层级—操作矩阵

本矩阵先列业务所需操作，再标注交付边界；`G` 不等于已经注册 MCP 工具，`C` 也不等于可以安全模拟原生操作。详细语义、限制和候选组合方案见各层级分文档。

### 操作语义与英文命名

英文标准名用于产品文案、设计文档和代码命名参考。代码动词统一使用小写 `snake_case`，并追加资源名，例如 `list_notebooks`、`get_section`、`create_page`。下表参数是跨层级的概念签名；具体工具只保留该资源真正需要且平台支持的参数。

| 中文操作 | 英文标准名 | 建议代码动词 | 基本调用参数 | 统一语义 |
| --- | --- | --- | --- | --- |
| 列表 | List | `list_*` | `parent_id?`、`cursor?`、`limit?`、`filter?`、`order_by?` | 在指定范围内读取一组同类对象，例如列出某 Notebook 的直属 Section。结果是集合，必须考虑分页；默认只表示直接成员，不递归读取完整后代树。 |
| 单项读取 | Get | `get_*` | `<resource>_id`、`include?` | 通过一个已经确定的资源 ID 读取单个对象的元数据、必要关系或显式请求的内容。它不负责按名称查找，也不自动读取全部子级。 |
| 路径/树 | Get Path / Get Tree | `get_*_path` / `get_*_tree` | `<resource>_id`；Tree 另含 `max_depth?`、`include_pages?`、`limit?` | Get Path 沿父关系读取祖先路径；Get Tree 递归读取指定对象的后代结构。两者可以组合多个 List/Get，并可能包含 SectionGroup 递归和 Page 层级的本地推导。 |
| 创建 | Create | `create_*` | `parent_id?`、`name` 或 `title`、资源特有创建内容 | 在调用者明确指定的父级或位置新建对象；创建返回新资源，不能用来表示对原对象的重命名、移动或恢复。Notebook 没有 `parent_id`，Page 可另含 `content_html?`。 |
| 名称/内容更新 | Rename / Update Content | `rename_*` / `update_*_content` | Rename：`<resource>_id`、`new_name` 或 `new_title`；Content：`<resource>_id`、`target`、`action`、`content`、`position?` | 保持资源身份不变，修改该对象自身可写的名称、标题或内容。名称或标题变更统一称为 Rename；对子级集合的增删属于“子级聚合操作”。 |
| 子级聚合操作 | Child Aggregate Operations | 使用具体动词，如 `create_page`、`delete_page` | 明确的 `parent_id`、子资源输入；破坏性动作另含确认参数 | 通过创建、更新、复制或删除直接/间接子资源来改变父对象所管理的集合，例如在 Section 中创建 Page。它不是对父对象字段的 PATCH，也不应设计含糊的 `manage_*` 工具。 |
| 复制 | Copy | `copy_*` | `source_id`、`target_parent_id?`、`rename_as?` | 保留源对象并创建具有新 ID 的副本；副本可位于目标容器并可能使用新名称。目标位置和 `rename_as` 是否适用由具体资源决定；复制不是原地更新、移动、备份或恢复。 |
| 移动/重挂 | Move / Reparent | `move_*` / `reparent_*` | `<resource>_id`、`target_parent_id`、`expected_label?` | Move 表达业务位置迁移；Reparent 特指改变直接父级。若通过 `copy → verify → markAsDeleted` 组合，只能称为项目级 Logical Move，不能称为 Graph 原生 Move。 |
| 排序/缩进 | Reorder / Indent / Outdent | `reorder_*` / `indent_page` / `outdent_page` | Reorder：`<resource>_id`、`reference_id?`、`position`；Indent/Outdent：`page_id`、`expected_parent_page_id?` | Reorder 改变同级先后顺序；Indent/Outdent 改变 Page 的层级缩进。仅在返回结果中本地排序不算修改 OneNote 中的真实顺序。 |
| 删除 | Delete | `delete_*` | `<resource>_id`、`expected_label`、`expected_parent_id?` | 移除调用者精确确认的现有对象。确认字段应使用该资源的 `name` 或 `title`；删除子资源不等于删除父对象。逻辑标记和移入回收站不能统称 Delete。 |
| 恢复 | Restore | `restore_*` | `deletion_ref`、`target_parent_id?`、`expected_label?` | 撤销一次删除或恢复原对象身份、位置和内容。`deletion_ref` 必须是受支持恢复机制给出的安全引用；重新创建同名对象或从副本创建新对象不属于恢复。 |
| 查找/筛选 | Find / Filter | `find_*` / `filter_*` | `parent_id?`、`query` 或 `criteria`、`match_mode?`、`cursor?`、`limit?` | Find 根据业务条件定位候选对象；Filter 从已确定集合中筛选结果。两者必须处理零匹配和重名；`search_*` 保留给标题/正文等全文搜索。 |
| 导出/共享 | Export / Share | `export_*` / `share_*` | Export：`<resource>_id`、`format`、`destination?`；Share：`<resource>_id`、`principal`、`role` | Export 生成可移植、可恢复的数据；Share 读取或修改协作权限。返回导航链接、复制对象或读取树快照均不自动等同于导出、备份或共享管理。 |

参数名必须使用明确的资源语义，例如 `notebook_id`、`section_group_id`、`section_id`、`page_id`，不得在公开工具中只写 `id` 或 `parent_id`。表中的 `<resource>_id` 和 `parent_id` 只是概念占位符，`?` 表示可选参数；也不得用 `self_url`、`pages_url` 等原始 Graph URL 替代资源 ID。命名时优先使用上表动词，不混用 `read_*`、`fetch_*`、`load_*` 表示 Get，也不使用 `get_all_*` 表示 List。异步操作若拆成开始和状态查询，使用 `start_*` 与 `get_operation`；若工具内部等待完成，仍使用业务动词，例如 `copy_section`。

| 层级 | 列表 | 单项读取 | 路径/树 | 创建 | 名称/内容更新 | 子级聚合操作 | 复制 | 移动/重挂 | 排序/缩进 | 删除 | 恢复 | 查找/筛选 | 导出/共享 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Notebook | `M`，暂缺统一分页 | `M` | `C` | `M` | `X` | `M` 部分：Section/Page；`G`：SectionGroup | `G`，异步 | `—`；跨位置迁移 `X` | `X` | `X`；Drive 整包删除仅测试控制面 | `X` | `C`；最近使用为 `G` | `X` |
| SectionGroup | `G` | `G` | `C` | `G` | `X` | `G`：Section/子 SectionGroup | `X` | `X` | `X` | `X` | `X` | `C` | `X` |
| Section | `M` 部分：仅 Notebook 直属入口 | `M` | `C` | `M`：Notebook 下；`G`：SectionGroup 下 | `X` | `M`：Page 增改删；页面树变形除外 | `G`，异步 | `C`：复制、验证、逻辑标记 | `X` | `X` | `X` | `C` | `X` |
| Page | `M`，暂缺统一分页 | `M`：元数据与 HTML | `C`：由 `level/order` 推导 | `M` | `M` 部分：固定追加；完整受控变更待实现 | `C`：图片/附件由 HTML 管理；子 Page 不是原生集合 | `G`，异步 | `C`：复制、验证、逻辑标记 | `X` | `M`，双开关与标题确认 | `X` | `G/C`：Graph 查询 + 本地层级筛选 | `X` |

矩阵中的 `X` 仍保留为业务需求记录：它表示用户可能需要该动作，但当前不能据此构造任意 Graph、Drive 或 UI 自动化绕路。尤其不得把 Copy 说成原地重命名，把 `copy → verify → markAsDeleted` 说成 Graph 原生 Move，或把测试控制面的 Drive 清理说成 Notebook 产品级 Delete。

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
