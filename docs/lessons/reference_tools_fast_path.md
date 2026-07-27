# 对标项目 Tools 快速移植边界

## 问题

为尽快扩展 OneNote MCP 工具，需要判断本地对标项目 `azure-onenote-mcp-server` 中哪些端点可以安全迁入当前 Public Client + Device Code Flow 架构。参考版本为 commit `38b8f7b`。

## 发现

- `getNotebook`、`getSection` 和 `getPage` 使用的单资源 GET 端点与 Microsoft Graph v1.0 一致，可以在现有统一 Graph 客户端上直接实现。
- `deletePage` 对应官方 `DELETE /me/onenote/pages/{id}`，个人账号可继续使用 Delegated `Notes.ReadWrite`。
- 对标项目的 `deleteNotebook`、`deleteSection` 只有 Mock 客户端测试，不能证明真实 OneNote Graph 端点受支持。
- 对标项目的 `.search(query)` 没有处理 OneNote 官方查询能力、分页和作用域限制，不适合直接迁入。
- 对标项目使用 Client Secret 和 `.default` scope，违反当前项目的 Public Client + Device Code Flow 安全边界。
- 对标项目直接传播异常 message，可能泄露 Graph 原始响应正文。

## 方案

- 只参考端点形状，不复制或导入对标源码。
- 新增三个精确读取工具，并把 Page 元数据与现有 HTML 内容读取拆开，避免不必要的双请求。
- Page 删除使用双开关：普通写入开关与独立删除开关必须同时开启。
- 删除前回读 Page 标题并与调用者提供的 `expected_title` 完全匹配；不匹配时不得发送 DELETE。
- Notebook 和 Section 不增加 MCP 删除工具；普通验收继续人工删除。只有开发仓库的 opt-in pytest 控制面可临时请求 `Files.ReadWrite` 并清理精确测试 Notebook；它可以按授权复用加密 cache，但不得向 Agent 暴露 Drive 能力。产品搜索、分页和 Section Group 留待独立设计。

## 预防措施

- 对标项目中的 Mock 成功不能代替 Microsoft Graph 官方文档和真实隔离资源验收。
- 任何新删除工具都必须有独立开关、MCP destructive annotation、确认参数和零请求拒绝测试。
- 不迁移 Client Secret、token 输出、原始错误正文或通用 Graph 请求入口。
- 真实删除验收只允许针对唯一隔离测试 Notebook 内的 Page，并在结束时恢复全部写入开关。
