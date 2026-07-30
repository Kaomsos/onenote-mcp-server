# 对标项目功能追平盘点

- 状态：探索中
- 对标项目：`ZubeidHendricks/azure-onenote-mcp-server`
- 当前参考版本：`38b8f7bb8e671063b01fd4f950b6f630188ae213`

## 目标

逐项比较对标项目 X 与本项目的 MCP 能力，区分“X 声称具备”“Graph 官方支持”“本项目已实现并测试”三种状态，形成可审查的功能矩阵和后续取舍。

## 当前基线

- 本项目已经实现 X 原先独有的 Notebook/Section 精确读取，并把 X 的 Page 读取拆为 `get_page_metadata` 与 `get_page_content`。
- 本项目已经实现 Graph 官方支持的 Page 删除，并增加写入开关、独立删除开关和标题确认。
- X 的 `searchPages` 尚未迁入；其实现没有给出分页、查询转义和作用域兼容性的完整证据。
- X 声明了 Notebook/Section 删除，但 Microsoft Graph OneNote v1.0 的资源方法表没有对应受支持方法，不能把 Mock 或代码声明视为可用能力。
- X 的 Client Secret、`.default` scope、原始错误传播和未经确认的删除模型违反本项目安全边界，不属于可迁移功能。

## 待探索问题

1. 为 X 与本项目的每个业务工具建立端点、请求形状、权限、写入风险、Mock 覆盖和 live 证据矩阵。
2. 重新设计 Page 搜索，确认全局、Section 范围和 Notebook 范围分别受哪些官方端点支持，并定义查询转义、分页和结果上限。
3. 判断 X 的 `createNotebook(sectionName)` 单调用便利能力是否值得在保持现有稳定工具名的前提下提供，还是继续使用两步组合。
4. 识别 X 之外但官方支持、且符合生产 `/me/onenote/` allowlist 的低风险读取能力，避免把“追平 X”误当作产品上限。

## 验收条件

- 每个 X 工具都有“已覆盖、部分覆盖、待设计、明确拒绝”之一的结论，并附本地实现或 Microsoft 官方文档证据。
- 候选迁移功能有明确 MCP 接口、安全门、分页策略和 Mock 测试计划。
- 不以 X 的 Mock、README 或未受支持端点代替官方 Graph 证据；任何 live 结论都来自另行授权的隔离验证。
- 稳定结论迁入设计文档或 lessons 后，删除本 TODO 和索引项。

## 阶段进展

### 2026-07-29：完成初步静态盘点

- 脱敏证据：对照本项目工具注册表、X commit `38b8f7b` 和 Microsoft Graph v1.0 资源方法表；本项目非 live 测试为 `42 passed, 3 skipped`。
- 结论：精确读取和 Page 删除已经追平且安全性高于 X；真正待设计的 X 差异主要是 Page 搜索和创建 Notebook 时顺带创建 Section 的便利接口。Notebook/Section 删除不应按 X 的实现直接迁入。
- 下一步：为 Page 搜索建立官方端点与分页兼容矩阵，不进行未授权 live 请求。
