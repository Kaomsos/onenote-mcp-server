# 本地 OneNote COM MCP 调研与 Graph 路线互补评估

## 文档目的

本文记录截至 2026-08-04 对两个 Windows 本地 OneNote MCP 项目的静态调研，并评估 OneNote Win32 COM 技术路线能否补全 [对象模型总览](../design/onenote_object_model/00_overview.md) 中由 Microsoft Graph v1.0 留下的操作缺口。

本文所说的“COM 可支持”不等于当前 Graph MCP 已支持，也不等于被调研项目已经公开相应工具。能力结论分为三层：

- **项目已开放**：参考项目已有明确 MCP 工具；
- **COM 原生**：微软 OneNote Application 接口明确记录该能力；
- **组合或待验证**：可由 XML、创建、复制内容和删除等步骤推导，但没有等价的单一 COM 方法，必须在隔离 Notebook 中验证完整性和失败处置。

## 调研对象

### Peteroooooooo/local-onenote-mcp

仓库：[Peteroooooooo/local-onenote-mcp](https://github.com/Peteroooooooo/local-onenote-mcp)，调研分支为 `main`。

这是两个项目中操作面更完整的实现。它使用 PowerShell 作为 `OneNote.Application` COM 桥，所有读写都交给 OneNote 桌面客户端，不直接修改 `.one` 文件。公开工具超过 30 个，主要能力包括：

- 列出完整层级、Notebook、Section 和 Page，读取 Page 文本、解析结果、原始 XML、页面对象和二进制内容；
- 在已打开的本地 Notebook 中搜索 Page 正文，可选择使用索引或包含未索引 Page；
- 创建 Notebook、SectionGroup、Section 和 Page；
- 更新 Page 标题，追加或替换 Page 正文，添加图片，删除 Page 内对象；
- 删除层级对象、更新 Page XML 和层级 XML；
- 导出、导航、同步、关闭 Notebook、合并 Section 和设置归档位置。

运行要求是 Windows 10/11、传统 Win32 OneNote 桌面应用而非旧版 OneNote for Windows 10 UWP、Python 3.11+；OneMore 只是 Markdown 富格式转换的可选依赖。

它最适合作为“COM 能力上限”的参考，但公开 `update_hierarchy_xml`、`update_page_xml` 和 `delete_hierarchy` 给 Agent 的接口过于宽泛。本项目若采用 COM，仍应把原始 XML 封装成单一业务动词、完整读取后修改、并发校验和回读验证，不应照搬任意 XML 写入口。

### wgthomas/onenote-mcp

仓库：[wgthomas/onenote-mcp](https://github.com/wgthomas/onenote-mcp)，调研分支为 `master`；公开工具实现见 [`onenote_mcp.py`](https://github.com/wgthomas/onenote-mcp/blob/master/onenote_mcp.py)，COM 桥见 [`com_client.py`](https://github.com/wgthomas/onenote-mcp/blob/master/onenote_lib/com_client.py)。

该项目公开 13 个工具，定位是只读、搜索和图像理解增强，而不是完整 CRUD：

- 列出 Notebook、递归列出 Notebook 下的 Section、列出 Section 下的 Page，并获取 Notebook 树；
- 将 Page 转为 Markdown，读取原始 XML，提取单张或多张图片为 MCP Image；
- 在全部已打开 Notebook 或单个 Notebook 中全文搜索；
- 可选调用 OpenAI-compatible vision endpoint 分析 Page 图片；
- 唯一公开写操作是创建包含 HTML 的 Page。

其底层 COM 客户端还实现了导航、打开层级和删除层级，但没有注册成 MCP 工具，因此不能计为产品支持。它要求 Windows、已安装并运行 OneNote 桌面应用和 Python 3.11+。

这个项目最值得借鉴的是“Page XML/图片 → Markdown 与 MCP Image”的读取体验。需要避免照搬的实现包括临时文件明文保存 XML、`tempfile.mktemp()` 的竞态风险、错误中返回原始 stderr、无写入保护的 Page 创建，以及把图片发送到可配置远程视觉服务时缺少清晰的数据外发边界。

### 两个项目的公开能力对照

下表只统计公开 MCP 工具，不把底层私有函数或理论上的 COM 能力算成已交付。

| 对象模型操作 | Peter 项目 | wgthomas 项目 |
| --- | --- | --- |
| 创建 | Notebook、SectionGroup、Section、Page | Page |
| 列出/获取树 | 完整层级及四层遍历 | Notebook、递归 Section、Page、Notebook 树 |
| 获取 Page | 文本、解析数据、XML、对象、二进制 | Markdown、XML、图片 |
| Query 元数据 | 未提供受约束的结构化 Query；可读取层级后本地筛选 | 未提供结构化 Query |
| Search 正文 | 所有已打开 Notebook，可包含未索引 Page | 所有已打开 Notebook 或单个 Notebook，索引搜索 |
| 重命名/更新 | Page 标题和正文；另有原始层级/Page XML | 无更新；仅新建 Page |
| 删除 | SectionGroup、Section、Page；另有 Page 内对象删除 | 未公开 |
| 复制 | 未提供高层 Copy 工具 | 未提供 |
| 移动/重挂接/排序 | 仅公开 `merge_sections` 与原始层级 XML，未形成高层工具 | 未提供 |
| 导出/客户端控制 | 导出、导航、同步、关闭 Notebook | 未公开 |
| 图像理解 | 获取二进制对象 | MCP Image 与可选视觉模型分析 |

### OneNote 与 Windows 兼容范围

微软把 COM 文档归在 OneNote 2013 Win32 桌面对象模型下，并明确说明它面向本地、未连接场景；这不是 OneNote for Windows 10 UWP 的接口。两个参考项目都只支持 Windows 桌面 OneNote：Peter 项目明确要求 Windows 10/11 和传统桌面版，wgthomas 项目要求 Windows 且 OneNote 桌面应用已安装并运行。

对 Microsoft 365 当前桌面 OneNote，最可靠的兼容判定不是营销版本名，而是当前用户会话能否实例化 `OneNote.Application` 并完成一次只读层级调用。静态调研不能据此承诺所有 OneNote 2010/2013/2016 永久版、企业定制安装或 Click-to-Run build 都兼容；正式 adapter 应在启动时执行 COM 注册、架构版本和只读 `GetHierarchy` 健康检查，并在不兼容时安全关闭 COM 工具。

## COM 相比 Graph API 的产品优势

### 原生正文搜索，范围更广且请求放大更小

微软的 [`FindPages`](https://learn.microsoft.com/zh-cn/office/client-developer/onenote/application-interface-onenote#findpages-%E6%96%B9%E6%B3%95) 接受根、Notebook、SectionGroup 或 Section 作为起始节点，并允许选择是否包含尚未被 Windows Search 索引的 Page。它返回命中 Page 及祖先路径，不需要 MCP 枚举全部候选 Page 再逐页下载 HTML。

这能直接覆盖：

- 所有已打开本地 Notebook 的全局正文 Search；
- Notebook、SectionGroup 或 Section 范围 Search；
- 索引优先搜索，以及包含未索引 Page 的较慢搜索。

Graph v1.0 没有 OneNote Page 正文搜索端点。本项目当前 Graph 设计只能在 Section 或 SectionGroup 中先枚举候选 Page，超过阈值即拦截，再逐页读取 HTML 并本地匹配。COM 因而不仅增加全局范围，还避免把一次搜索放大成大量 Graph 内容请求。COM 工具仍应设置最大结果数、总耗时和输出片段上限，但无需沿用“候选 Page 超阈值就完全不能搜索”的同一限制模型。

### 能修改真实层级，而不仅是云端资源字段

微软 [`UpdateHierarchy`](https://learn.microsoft.com/zh-cn/office/client-developer/onenote/application-interface-onenote#updatehierarchy-%E6%96%B9%E6%B3%95) 的官方说明明确包含：

- 新增 Notebook、SectionGroup、Section 和 Page；
- 在一个 Notebook 内移动 Section；
- 保持 Section ID 不变并重命名 Section；
- 改变一个 Section 内 Page 的真实顺序；
- 控制新 Page 的插入位置，并在创建时建立子 Page。

Graph 中 `level` 和 `order` 是只读字段，Notebook、SectionGroup、Section 也没有稳定 PATCH 或 Move。COM 直接操作 OneNote 客户端的层级 XML，因此有机会保留对象 ID 完成真实层级变更，而不是一律使用“复制后逻辑标记”的替代语义。

但 `UpdateHierarchy` 对不完整且有歧义的 XML 可能自行推断未列出的节点位置。安全实现必须先读取目标父级的完整同级列表，构造无歧义的最小变更，写入后重新读取并验证 ID、父级和顺序；不能把任意 XML 直接暴露给 Agent。

### 本地 CRUD 与内容对象更完整

[`DeleteHierarchy`](https://learn.microsoft.com/zh-cn/office/client-developer/onenote/application-interface-onenote#deletehierarchy-%E6%96%B9%E6%B3%95) 原生删除 SectionGroup、Section 或 Page，默认移入对应 Notebook 的 OneNote 回收站，并支持期望修改时间校验；Graph 只提供 Page 删除。Notebook 不在该方法支持范围内，`CloseNotebook` 只是关闭，不是删除。

Page 内容方面，COM 可以读取和更新完整 OneNote XML，并通过 callback ID 读取图像、墨迹等二进制对象。它能表达 Page 内对象位置、图像、墨迹和删除单个对象等 Graph HTML change-object 不便完整覆盖的操作。

### 离线、低认证摩擦和桌面联动

COM 面向当前 Windows 用户已打开的本地 OneNote 数据，不需要 Azure App Registration、OAuth scope 或网络可用性，还能导航到具体对象、触发同步、关闭 Notebook、调用与桌面 UI 一致的 Section 合并和发布功能。

这类能力非常适合单机个人知识库和离线 Agent，但不能替代 Graph 的跨平台、远程服务、云端授权与多用户协作模型。COM 的“本地”边界也只覆盖 MCP 与 OneNote 之间；若再调用远程视觉模型，图片仍可能离开本机。

## 对 `00_overview.md` 操作缺口的原理评估

### 评估标记

| 标记 | 含义 |
| --- | --- |
| `A` | 微软 OneNote COM Application 接口明确记录的原生能力 |
| `C` | 可通过多个 COM 操作组合，但会产生新 ID、存在保真或失败处置问题 |
| `V` | XML 模型显示有实现路径，但官方说明不足以保证目标语义，必须隔离验证 |
| `X` | 未发现受支持的 COM 方法，或只可由 UI/文件系统绕路，不应承诺 |
| `—` | 不适用，或 Graph 已有更可靠的原生方案且 COM 没有补缺价值 |

### 缺口矩阵

| 操作 | Notebook | SectionGroup | Section | Page | 结论 |
| --- | --- | --- | --- | --- | --- |
| 创建 | `A` | `A` | `A` | `A` | 可补 Graph MCP 尚未开放的 SectionGroup 创建，并统一覆盖四层本地对象。 |
| 获取路径/树 | `A` | `A` | `A` | `A` | `GetHierarchy` 与 `GetHierarchyParent` 原生返回完整本地层级；Page 父子仍由顺序和 `pageLevel` 解释。 |
| Query | `C` | `C` | `C` | `C` | 读取层级 XML 后进行受约束本地筛选；不是 OData，也不应暴露任意 XPath。 |
| Search 正文 | `—` | 作为范围 `A` | 作为范围 `A` | `A` | `FindPages` 还能以根或 Notebook 为范围，明显强于 Graph 的逐页扫描方案。 |
| 重命名 | `V` | `V` | `A` | `A` | Section 保持 ID 重命名有官方示例；Notebook/SectionGroup 同属层级 XML，但需验证各存储类型与同步行为。 |
| 更新 Page 内容 | `—` | `—` | `—` | `A` | 可更新完整 Page XML、移动页面内对象并处理图片、墨迹等二进制内容。 |
| 删除 | `X` | `A` | `A` | `A` | 默认可进 OneNote 回收站；Notebook 只能关闭，不能把关闭称为删除。 |
| 复制 | `C` | `C` | `C` | `C` | COM 没有通用 Copy 方法。Page 可“新建目标 Page + 复制 XML/二进制”；上层对象只能递归重建。Graph 对 Notebook、Section、Page 的原生 Copy 仍更可靠。 |
| 移动 | `X` | `V` | `A`：同一 Notebook | `C`：跨 Section | Section 同 Notebook 移动是官方能力；Page 跨 Section 可复制、验证、回收源 Page，但会换 ID，不是原生 Move。 |
| 重新排序 | `—` | `V` | `V` | `A` | Page 顺序是官方明确能力；Section 可借完整层级 XML 调整位置，但需验证；SectionGroup 排序证据不足。 |
| 缩进/取消缩进 | `—` | `—` | `—` | `V` | 官方明确可在创建时建立子 Page，但没有明确保证对既有 Page 执行双向层级调整；应先验证 ID、子树和相邻 Page 行为。 |
| 导出 | `A` | `V` | `A` | `A` | `Publish` 支持 PDF、HTML、MHTML、Word、`.one`、`.onepkg` 等格式；SectionGroup 作为独立导出范围需验证。 |

## 复制、移动和排序的专项结论

### 复制：COM 不是 Graph 原生 Copy 的替代品

OneNote Application 接口没有通用的 `CopyPage`、`CopySection` 或 `CopySectionGroup`。COM 可组合 Page 复制：读取源 Page 的 XML 和二进制对象，在目标 Section 创建新 Page，保留新 Page ID 后写入内容，再逐项回读验证。Section、SectionGroup 和 Notebook 只能继续递归创建并复制后代。

这类复制存在三个产品语义限制：

1. 副本必然使用新 ID，原链接、内部引用、历史和部分对象标识不能假设保留；
2. 图片、墨迹、附件、嵌入对象、子 Page、Page 顺序及内部链接需要逐类验证，不能仅比较标题和纯文本；
3. 中途失败会留下部分副本，需要事务记录和可追踪清理，不能盲目重试整个复制。

因此，Graph 已原生支持的 Notebook、Section 和 Page Copy 应继续优先走 Graph 的异步复制端点。COM 的主要补充价值是本地/离线复制实验，以及对 Graph 不支持的 SectionGroup 复制做受限组合，但后者在完成保真测试前不应作为稳定工具。

### 移动：Section 是最大增益，Page 仍需区分真实移动与重建

`UpdateHierarchy` 明确支持在同一个 Notebook 内移动 Section。原则上这是保持 Section ID 的真实位置变更，能补上 Graph 的 Section Move 缺口，也是 COM 路线最有价值的写能力之一。

需要分别验证以下转换，不能用一次成功概括全部 Move：

- Notebook 直属 Section → 同 Notebook 的 SectionGroup；
- SectionGroup → 同 Notebook 根；
- 一个 SectionGroup → 另一个 SectionGroup，包括嵌套组；
- 同一父级内只改变 Section 的相对位置。

跨 Notebook Section Move 不在官方表述范围内。`MergeSections` 是把一个 Section 的内容合并进另一个 Section，与桌面“合并到另一个节”一致；它会改变 Section 边界，不能冒充保留源 Section 身份的 Move。

Page 跨 Section 没有已确认的原生 COM Move。可以采用 `copy → verify → DeleteHierarchy(deletePermanently=false)`，使源 Page 进入 OneNote 回收站，但目标 Page 使用新 ID。这比当前 Graph 设计的逻辑墓碑更接近用户可见移动，却仍只能命名为重建式 Move，且必须启用独立删除开关和精确确认。

### 排序：Page 可原生补全，Section 次之，SectionGroup 尚不可靠

`UpdateHierarchy` 明确支持改变 Section 内 Page 顺序，因此 `reorder_page` 原理上可成为保留 Page ID 的原生 COM 操作。安全接口应使用 `page_id + reference_page_id + before/after`，服务端读取完整 Page 序列后生成 XML；不要让调用者提交数字索引或原始 XML。

Section 的位置由层级 XML 中的节点顺序表达，官方也允许插入 Section 到指定位置并在 Notebook 内移动 Section，因此 `reorder_section` 具有较高可行性，但仍应在不同父级和同步型 Notebook 上验证。微软明确警告不完整 XML 的顺序可能被自行推断，所以必须提交无歧义的完整同级序列并回读。

SectionGroup 的移动和排序没有同等级的官方文字保证，只能保持 `V`。Page 缩进/取消缩进也不能仅因 XML 存在 `pageLevel` 就直接标为支持；官方只明确了创建子 Page，既有 Page 与整棵子树的层级变更仍需 live 测试。

## 建议的产品架构

COM 不应直接替换当前 Graph 后端。更合适的是保留统一对象模型，在其下增加可选 `graph` 与 `windows_com` adapter，并让每个工具按能力协商选择后端：

- Graph 继续负责跨平台、远程、云端稳定 CRUD 和原生异步 Copy；
- COM 负责本地全文搜索、层级移动/排序、SectionGroup/Section 删除、完整 Page 对象读写、导出和桌面联动；
- 同一工具结果必须标明 `backend`，ID 只在对应后端和当前 OneNote 上下文内使用，不假设 Graph ID 与 COM ID 可互换；
- COM 写操作沿用默认关闭的写入开关；删除继续使用独立删除开关、期望标签/父级和修改时间校验；
- 原始 XML 只存在于 adapter 内部，不作为 MCP 参数或默认结果；
- 所有层级变更执行“完整读取 → 构造无歧义变更 → 写入 → 回读验证”，失败时返回固定脱敏错误码。

优先级建议是：

1. 先做只读 COM adapter：Get Tree、Get Path、Section/SectionGroup 范围及全局 Search；
2. 再做低风险、官方明确的 `reorder_page` 和同 Notebook `move_section`，仅针对唯一命名测试 Notebook 验证；
3. 然后评估 SectionGroup/Section/Page 的回收站删除和 `reorder_section`；
4. 最后才考虑组合式 Copy、跨 Section Page Move、既有 Page 缩进/取消缩进；
5. 不规划 Notebook Delete，除非微软提供稳定接口。

## 本机可行性结论

2026-08-04 已在普通用户 PowerShell 会话中成功执行 `New-Object -ComObject OneNote.Application` 并释放对象，返回 `COM_OK`。本机为 Windows 11，安装的是 Microsoft 365 Win32 桌面 OneNote，而非旧 UWP 应用，因此已经满足 COM adapter 的关键运行前提。

该验证只证明 COM 可实例化，没有执行读取、写入、移动、删除或真实 Notebook 操作。任何写能力仍须按照项目的 live 授权和隔离测试要求单独验证。

## 主要资料

- [OneNote Application interface](https://learn.microsoft.com/zh-cn/office/client-developer/onenote/application-interface-onenote)
- [OneNote developer reference](https://learn.microsoft.com/en-us/office/client-developer/onenote/onenote-developer-reference)
- [Peteroooooooo/local-onenote-mcp](https://github.com/Peteroooooooo/local-onenote-mcp)
- [wgthomas/onenote-mcp](https://github.com/wgthomas/onenote-mcp)
