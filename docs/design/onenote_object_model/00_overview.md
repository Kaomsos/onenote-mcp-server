# OneNote 对象层级、字段与操作模型

## 目的与范围

本文档集定义本项目在 Microsoft Graph v1.0 上使用的 OneNote 对象模型、字段命名、业务操作、读写边界和树读取语义。生产范围固定为当前登录用户的 `/me/onenote/`，不把 Group、Site、Drive 或通用 Graph 资源纳入 MCP 数据面。

本设计区分三种事实：

1. Graph 原生对象、字段和 relationship；
2. 本项目为 MCP 返回值规范化的字段；
3. 为 Page 层级和统一路径而由本地代码推导的字段。

推导字段不得描述成 Graph 原生 relationship。

## 文档索引

- [完整层级与树读取契约](01_hierarchy_and_queries.md)
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

## 静态字段模型

### 字段能力标记

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

### 统一公共字段

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

### 字段读写结论

| 对象 | 创建时可写 | 创建后可直接更新 | 可聚合更新 | 不可写的关键字段 |
| --- | --- | --- | --- | --- |
| Notebook | `name` | 无 | 添加 Section、SectionGroup，以及经子资源改变 Page | ID、时间、默认/共享状态、角色、父关系 |
| SectionGroup | `name`、创建位置 | 无 | Graph 可添加 Section 和子 SectionGroup；当前 MCP 不开放 | ID、时间、父关系 |
| Section | `name`、创建位置 | 无 | 创建、更新、删除 Page | ID、时间、默认状态、父关系 |
| Page | `title`、HTML、目标 Section | `title` 和受控 HTML 元素 | 删除、复制 | ID、时间、`level`、`order`、推导父关系 |

Notebook、SectionGroup、Section 的 `displayName` 没有稳定更新方法；Copy 的 `renameAs` 创建副本，不是原地重命名。Page 标题可用内容 PATCH 的 `target: "title"` 与 `action: "replace"` 更新。

## 动态操作模型

### 操作交付状态

操作矩阵使用以下交付状态；它描述的是“业务需要怎样操作对象”，不能替代字段能力标记：

| 标记 | 含义 |
| --- | --- |
| `M` | 当前 MCP 已开放；若带“部分”，表示语义或完整性仍有限制 |
| `G` | 稳定 Graph v1.0 原生支持，但当前 MCP 尚未开放 |
| `P` | 需要多个 Graph 调用、本地推导或项目级状态组合，尚未形成稳定工具契约 |
| `X` | 稳定 Graph v1.0 不支持，或因本项目安全/产品边界明确不提供 |
| `—` | 对该层级不适用 |

### 操作语义与英文命名

英文标准名用于产品文案、设计文档和代码命名参考。操作依次按 `C`（Create）、`R`（Read）、`U`（Update）、`D`（Delete）和 `O`（Other，其他组合操作）排列；类别表示业务语义，不表示交付状态。代码动词统一使用小写 `snake_case`，并追加资源名，例如 `list_notebooks`、`get_section`、`create_page`。

