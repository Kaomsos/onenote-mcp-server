# 探索 TODO 索引

`docs/todos/` 只保存尚未完成、需要进一步验证或设计的工作。它是 Agent 和维护者开始 non-trivial 任务前必须检查的活动清单，不是永久知识库。

## 活动事项

- [对标项目功能追平盘点](reference_project_feature_parity.md)：核对 X 声称的能力、当前实现和 Graph 官方支持边界。
- [Notebook、Section、Page 三级 CRUD 缺口](three_level_crud_gap.md)：定义可实现的完整度并形成受约束的演进路线。
- [Page 子页面层级支持](page_hierarchy_support.md)：验证层级读取、树形重建及层级写入的 API 边界。
- [Page 与 Section 复制、移动能力](page_section_copy_move.md)：调研异步复制端点、移动边界和安全实现条件。
- [Page 正文范围搜索](page_content_search.md)：区分元数据 Query 与正文 Search，并设计 Section/SectionGroup 范围、候选 Page 硬限制和安全结果契约。

## 文档约定

每个 TODO 至少包含状态、目标、当前基线、待探索问题、验收条件和阶段进展。状态只使用：`待探索`、`探索中`、`阻塞`。

- 一个独立问题对应一个文件，文件名使用小写英文和下划线。
- 每完成一个可验证阶段，就追加一条带日期的阶段进展，记录脱敏证据、所得结论和明确下一步。
- 真实账号或 live 验证必须先取得项目守则要求的显式授权；TODO 不得保存账号资料、认证材料、资源 ID、原始 Graph 响应或 Agent trace。
- 代码、测试、Graph 官方文档或产品范围变化导致基线失效时，在同一变更中更新相关 TODO。
- 整个事项完成后，将仍有长期价值的结论迁入 `docs/design/`、`docs/lessons/`、README 或测试，然后删除 TODO 文件及本索引条目。
- 事项被取消、合并或替代时，直接删除旧 TODO 和索引条目；必要的原因写入接替它的正式文档，不保留失效清单。
- 新增或删除活动 TODO 文件时，同步源码 ZIP 的显式文件白名单及发布测试，保证分发包内的索引链接有效。

TODO 文件删除后不再承担历史记录职责；Git 历史以及迁入的正式文档负责保存可追溯性。
