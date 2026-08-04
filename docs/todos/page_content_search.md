# Page 正文范围搜索

- 状态：探索中

## 目标

为本项目设计独立于对象 Query 的 Page 正文 Search。首期只考虑以单个 Section 或单个 SectionGroup 为范围，返回匹配的 Page 与有限纯文本片段；不提供 Notebook 或账号全局正文搜索，不把元数据 OData Query、OneNote 客户端搜索或 Microsoft Search API 描述成 Graph 原生 OneNote Page 正文搜索。

## 当前基线

- 稳定 Microsoft Graph OneNote v1.0 可以查询 Page 元数据、读取单 Page HTML 和短 Preview，但没有 OneNote Page 正文搜索端点，也不支持对 Page HTML 使用 `$search`。
- 当前 MCP 已有 `list_pages(section_id)` 与 `get_page_content(page_id)`，但没有 Search 工具；集合读取也尚未统一处理 `@odata.nextLink`。
- Search 候选范围固定为 `section_id` 或 `section_group_id` 二选一。SectionGroup 范围需要递归枚举全部后代 Section，再扫描其 Page。
- 正文匹配属于项目组合能力：必须先枚举候选 Page，再逐页读取 HTML、提取可见文本并在本地匹配。
- 候选 Page 数使用服务端配置 `ONENOTE_SEARCH_MAX_PAGES` 硬限制，默认建议为 `100`。超限必须在读取任何 Page HTML 前以 `search_scope_too_large` 拒绝；调用者不得提高该阈值。

## 待探索问题

1. 固定 `search_pages` 输入契约：`query` 必填，`section_id` 与 `section_group_id` 必须且只能提供一个；不得接受任意 Graph URL、原始 OData、`nextLink` 或调用者自定的扩大扫描上限。
2. 设计候选预检：只读取元数据，SectionGroup 全部后代共享一个累计 Page 预算；枚举到“阈值 + 1”即可拒绝，不继续追求精确总数，也不得提前读取正文。
3. 为 `ONENOTE_SEARCH_MAX_PAGES` 增加启动时正整数校验、默认值、合理硬上限和 Mock；无效配置必须 fail closed，不能静默成为无限制。
4. 定义 SectionGroup 递归的深度、节点数、分页、循环、父关系缺失和部分失败行为；结构不完整时不得宣称 Search 完整。
5. 定义 HTML 到可见纯文本的规范化规则、Unicode/大小写处理、短语或多词匹配语义，以及标题与正文匹配的排序方式。
6. 除 Page 数外，定义单 Page 字节数、总下载字节数、并发请求数、总耗时和返回结果数上限；网络错误与限流后不得盲目从头重扫。
7. 固定结果契约：只返回必要元数据、匹配位置和有限纯文本片段；可续传中止返回 `complete=false` 与不透明游标，候选 Page 超限则硬拒绝且不返回部分匹配。
8. 明确首期不搜索图片 OCR、手写、音视频或附件正文，不持久化原始 HTML，不在日志中记录查询词、正文、片段或 Graph 原始响应。
9. Notebook/全局正文搜索若未来进入范围，必须独立设计显式启用、可清除且不明文持久化正文的本地索引；不得通过每次全库扫描实现。

## 验收条件

- 正式设计文档明确区分 Query 与 Search，并在层级—操作矩阵中只把 Search 归于 Page。
- Mock 证明 Section 与 SectionGroup 候选预检在阈值内才读取正文，阈值 + 1、分页异常、递归异常和无效配置均 fail closed。
- 搜索结果的完整性、游标、片段长度、匹配模式和各类资源预算有稳定契约；零匹配但不完整不会被返回为“没有结果”。
- 工具与错误不泄露原始 HTML、Graph 响应、账号资料或认证信息。
- 真实账号验证只在账号所有者明确授权只读 Graph 数据和 Provider 数据后进行，不持久化资源 ID、正文或 Agent trace。
- 实施结论、Mock 与长期约束迁入正式文档、README 和测试后，删除本 TODO 及索引项。

## 阶段进展

### 2026-08-04：完成 Query/Search 边界与首期范围设计

- 脱敏证据：核对 Graph OneNote v1.0 的 Page 集合查询、Page HTML/Preview 读取和 Microsoft Search 支持范围，并检查当前 `list_pages`、`get_page_content` 与分页基线；未执行真实账号请求。
- 结论：Query 只查询对象元数据与 relationship；Search 只检索 Page 正文，首期范围为 Section 或 SectionGroup。候选 Page 预检受 `ONENOTE_SEARCH_MAX_PAGES` 服务端硬限制，超限时必须在正文读取前拒绝。
- 下一步：先完成统一分页和 SectionGroup 只读层级，再设计 `Settings` 校验、候选预检状态机、HTML 纯文本提取及 Mock。

### 2026-08-04：同步 Page 章节的 Search 边界

- 脱敏证据：在 Page CRUD 章节中对照总览的 Query/Search 定义、范围互斥规则和候选 Page 硬限制；未读取任何真实 Page 内容。
- 结论：Page 章节现已把元数据 `query_pages` 归入 Read，把正文 `search_pages` 标为 Page 层级的项目组合能力；Section 与 SectionGroup 只限定范围，不获得独立 Search 操作。超限必须在读取 HTML 前拒绝。
- 下一步：实现前先补 `ONENOTE_SEARCH_MAX_PAGES` 配置校验和候选预检 Mock，再进入正文提取与匹配设计。
