# OneNote 四层对象 CRUD 缺口

- 状态：探索中

## 目标

明确本项目对 Notebook、SectionGroup、Section、Page 的直接 Create、Read、Update、Delete 支持程度。子资源的创建、更新或删除归入子资源自身的 CRUD，不把它们计作父对象原地 Update；需要同时分离实现缺口与 Microsoft Graph OneNote v1.0 的平台限制，避免对“完整 CRUD”作无法兑现的承诺。

## 当前基线

| 资源 | Create | Read | Update | Delete |
| --- | --- | --- | --- | --- |
| Notebook | 已实现 | `list` 与 `get` 已实现，结构化 Query 待实现 | 稳定 v1.0 没有 PATCH | OneNote API 不支持；理论上可用 `Files.ReadWrite` 删除 Notebook 对应的 OneDrive `package` driveItem，但当前仅允许测试控制面使用 |
| SectionGroup | Graph 支持在 Notebook 或 SectionGroup 下创建，MCP 待实现 | Graph 支持 `list`、`get` 和元数据 Query，MCP 均待实现 | 稳定 v1.0 没有 PATCH、Move 或 reparent | 稳定 v1.0 没有 DELETE |
| Section | Notebook 下创建已实现；SectionGroup 下创建待实现 | Notebook 下 `list` 与按 ID `get` 已实现；根级/SectionGroup 下 List、结构化 Query、分页和父关系待实现 | 稳定 v1.0 没有 PATCH、Move 或 reparent | 没有受支持的 OneNote API；OneDrive 也没有可安全寻址为独立 driveItem 的 Section |
| Page | 已实现 | 元数据与 HTML 已实现 | 已实现固定 `append`，不是通用更新 | 已实现双开关与标题确认删除 |

当前 list 工具没有统一的 `@odata.nextLink` 处理；Page 列表默认最多返回首批结果，因此“Read 已实现”不等于大数据量下读取完整。

## 删除能力的官方边界