| 类别 | 中文操作 | 英文标准名 | 建议代码动词 | 基本调用参数 | 统一语义 |
| --- | --- | --- | --- | --- | --- |
| `C` | 创建 | Create | `create_*` | `parent_id?`、`name` 或 `title`、资源特有创建内容 | 在调用者明确指定的父级或位置新建对象；返回新资源，不能表示对原对象的重命名、移动或恢复。Notebook 没有父 ID，Page 可另含 `content_html?`。 |
| `R` | 列出 | List | `list_*` | `parent_id?`、`cursor?`、`limit?` | 在指定范围读取一组同类对象。结果必须考虑分页；默认只返回直接成员，不递归读取完整后代树。 |
| `R` | 获取 | Get | `get_*` | `<resource>_id`、`include?` | 通过已确定的资源 ID 读取单个对象的元数据、必要关系或显式请求的内容；不负责按条件查找。 |
| `R` | 查询 | Query | `query_*` | 资源类型对应的范围 ID、`criteria?`、`order_by?`、`cursor?`、`limit?` | 按对象的名称、标题、时间、状态或 Graph relationship 等元数据条件返回候选集合。公开工具只接受结构化且经过校验的条件，不查询 Page 正文，也不接受任意 OData、Graph URL 或原始查询表达式。 |
| `R` | 搜索 | Search | `search_pages` | `query`、`section_id?`、`section_group_id?`、`cursor?`、`limit?` | 在明确的 Section 或 SectionGroup 范围内检索 Page 正文，只返回 Page 匹配结果。Graph 没有 OneNote Page 正文搜索端点；项目必须列出候选 Page、逐页读取 HTML 并在本地匹配。 |
| `R` | 获取路径 | Get Path | `get_*_path` | `<resource>_id` | 沿父关系读取单个对象的祖先链和规范化路径；Notebook 是根，不需要该操作。 |
| `R` | 获取树 | Get Tree | `get_*_tree` | `<resource>_id`、`max_depth?`、`include_pages?`、`limit?` | 递归读取指定对象的后代结构；可组合多个 List/Get，并可能包含 SectionGroup 递归和 Page 层级的本地推导。 |
| `U` | 重命名 | Rename | `rename_*` | `<resource>_id`、`new_name` 或 `new_title` | 保持资源身份不变并修改名称或标题；Copy 的 `renameAs` 只命名副本，不属于重命名。 |
| `U` | 更新内容 | Update Content | `update_*_content` | `<resource>_id`、`target`、`action`、`content`、`position?` | 保持资源身份不变并修改其内容；在当前对象模型中主要适用于 Page 的受控 HTML change-object。 |
| `D` | 删除 | Delete | `delete_*` | `<resource>_id`、`expected_label`、`expected_parent_id?` | 移除调用者精确确认的现有对象。逻辑标记和移入回收站不能笼统称为 Delete。 |
| `O` | 变更子级集合 | Mutate Children | 使用具体动词，如 `create_page`、`delete_page` | 明确的父资源 ID、子资源输入；破坏性动作另含确认参数 | 通过创建、更新、复制或删除子资源来改变父对象所管理的集合。它不是父对象字段 PATCH，也不设计含糊的 `manage_*` 工具。 |
| `O` | 复制 | Copy | `copy_*` | `source_id`、`target_parent_id?`、`rename_as?` | 保留源对象并创建具有新 ID 的副本；复制不是原地更新、移动、备份或恢复。 |
| `O` | 移动 | Move | `move_*` | `<resource>_id`、`target_parent_id`、`expected_label?` | 表达业务位置迁移；若使用 `copy → verify → markAsDeleted`，只能称为项目级 Logical Move。 |
| `O` | 重新挂接 | Reparent | `reparent_*` | `<resource>_id`、`target_parent_id` | 保持资源身份不变并改变直接父级；它比 Move 语义更窄，不能用 Copy 冒充。 |
| `O` | 重新排序 | Reorder | `reorder_*` | `<resource>_id`、`reference_id?`、`position` | 改变同级对象在 OneNote 中的真实先后顺序；只调整本地返回顺序不算重新排序。 |
| `O` | 缩进 | Indent | `indent_page` | `page_id`、`expected_parent_page_id?` | 增加 Page 层级，使其成为前序 Page 的后代；只适用于 Page。 |
| `O` | 取消缩进 | Outdent | `outdent_page` | `page_id`、`expected_parent_page_id?` | 减少 Page 层级，使其提升到更高层；只适用于 Page。 |
| `O` | 恢复 | Restore | `restore_*` | `deletion_ref`、`target_parent_id?`、`expected_label?` | 撤销删除并恢复原对象身份、位置和内容；重新创建同名对象或从副本创建新对象不属于恢复。 |
| `O` | 导出 | Export | `export_*` | `<resource>_id`、`format`、`destination?` | 生成可移植、可恢复的数据；复制对象或读取树快照不自动等同于导出或备份。 |
| `O` | 共享 | Share | `share_*` | `<resource>_id`、`principal`、`role` | 读取或修改协作权限；返回 Web/客户端导航链接不等同于共享管理。 |

参数名必须使用明确的资源语义，例如 `notebook_id`、`section_group_id`、`section_id`、`page_id`，不得在公开工具中只写 `id`、`parent_id` 或 `scope_id`。表中的 `<resource>_id` 只是概念占位符，`?` 表示可选参数；也不得用 `self_url`、`pages_url` 等原始 Graph URL 替代资源 ID。命名时优先使用上表动词，不混用 `read_*`、`fetch_*`、`load_*` 表示 Get，也不使用 `get_all_*` 表示 List。异步操作若拆成开始和状态查询，使用 `start_*` 与 `get_operation`；若工具内部等待完成，仍使用业务动词，例如 `copy_section`。

