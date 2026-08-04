# Page 与 Section 复制、移动能力

- 状态：探索中

## 目标

调研 Microsoft Graph OneNote v1.0 对 Page 和 Section 复制、移动的真实支持范围，并为可能的 MCP 能力定义异步操作、安全门、验证方式和失败恢复边界。

## 当前基线

- 本项目和对标项目 X 当前都没有 Page/Section 复制或移动工具。
- Graph 官方支持 [`POST /me/onenote/pages/{id}/copyToSection`](https://learn.microsoft.com/en-us/graph/api/page-copytosection?view=graph-rest-1.0)，请求体必须提供目标 Section ID；复制到 Microsoft 365 Group 时还可以提供 `groupId`。
- Graph 官方支持 Section 的 [`copyToNotebook`](https://learn.microsoft.com/en-us/graph/api/section-copytonotebook?view=graph-rest-1.0) 和 [`copyToSectionGroup`](https://learn.microsoft.com/en-us/graph/api/section-copytosectiongroup?view=graph-rest-1.0)，可使用 `renameAs` 指定副本名称。
- 上述复制操作都返回 `202 Accepted` 和 `Operation-Location`，必须轮询 [`GET /me/onenote/operations/{id}`](https://learn.microsoft.com/en-us/graph/api/onenoteoperation-get?view=graph-rest-1.0)，直到状态为 `Completed` 或 `Failed`，成功后再从 `resourceId` 或 `resourceLocation` 定位副本。
- 当前 `GraphClient.request_json` 只返回 JSON body，无法取得 `Operation-Location` 响应头，因此尚不具备实现异步复制的客户端抽象。
- Graph 的 Page 和 Section 方法表没有原生 Move，也没有名为 `markAsDeleted` 的属性或方法。本 TODO 将模拟移动统一定义为 `copy → verify → markAsDeleted`：复制并验证新对象后，只把源对象标记为逻辑删除，不调用 Graph DELETE，源对象仍物理存在且标记必须可逆。
- `markAsDeleted` 的持久化形式尚待设计。Page 可以评估受控的内容或标题标记；Section 没有受支持的更新接口，可能需要项目自有的本地墓碑索引。若不能可靠保存和同步标记，对应资源只能提供 Copy，不能宣称支持 Move。

## 待探索问题

1. 设计统一的异步 Graph 调用接口：只接受 `/me/onenote/` allowlist 内的相对 operation 路径，提取并校验 `Operation-Location`，有界轮询且不泄露完整 URL、原始错误或诊断正文。
2. 明确轮询超时、网络中断和未知状态下的恢复协议；复制 POST 不得盲目重试，避免产生重复 Page 或 Section。
3. 验证 Page 复制是否保留标题、HTML、附件、页面层级以及子 Page；特别区分复制单个 Page 与复制整棵子页面树。
4. 验证 Section 复制是否完整保留全部 Page、Page 层级、附件和顺序，并确认同一 Notebook、跨 Notebook、目标 Section Group 与 Microsoft 365 Group 的支持差异。
5. 定义目标确认信息和冲突策略：Section 可使用唯一 `renameAs`，Page 没有对应重命名参数，必须避免仅按可能重复的标题判断副本。
6. 决定 MCP 接口应由一个阻塞到完成的 copy 工具封装轮询，还是拆分为开始复制与查询状态；无论哪种方式都不得向 Agent 暴露任意 operation URL 或通用 Graph 工具。
7. 定义 `markAsDeleted` 的统一契约：逻辑状态的存储位置、源对象精确确认、可逆恢复、跨进程持久化、列表过滤方式，以及源对象在其他 OneNote 客户端仍然可见时如何避免误导用户。
8. Page 模拟移动固定采用 `copy → verify → markAsDeleted`，不得追加物理删除步骤。若副本已验证但标记失败，应明确返回“已复制、源未标记”，不得回滚副本、盲目重试复制或扩大修改范围。
9. Section 只有在墓碑索引的身份、持久化和同步语义得到可靠设计后才能采用同一流程；否则只提供 Copy。不得通过重建 Notebook、Drive 删除或 UI 自动化冒充 Move。

## 验收条件

- 为 Page copy、Section copy-to-notebook、Section copy-to-section-group 和 operation polling 建立官方端点、参数、权限、响应及云环境支持矩阵。
- Mock 覆盖 `202` 缺少或伪造 `Operation-Location`、Running→Completed、Failed、未知状态、超时、网络中断和重复风险，所有错误保持脱敏。
- Copy 与 `markAsDeleted` 都受普通写入开关保护；标记前必须精确确认源对象。该流程不得调用 Page DELETE，也不得把 `ONENOTE_ENABLE_DELETES` 作为实现依赖；是否设置 destructive annotation 取决于最终墓碑是否真正可逆。
- live 验证只在账号所有者分别授权 Provider 数据和真实写入后，对唯一命名测试 Notebook 执行；不得持久化资源 ID、operation ID、原始响应或 trace。
- README 和设计文档明确区分 Copy、`copy → verify → markAsDeleted` 的逻辑 Move，以及 Graph 原生 Move 的缺失；实施或否决结论迁入正式文档与测试后，删除本 TODO 和索引项。

## 阶段进展

### 2026-07-29：完成官方端点静态调研

- 脱敏证据：核对 Microsoft Graph v1.0 的 Page `copyToSection`、Section `copyToNotebook`/`copyToSectionGroup` 和 `onenoteOperation` 官方文档，并检查当前 Graph 客户端和工具注册表。
- 结论：Page 与 Section 原生复制可行但必须补异步响应头与轮询抽象；Graph 没有原生移动。
- 下一步：先设计只复制的异步客户端契约和 Mock 状态机；未获得显式授权前不执行 live 复制。

### 2026-07-29：调整模拟移动语义

- 脱敏证据：复核 Graph Page/Section 官方方法表，未发现 `markAsDeleted` 原生属性或操作。
- 结论：项目中的 Move 统一表示为 `copy → verify → markAsDeleted`，最后一步是可逆的项目级逻辑标记，不执行源对象物理删除。
- 下一步：分别确定 Page 与 Section 墓碑的存储和同步方案；方案确定前不注册 Move 工具。

### 2026-08-03：将复制与移动边界纳入层级操作矩阵

- 脱敏证据：复核 Graph v1.0 资源方法表与现有设计文档；未执行复制、写入或真实账号验证。
- 结论：总览矩阵和 Section 业务操作目录已明确区分异步 Copy、组合式逻辑 Move 与不可用的原生 Move；SectionGroup 不具备原生 Copy，Notebook Copy 也不构成移动、备份或重命名。
- 下一步：继续设计异步响应头校验与有界轮询；Section 墓碑持久化方案确定前，矩阵中的 Move 保持 `P`（项目组合），不得注册为稳定工具。

### 2026-08-04：评估 Windows COM 的复制与移动补充路线

- 脱敏证据：静态核对微软 OneNote Application 接口的 `UpdateHierarchy`、`MergeSections`、`DeleteHierarchy`、`GetPageContent` 和 `UpdatePageContent`，并对照两个公开本地 COM MCP；未执行真实 Notebook 写入。
- 结论：COM 没有通用 Copy 方法，组合复制仍会产生新 ID，Graph 原生 Notebook/Section/Page Copy 应保持优先。COM 的显著新增能力是 `UpdateHierarchy` 官方明确支持同一 Notebook 内移动 Section；跨 Section Page Move 仍只能组合为复制、验证后将源 Page 移入 OneNote 回收站，不能称为保留 ID 的原生 Move。跨 Notebook Section Move、SectionGroup Move 与各类重挂接仍需验证。
- 下一步：若引入可选 COM adapter，先在唯一命名隔离 Notebook 中分别验证三种同 Notebook Section 父级转换及 ID 保持；Page 组合 Move 必须另行设计删除开关、保真验证和部分失败恢复，不能复用 Graph 逻辑墓碑语义而不改名。
