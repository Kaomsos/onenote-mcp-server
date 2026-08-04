# Merge Agent Handler OneNote 工具调研

## 调研范围与证据

- 调研日期：2026-08-04。
- 主要来源：[Merge OneNote connector 页面](https://www.merge.dev/connectors/onenote)、[Merge Agent Handler 概览](https://docs.merge.dev/merge-agent-handler/overview)，以及 Microsoft Graph v1.0 的 [OneNote 读取与 OData 查询说明](https://learn.microsoft.com/en-us/graph/onenote-get-content)、[Notebook](https://learn.microsoft.com/en-us/graph/api/resources/notebook?view=graph-rest-1.0)、[SectionGroup](https://learn.microsoft.com/en-us/graph/api/resources/sectiongroup?view=graph-rest-1.0)、[Section](https://learn.microsoft.com/en-us/graph/api/resources/onenotesection?view=graph-rest-1.0)、[Page](https://learn.microsoft.com/en-us/graph/api/resources/page?view=graph-rest-1.0) 资源方法表。
- 范围：仅整理公开页面列出的工具名称和说明，并按本项目 [OneNote 对象模型总览](../design/onenote_object_model/00_overview.md) 的对象层级和 `C/R/U/D/O` 分类映射。
- 限制：未登录 Merge、未调用其 MCP、未检查隐藏工具、实际输入 schema、权限模型实现或运行效果。因而“未列出”只表示公开页面没有给出该能力，不能证明 Merge 产品或 Graph 不支持。

## 产品形态差异

Merge 的 OneNote connector 是其云端 Agent Handler 平台中的一个远程 MCP connector。公开资料称：工具通过 Tool Pack 按 Agent 或用户范围配置，认证可按终端用户或 Group 管理，并对每次调用提供 DLP 检查、日志和审计能力。

本项目是本机运行、直接面向当前用户 `/me/onenote/` 的 MCP 服务。两者不应简单比较为“工具数量多少”：Merge 的 Tool Pack、托管 OAuth、DLP 与集中审计属于平台层；本项目的 Device Code Flow、平台加密缓存、最小 scope、双开关和删除前确认属于本地数据面安全边界。

特别是，Merge 公开说明会记录调用参数和结果元数据；本项目不得因此记录 Page 正文、查询词、原始 Graph 响应或认证材料。平台可观测性模式可作为“按工具最小授权”的产品参考，但不能改变本项目的脱敏日志约束。

## Merge 层级—操作矩阵

此矩阵复刻对象模型总览的行列结构，但只表示 Merge 公开目录能证明的能力，而不是本项目实现状态。

| 标记 | 含义 |
| --- | --- |
| `✓` | 公开页面列出对应的独立 Merge 工具，且可映射到 Graph v1.0 方法或查询能力。 |
| `△` | 没有独立工具；由已列工具组合、局部参数能力或 Merge 产品逻辑实现。公开信息不足以证明完整语义。 |
| `?` | 公开页面未给出工具或参数证据；不等于 Graph 或 Merge 一定不支持。 |
| `X` | Graph v1.0 本身不支持，或不能作为该对象的原地操作。 |
| `—` | 对该层级不适用。 |

| 类别 | 操作 | Notebook | SectionGroup | Section | Page |
| --- | --- | --- | --- | --- | --- |
| `C` | 创建 | `✓ create_notebook` | `✓ create_section_group`：仅公开 Notebook 父级 | `✓ create_section`：Notebook 或 SectionGroup 父级 | `✓ create_page`：Section 父级 |
| `R` | 列出 | `✓ list_notebooks`：分页、排序、过滤、展开 | `✓ list_section_groups`：全部或按 Notebook | `✓ list_sections`：全部、Notebook 或 SectionGroup | `✓ list_pages`：仅 Section 范围 |
| `R` | 获取 | `✓ get_notebook` | `✓ get_section_group` | `✓ get_section` | `✓ get_page`；`✓ get_page_content` 为显式正文读取 |
| `R` | 查询 | `△`：`list_notebooks` 暴露 OData filter/orderby | `△`：仅公开父 Notebook 筛选 | `△`：仅公开父级筛选 | `?`：页面公开说明只有 Section 范围 List |
| `R` | 搜索 | `—` | `—`：仅能成为 Page Search 范围 | `—`：仅能成为 Page Search 范围 | `?`：未列出正文 Search |
| `R` | 获取路径 | `—`：树根 | `?`：无独立工具 | `?`：无独立工具 | `?`：无独立工具 |
| `R` | 获取树 | `△`：Get/List 可展开直接子关系，不等于完整递归树 | `△`：可展开直接 Section/SectionGroup，不等于完整递归树 | `△`：可展开 Page，不等于层级树 | `?`：未公开 `pagelevel` 或子 Page 树工具 |
| `U` | 重命名 | `X`：Graph 无 PATCH | `X`：Graph 无 PATCH | `X`：Graph 无 PATCH | `△`：可能经 `update_page` 的 title replace；公开说明未明确 title target |
| `U` | 更新内容 | `—` | `—` | `—` | `✓ update_page`：公开列出 append/replace/prepend/insert；合法 target/action 组合见下文限制 |
| `D` | 删除 | `X`：Graph OneNote API 无 DELETE | `X`：Graph 无 DELETE | `X`：Graph 无 DELETE | `✓ delete_page` |
| `O` | 变更子级集合 | `✓`：通过创建 Section/SectionGroup | `✓`：通过创建 Section；嵌套 Group 未公开 | `✓`：通过创建、更新、删除 Page | `—`：Page 没有原生子 Page relationship |
| `O` | 复制 | `✓ copy_notebook`：异步 | `X`：Graph 无 SectionGroup Copy | `✓ copy_section_to_notebook`、`copy_section_to_section_group`：异步 | `✓ copy_page`：异步到 Section |
| `O` | 移动 | `X` | `X` | `X`：Copy 不是 Move | `X`：Copy 不是 Move |
| `O` | 重新排序 | `X` | `X` | `X` | `X`：`order` 只读 |
| `O` | 缩进 | `—` | `—` | `—` | `X`：`level` 只读 |
| `O` | 取消缩进 | `—` | `—` | `—` | `X`：`level` 只读 |
| `O` | 导出 | `X` | `X` | `X` | `X` |

矩阵中的 `X` 是 Graph v1.0 对对象操作的边界，不能用 Copy、UI 自动化或 Drive 删除伪装为同义操作。`?` 只说明 Merge 的公开页面未给足证据；后续若取得其实际 schema 或受控测试结果，应把 `?` 改为明确结论。

## 按对象层级梳理的公开工具

下表的“类别”沿用总览：`C` 创建、`R` 读取、`U` 更新、`D` 删除、`O` 其他组合操作。名称保留 Merge 公开名称；“映射说明”描述它在本项目对象模型中的归属，并非本项目已实现状态。

### Notebook

| 类别 | Merge 工具 | 公开说明摘要 | 对象模型映射 |
| --- | --- | --- | --- |
| `R` | `list_notebooks` | 列出 Notebook；支持 `top`/`skip` 分页、`orderby`、OData `filter`，可展开 `sections` 或 `sectionGroups`。 | List 与 Query 的混合入口；本项目应保持 List、Query 分离，并只接受结构化条件和不透明游标。 |
| `R` | `get_notebook` | 按 ID 获取，可展开 `sections` 或 `sectionGroups`。 | Get Notebook；子关系展开不等同于完整树读取。 |
| `R` | `get_recent_notebooks` | 获取最近访问的 Notebook，包含他人共享给当前用户的 Notebook。 | 专用 Read；不等同于完整 List 或 Query。 |
| `R` | `get_default_notebook` | 获取默认 Notebook；没有默认标记时返回第一个。 | 专用 Read；“第一个”是产品回退策略，不能视为 Graph 默认属性。 |
| `C` | `create_notebook` | 用唯一 `displayName` 创建 Notebook，最长 128 字符。 | Create Notebook。 |
| `O` | `copy_notebook` | 异步复制，返回 operation URL 供轮询。 | Copy Notebook；应拆成受限启动与状态读取，不能把 operation URL 暴露为调用授权。 |

公开页面没有列出 Notebook 的原地更新、重命名或删除工具；这与总览中稳定 Graph v1.0 没有 Notebook PATCH/OneNote DELETE 的边界一致。

### SectionGroup

| 类别 | Merge 工具 | 公开说明摘要 | 对象模型映射 |
| --- | --- | --- | --- |
| `R` | `list_section_groups` | 可按 Notebook 过滤，省略过滤时列出所有 SectionGroup。 | List SectionGroup；需要区分根级 List、Notebook 的直接子组 List 与递归 Get Tree。 |
| `R` | `get_section_group` | 按 ID 获取，可展开 `sections` 或 `sectionGroups`。 | Get SectionGroup；展开子项不替代完整树或路径读取。 |
| `C` | `create_section_group` | 在 Notebook 下创建 SectionGroup。 | Create SectionGroup；公开说明未覆盖“在 SectionGroup 下创建嵌套 SectionGroup”。 |

公开页面没有列出 SectionGroup 的更新、删除或复制工具。这不能证明平台完全没有其他能力，但没有改变本项目将这些动作标记为 Graph/产品边界的结论。

### Section

| 类别 | Merge 工具 | 公开说明摘要 | 对象模型映射 |
| --- | --- | --- | --- |
| `R` | `list_sections` | 可按 `notebookid` 或 `sectiongroupid` 过滤，省略两者时列出全部 Section。 | 分别覆盖根级、Notebook 下和 SectionGroup 下的 List；不是单一含糊的“列出 Section”。 |
| `R` | `get_section` | 按 ID 获取，可展开 `pages` 或 `parentNotebook`。 | Get Section；需要补齐可选父 SectionGroup 的规范化关系。 |
| `C` | `create_section` | 在 Notebook 或 SectionGroup 下创建，二者择一。 | 两个独立 Create 场景：`create_section_in_notebook` 与 `create_section_in_section_group`。 |
| `O` | `copy_section_to_notebook` | 异步复制到 Notebook，返回 operation URL。 | Copy Section to Notebook。 |
| `O` | `copy_section_to_section_group` | 异步复制到 SectionGroup，返回 operation URL。 | Copy Section to SectionGroup。 |

Merge 的“在两类父级下创建、在三类范围内列出”与本项目总览的 Section 矩阵一致，适合用来验证工具拆分粒度；但不能采用任意筛选参数或 operation URL 透传。

### Page

| 类别 | Merge 工具 | 公开说明摘要 | 对象模型映射 |
| --- | --- | --- | --- |
| `R` | `list_pages` | 只接受 Section ID；公开页面说明全局列出可能失败，因性能原因始终要求范围。 | List Page in Section；与本项目“有界读取优先”一致。 |
| `R` | `get_page` | 按 ID 获取元数据，不含正文。 | Get Page Metadata。 |
| `R` | `get_page_content` | 获取 HTML；可用 `includeids=true` 取得 PATCH 所需元素 `data-id`。 | Get Page Content；元素更新前的显式读取。 |
| `C` | `create_page` | 在 Section 中创建带 HTML 的 Page，标题成为页面标题。 | Create Page。 |
| `U` | `update_page` | PATCH change-object：`target` 为 `body` 或元素 ID，`action` 为 `append`、`replace`、`prepend`、`insert`，内容为 HTML。 | Page 的 Rename/Update Content 基础；本项目应分别建模四种 action，并限制 target、position 与 HTML。 |
| `D` | `delete_page` | 永久删除且不可撤销。 | Delete Page；本项目必须继续保留写入开关、删除开关、标题确认与删除前回读，不能只按该说明放宽。 |
| `O` | `copy_page` | 异步复制到其他 Section，返回 operation URL。 | Copy Page to Section。 |

公开页面未列出 `search_pages`。这符合本项目将正文 Search 作为 Page 层级的本地组合能力，而非 Graph 原生工具的设计；不能将“未列出”理解为 Merge 一定没有内容搜索。

### 认证与平台级工具

| 类别 | Merge 工具或机制 | 公开说明摘要 | 本项目映射 |
| --- | --- | --- | --- |
| 平台 | `validate_credential` | 在连接设置期间验证 OneNote 凭据。 | 相当于认证健康检查；本项目已有 `check_authentication`，认证流程仍必须保持本机 Device Code Flow。 |
| 平台 | Tool Packs | 以工具包限定某个 Agent/用户可使用的工具集合。 | 可借鉴为最小工具暴露与按场景配置，但不改变现有 MCP 工具稳定性或安全开关。 |
| 平台 | DLP、调用日志、审计轨迹 | 公开资料称可对每次调用作数据检查、记录调用信息和审计。 | 仅作平台能力参考；本项目日志继续执行脱敏与最小化原则。 |

## 与本项目层级—操作矩阵的对照

| 对象层级 | Merge 公开覆盖 | 本项目当前矩阵 | 可借鉴的设计结论 |
| --- | --- | --- | --- |
| Notebook | `C`、List/Get/Recent/Default、Copy | Create 已实现；List/Get 部分；Query/Recent/Copy 待实现；Update/Delete 为边界。 | 补齐分页与结构化 Query；将 Recent、Default 保持为单用途 Read，不混入 List。 |
| SectionGroup | List/Get/Create | 全部 Graph 原生能力待实现；Update/Delete 为边界。 | 优先补只读层级与创建工具；List、Get、Get Tree 仍需分开。 |
| Section | 多范围 List、Get、双父级 Create、两种 Copy | Notebook 下 Create/List/Get 部分实现；其他 Graph 原生能力待实现。 | 按父级和目标位置拆分参数/工具，避免单一 `parent_id` 或 `target_id`。 |
| Page | Section 范围 List、Metadata/Content Get、Create、完整 change action、Delete、Copy | Create/Content Get/Delete 已实现；List/Get/Update 仍有完整性缺口；Copy 待实现。 | 以 `includeIDs`、受控 target、action 和 position 设计完整 Update；复制需受限异步 operation 客户端。 |

## 是否超出 Graph API 边界

结论：根据 Merge 的公开工具目录和 Microsoft Graph v1.0 文档，**没有发现某个 OneNote 对象工具必须依赖 Graph 未提供的 CRUD、Copy 或正文更新方法**。Notebook/SectionGroup/Section/Page 的 List、Get、Create、Page Delete、Page Update 以及 Notebook/Section/Page Copy 都有 Graph v1.0 对应能力；Graph 也支持 `$top`、`$skip`、`$orderby`、`$filter`、`$select` 和受限 `$expand`。因此，Merge 的公开工具集整体没有显示出“超出 Graph API”的证据。

但有三类工具或描述不应误读为纯 Graph 原生能力：

| Merge 能力 | 评估 | Graph/产品边界 |
| --- | --- | --- |
| `get_default_notebook` | `△` 产品组合，不是 Graph 独立方法。 | Graph 的 Notebook 有只读 `isDefault` 字段，且支持过滤；“没有默认时返回第一个”是 Merge 的本地回退规则。它没有越过 API，只是在 API 结果上增加产品语义。 |
| `validate_credential` | `△` 平台认证动作，不是 OneNote 对象操作。 | 可通过 OAuth 状态或受限 Graph 请求实现；公开资料不足以判断它调用了哪条 API，但没有证据显示其取得了额外 OneNote 数据能力。 |
| List 中的 raw OData 与 Copy 返回 operation URL | `✓` 对 Graph 是原生用法，`X` 对本项目的公开接口策略。 | Graph 官方支持这些查询选项，并在异步 Copy 响应中返回 `Operation-Location` 供轮询；本项目仍不得透传任意 OData 或 URL，而应改为结构化条件和受校验的不透明游标/operation 引用。 |

### Page 更新的边界核验

Merge 的 `update_page` 页面说明把 target 概括为“`body` 或元素 ID”，并列出 `append`、`replace`、`prepend`、`insert`。这并未证明越过 Graph，但它**省略了必须由工具 schema 或服务端校验的限制**：

- `body` 只能追加或前置内容，不能 replace 或 insert；
- `replace` 对多数元素需要 Graph 生成的 ID；title、部分图片/对象是特例；
- `insert` 必须使用支持 sibling 的元素并指定合法位置；
- 生成 ID 在更新后可能变化，通常要先以 `includeIDs=true` 重新读取页面。

如果 Merge 实际接受任意 `target/action` 并承诺全部成功，这会是其**工具契约过宽**，而不是 Graph API 被突破：Graph 会拒绝不支持的组合。没有实际 schema 或调用记录时，不能断言它存在此问题；本项目应继续按上述规则做 fail-closed 校验。

### Page 删除的安全边界

`delete_page` 可直接对应 Graph v1.0 的 Page DELETE，因此不是 API 越界。Merge 公开页将其描述为永久且不可撤销；本项目的额外双开关、标题确认和删除前回读是本地产品安全要求，不是 Graph 的能力限制。两种产品在这里的差异是风险控制，而不是 API 覆盖范围。

## 建议的后续取舍

1. 先补齐总览已标为 `M（部分）` 或 `G` 的 Graph 原生能力：统一分页、SectionGroup 读取、SectionGroup 下创建 Section、结构化 Query，以及 Page 的受控四种更新 action。
2. 复制操作可参考 Merge 的“异步 operation”产品形态，但实现必须遵守本项目的 `/me/onenote/` allowlist、有限轮询、幂等回查和 operation URL 不外露规则。
3. 将 Merge 的 List 筛选能力拆为本项目的 List 与 Query：公开参数使用资源级字段和白名单条件，不允许调用者提交原始 OData、`$skip` 或任意 Graph URL。
4. 维持 Page List 必须有 Section 范围的原则；正文 Search 继续仅允许 Section 或 SectionGroup 范围，并执行候选 Page 预检和服务端硬上限。
5. 不以 Merge 的“永久删除”描述降低 Page Delete 的确认门槛，也不将平台级 DLP/审计宣传转化为本地持久化 Page 内容或敏感调用参数。

本报告是外部产品对标材料，不改变本项目的实现状态或路线优先级。实施工作仍应以对象模型、活动 TODO、Mock 测试和 Microsoft Graph 官方文档为准。