### 层级—操作矩阵

本矩阵按 `C → R → U → D → O` 排列，每行只表达一个操作。`G` 不等于已经注册 MCP 工具，`P` 也不等于可以安全模拟原生操作。详细语义、限制和候选组合方案见各层级分文档。

| 类别 | 操作 | Notebook | SectionGroup | Section | Page |
| --- | --- | --- | --- | --- | --- |
| `C` | 创建 | `M` | `G` | `M`：Notebook 下；`G`：SectionGroup 下 | `M` |
| `R` | 列出 | `M`，暂缺统一分页 | `G` | `M` 部分：仅 Notebook 直属入口 | `M`，暂缺统一分页 |
| `R` | 获取 | `M` | `G` | `M` | `M`：元数据与 HTML |
| `R` | 查询 | `G`；最近使用另有专用 `G` 方法 | `G` | `G` | `G`：仅元数据与 relationship |
| `R` | 搜索 | `—` | `—`：只作为 Page 搜索范围 | `—`：只作为 Page 搜索范围 | `P`：范围暂限 Section 或 SectionGroup |
| `R` | 获取路径 | `—`：树根 | `P` | `P` | `P` |
| `R` | 获取树 | `P` | `P` | `P` | `P`：由 `level/order` 推导 |
| `U` | 重命名 | `X` | `X` | `X` | `G` |
| `U` | 更新内容 | `—` | `—` | `—` | `M` 部分：固定追加；完整受控变更为 `G` |
| `D` | 删除 | `X`；Drive 整包删除仅测试控制面 | `X` | `X` | `M`：双开关与标题确认 |
| `O` | 变更子级集合 | `M` 部分：Section/Page；SectionGroup 为 `G` | `G`：Section/子 SectionGroup | `M`：Page 增改删；页面树变形除外 | `P`：图片/附件由 HTML 管理；子 Page 不是原生集合 |
| `O` | 复制 | `G`：异步 | `X` | `G`：异步 | `G`：异步 |
| `O` | 移动 | `X`：跨位置迁移 | `X` | `P`：复制、验证、逻辑标记 | `P`：复制、验证、逻辑标记 |
| `O` | 重新挂接 | `—`：树根 | `X` | `X` | `X` |
| `O` | 重新排序 | `X` | `X` | `X` | `X` |
| `O` | 缩进 | `—` | `—` | `—` | `X` |
| `O` | 取消缩进 | `—` | `—` | `—` | `X` |
| `O` | 恢复 | `X` | `X` | `X` | `X` |
| `O` | 导出 | `X` | `X` | `X` | `X` |
| `O` | 共享 | `X` | `X` | `X` | `X` |

### 操作边界结论

矩阵中的 `X` 仍保留为业务需求记录：它表示用户可能需要该动作，但当前不能据此构造任意 Graph、Drive 或 UI 自动化绕路。尤其不得把 Copy 说成原地重命名，把 `copy → verify → markAsDeleted` 说成 Graph 原生 Move，或把测试控制面的 Drive 清理说成 Notebook 产品级 Delete。

### Query 与 Search 边界

Query 查询对象本身：Notebook、SectionGroup、Section、Page 都可以依据 Graph 暴露的元数据和 relationship 使用 OData 条件、排序、投影与分页。Query 不读取 Page HTML；标题属于 Page 元数据，因此按标题查询仍是 Query。

Search 检索 Page 正文：它只属于 Page 层级，Section 和 SectionGroup 仅用于限定候选 Page 的范围，不因此获得独立的正文 Search 操作。稳定 Graph v1.0 没有 OneNote Page 正文搜索端点，也没有可用于 Page HTML 的 `$search`；本项目只能组合 List/Get Content 后在本地匹配纯文本。

Search 首期只考虑以下两种互斥范围：

- `section_id`：分页列出该 Section 的 Page，逐页读取正文并匹配；
- `section_group_id`：递归列出该 SectionGroup 的全部后代 Section，再对每个 Section 执行上述 Page 扫描。

暂不提供 Notebook 或全局正文 Search。按需扫描整个 Notebook 或账号会把一次 MCP 调用放大为大量 Page 内容请求；若以后需要全局搜索，应单独设计显式启用、可清除且不会明文持久化正文的本地索引，而不是把有界扫描伪装成完整搜索。