- Microsoft Graph v1.0 的 [`onenoteSection` 资源方法表](https://learn.microsoft.com/en-us/graph/api/resources/onenotesection?view=graph-rest-1.0) 只有读取、创建/列出 Page、复制到 Notebook 或 Section Group，没有 Section 删除方法。
- OneDrive 把整个 Notebook 表示为带有 `package.type=oneNote` 的顶层 driveItem。[`package` 文档](https://learn.microsoft.com/en-us/graph/api/resources/package?view=graph-rest-1.0)说明 package 不带 folder/file facet；[`driveItem` 文档](https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0)又规定只有 folder 才有可枚举的 `children`。因此不能通过标准 Drive 层级把 Notebook 内部 Section 可靠定位成独立 driveItem。
- 对 Notebook package 使用 [`DELETE driveItem`](https://learn.microsoft.com/en-us/graph/api/driveitem-delete?view=graph-rest-1.0) 在技术上可以把整个 Notebook 移入 OneDrive 回收站，委派权限最低为 `Files.ReadWrite`。本项目只允许显式授权的本地 pytest 控制面使用该能力，生产 MCP、Agent 配置与临时 MCP 配置仍不得请求 Files scope 或暴露 DriveItem。
- 删除 Section 的理论绕路是复制保留内容、重建 Notebook，再删除整个旧 Notebook package，或者调用 OneNote 客户端/UI；前者会更换资源 ID/链接并放大删除范围，后者不属于 Graph API。二者都不能视为受支持、可安全交付的 Section Delete。

## 待探索问题

1. 以直接对象语义定义 CRUD：Notebook、SectionGroup、Section 的子资源变化不计作父对象原地 Update；Page Update 只覆盖标题与受控内容元素，同时保留对分页完整、幂等回查、精确更新和可靠删除的质量要求。
2. 为所有集合读取设计统一分页机制，同时保持生产 Graph 客户端的 `/me/onenote/` endpoint allowlist 和脱敏错误边界。
3. 将 Page Update 从固定追加扩展到官方支持的 `append`、`prepend`、`insert`、`replace` 时，定义允许的 target、position、HTML 校验和 `includeIDs=true` 读取流程。
4. 判断 Page 标题更新应作为专用稳定工具还是受限 change-object 能力，禁止暴露任意 Graph 请求入口。
5. 在 README 和工具说明中明确：Notebook 整包删除理论上可由 OneDrive `Files.ReadWrite` 覆盖，但当前只属于测试控制面；Section 没有等价的独立 driveItem 删除路径，不得把测试专用 Drive 清理提升为产品能力。
6. 将搜索、Section Group、附件和复制等扩展能力与基础 CRUD 分开排期，避免范围混淆；Page/Section 的复制与移动边界由 [独立 TODO](page_section_copy_move.md) 跟踪。

## 验收条件

- 形成按 Notebook、SectionGroup、Section、Page 和 CRUD 动词列出的官方端点、权限、当前实现、缺口、不可实现项和测试证据矩阵。
- Graph 支持的 Page CRUD 缺口有稳定 MCP 接口、输入校验、Mock 测试、写入保护和验收方案。
- Notebook 整包删除与 Section 删除分别记录 OneDrive 可行性和限制；不得通过扩大生产 Files scope、暴露 Drive 工具或重建整个 Notebook 来伪装成安全的 Section Delete。
- 稳定结论和实施结果迁入正式文档与测试后，删除本 TODO 和索引项。

## 阶段进展

### 2026-07-29：完成能力边界初判

- 脱敏证据：检查当前 `OneNoteTools`、Graph endpoint allowlist、Mock 测试和 Microsoft Graph v1.0 方法表。
- 结论：初判采用“修改资源自身属性”的 Update 口径，因此把 Notebook/Section 记为 Create + Read；严格意义的 Page Update 仍只是追加，集合 Read 仍缺分页。该 Update 口径已在下一阶段按聚合根语义修订。
- 下一步：优先设计分页与受限 Page change-object，再决定是否把 Page 称为完整 CRUD。

### 2026-07-29：按聚合根口径修订 Update，并复核删除路径

- 脱敏证据：核对 Microsoft Graph v1.0 的 `onenoteSection`、`package`、`driveItem` 和 `DELETE driveItem` 官方文档；未进行真实账号或删除验证。
- 结论：Section Update 按“增删 Page”口径已经实现；Notebook Update 可新增 Section/Page 和删除 Page，但因缺少 Section Delete 仍是部分实现。Notebook 可理论上通过 `Files.ReadWrite` 删除对应 OneNote package；Section 没有受支持的 OneNote DELETE，也没有可通过标准 Drive children 独立寻址的 driveItem。
- 下一步：将 Section Delete 标记为当前平台约束；若未来需要重新评估，只接受微软新增稳定 API 或经过显式授权、不会扩大删除范围的官方路径，不采用重建 Notebook 的模拟删除。

### 2026-07-30：固化对象字段与读写边界设计

- 脱敏证据：核对 Graph v1.0 的 Notebook、SectionGroup、Section、Page 资源属性、relationship 和方法表，并与当前 `OneNoteTools` 返回字段对照；未进行真实账号请求。
- 结论：在 `docs/design/onenote_object_model/` 建立独立设计包，明确 `R/C/U/A/D/X` 字段能力、聚合更新语义、SectionGroup 的结构定位及原始 URL/身份字段的排除规则。只有 Page 标题和受控 HTML 元素具备创建后字段更新；Notebook、SectionGroup、Section 名称均只在创建时可写。
- 下一步：依据设计先补集合分页和父 relationship 的 Mock，再实现受限 Page change-object；实现状态不得因设计文档完成而提前标记为已支持。

### 2026-08-03：补齐对象层级的业务操作目录

- 脱敏证据：复核 Graph v1.0 的 Notebook、SectionGroup、Section、Page 资源方法表和当前 MCP 工具注册；未进行真实账号请求。
- 结论：对象模型现已把字段能力与业务操作分开描述，并用层级—操作矩阵区分当前 MCP、Graph 原生待开放、项目组合能力和平台/产品边界。Notebook、SectionGroup、Section 的查找、树、统计、复制、移动、删除、恢复、导出与共享需求不再因缺少字段写性而被遗漏，也没有被误标为已实现。
- 下一步：以矩阵中的 `M` 部分项和 `G` 项为候选路线，优先补统一分页、父 relationship、SectionGroup 读取及异步复制客户端；`X` 项继续作为明确边界，不设计通用 Graph/Drive 绕路。

### 2026-08-04：统一 CRUD 与组合操作分类

- 脱敏证据：重排对象模型总览中的操作语义表和层级—操作矩阵；未调用 Graph 或执行真实账号验证。
- 结论：操作现按 `C/R/U/D/O` 五类排列，每行只表达一个动词；Query 只查询对象元数据与 relationship，Page 正文 Search 作为独立组合操作由专门 TODO 跟踪；Get Path、Get Tree、Rename、Update Content、Move、Reparent、Reorder、Indent、Outdent、Export 和 Share 均已拆分。交付状态中的项目组合标记由 `C` 改为 `P`，避免与 Create 类别混淆。
- 下一步：后续 MCP 工具设计沿用这些单一动词和结构化 Query 契约；不得接受任意 OData 表达式或 Graph URL。正文 Search 的范围与资源预算见 `page_content_search.md`。

### 2026-08-04：同步四个对象章节的直接 CRUD 矩阵

- 脱敏证据：逐项对照 `OneNoteTools` 当前注册工具与对象模型总览，将 Notebook、SectionGroup、Section、Page 章节统一为 `C/R/U/D` 支持表；未调用 Graph 或执行真实账号验证。
- 结论：每章现已分列 Graph v1.0 支持、当前 MCP 状态和待实现项。SectionGroup 被纳入基础 CRUD 基线；Notebook、SectionGroup、Section 的子资源变化不再冒充父对象原地 Update，Page 的四种内容 change action 分行记录。
- 下一步：优先实现统一分页、SectionGroup List/Get、SectionGroup 下创建 Section、结构化 Query 与受限 Page Update，并为每项功能补 Mock。