#### Search 候选 Page 硬限制

Search 必须先完成只读预检，只枚举候选 Page 元数据并计数，不读取任何 Page HTML。候选数大于服务端配置 `ONENOTE_SEARCH_MAX_PAGES` 时立即拒绝，返回固定错误码 `search_scope_too_large`；默认值建议为 `100`。配置必须是正整数，并由启动时的 `Settings` 校验；无效值应令服务启动失败，不能静默回退为无限制。

预检最多枚举到“阈值 + 1”个 Page 即可判定超限，不需要为了报告精确总数继续遍历。只有候选集合不超过阈值，才允许进入正文读取阶段。公开 `search_pages` 参数不得提供提高该阈值的选项；若以后允许调用者提交更小的单次预算，也只能取调用值与服务端阈值的较小者。

SectionGroup Search 应对全部后代 Section 共享同一个 Page 总预算，不能按每个 Section 分别重置阈值。递归或分页过程中一旦累计候选超过阈值，必须停止且不得返回部分匹配结果，以免调用者把被截断结果误认为完整搜索。

#### Search 范围限制与隐患

- Graph 不执行正文匹配。Section 搜索至少产生一次 Page 集合分页和每个候选 Page 一次内容请求；SectionGroup 还会递归放大为 SectionGroup、Section、Page 三层读取。
- Page 数阈值只是请求放大的第一道硬门，不能替代 SectionGroup 深度、节点数、单 Page 字节数、总响应字节数、并发数和总耗时限制；这些预算都应由服务端配置或硬编码上限控制。
- 所有集合分页完成前不能声称结果完整。候选 Page 预检超限属于硬拒绝，不返回匹配或续传游标；预检通过后若因字节数、时间或其他可续传预算中止，才返回 `complete=false`、`has_more=true` 和不透明 `next_cursor`。零匹配且 `complete=false` 不等于没有结果。
- SectionGroup 递归必须限制深度和节点数，并检测循环、父关系缺失和分页异常；任何结构不完整都应安全失败或明确返回不完整状态。
- 搜索期间 Page 可能新增、修改、移动或删除，因此结果不是事务快照。网络错误或限流后不得盲目从头重扫并合并为“完整结果”。
- 首期只匹配从 Page HTML 提取的可见文本和标题，不承诺图片 OCR、手写识别、音视频转写或附件正文；`previewText` 也只是短摘要，不能替代完整正文。
- 搜索结果只返回必要元数据、有限长度纯文本片段和匹配位置，不返回原始 HTML；查询词、正文、片段和 Graph 原始响应均不得写入日志。
- `search_pages` 必须且只能接收 `section_id` 或 `section_group_id` 之一。公开参数不得接受任意 Graph URL、原始 `nextLink`、OData 表达式或调用者自定扫描上限来绕过服务端硬限制。

## 安全与兼容原则

- 不返回 `createdBy`、`lastModifiedBy` 或其他账号身份字段。
- 不把 Graph 原始响应体、认证材料或账号资料写入日志、文档或 MCP 错误。
- `self`、`sectionsUrl`、`sectionGroupsUrl`、`pagesUrl`、`contentUrl` 不是调用授权；HTTP 层必须使用资源 ID 和 `/me/onenote/` allowlist 构造请求。
- 当前工具已有的 `sections_url`、`pages_url`、`content_url` 可暂时兼容，但新树和路径接口不得依赖这些 URL。
- Page HTML 只由显式内容工具返回，List、Search、Get Path 和 Get Tree 不得默认返回完整 HTML。
- 生产 MCP 不请求 `Files.ReadWrite`，不通过 Drive 模拟 Notebook 或 Section 产品级 CRUD。

## 当前实现差距

当前 `onenote_mcp/tools.py` 只映射：

- Notebook：`id`、`name`、`created`、`modified`；精确读取额外返回 `sections_url`；
- Section：`id`、`name`、`created`、`modified`；精确读取额外返回 `pages_url`；
- Page：`id`、`title`、`created`、`modified`、`content_url`，以及独立 HTML 读取；
- SectionGroup：尚未实现。

目标模型还需补充父 relationship、SectionGroup、`pagelevel=true`、分页完成性以及 Page 本地树推导。本文档只固定设计，不表示这些字段已经由 MCP 工具实现。
