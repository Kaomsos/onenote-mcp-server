# Page 子页面层级支持

- 状态：探索中

## 目标

评估并实现可验证的 Page 层级读取，使 Section 下的一级 Page、子 Page 和子子 Page 能在 MCP 返回值中保持结构；同时明确 Graph 是否支持创建、移动或调整 Page 层级。

## 当前基线

- 当前 `list_pages(section_id)` 调用 Section 的 pages 集合，但没有传入 `pagelevel=true`，返回值也不包含 `level` 或 `order`。
- 子 Page 目前会被当作普通 Page 读取；MCP 无法判断父子关系，也不能返回树形结构。
- Microsoft Graph 支持对 Section 页面集合或单个 Page 使用 `pagelevel=true`，返回只读的 `level` 与 `order`。
- Graph 的 Page 关系只有 `parentNotebook` 和 `parentSection`，没有 `parentPage`；父 Page ID 只能根据 Section 内顺序和缩进层级推导。
- `level` 与 `order` 在 Graph 资源模型中是只读属性，创建 Page 的请求也没有父 Page 或层级参数，因此稳定 API 没有受支持的层级写入方法。

## 待探索问题

1. 验证 `pagelevel=true`、分页和排序组合在个人账户与组织账户中的响应形状；真实账号只允许在显式授权后做只读验证。
2. 设计兼容现有工具名的返回接口：至少保留 `level`、`order`，并决定是否额外返回推导的 `parent_page_id` 或独立树形视图。
3. 定义树形重建算法：按可靠顺序遍历并维护层级栈；层级跳跃、缺失、重复顺序或分页不完整时不得猜测父节点。
4. 确认 Page 列表的全部分页完成后再建树，避免跨页边界丢失父节点。
5. 用 Mock 覆盖一级、二级、三级、同级切换、层级回退、非法跳级和分页边界。
6. 记录层级 mutation 的官方边界：创建子 Page、缩进、提升、重新挂接和设置顺序均不作为受支持 MCP 能力，除非未来官方稳定 API 明确提供。

## 验收条件

- Mock 测试能从扁平 `level`/`order` 数据稳定重建三层结构，并对不一致数据安全失败或明确降级为扁平结果。
- MCP 返回结构保持工具名稳定、字段语义明确，且不会把推导的父子关系描述成 Graph 原生 relationship。
- 分页、排序和层级信息经过官方文档核验；若进行 live 验证，使用唯一隔离测试内容且不记录资源 ID 或原始响应。
- README 或设计文档明确区分“可读取层级”和“不能写入层级”，实施完成后删除本 TODO 和索引项。

## 阶段进展

### 2026-07-29：完成官方能力与当前实现对照

- 脱敏证据：检查当前 `list_pages` 映射字段，并核对 Microsoft Graph 的 OneNote Page 资源和内容结构文档。
- 结论：只读层级支持技术上可行，当前项目尚未实现；稳定 Graph API 没有创建或调整子 Page 层级的受支持入口。
- 下一步：先设计分页完整的扁平返回与树形推导契约，再编写 Mock；未获得授权前不做真实账号验证。

### 2026-07-30：完成层级对象与树查询契约设计

- 脱敏证据：核对 Notebook/SectionGroup/Section/Page relationship、`pagelevel=true`、`level`、`order` 和 Page 内容资源文档；检查当前工具尚未返回层级字段。
- 结论：在 `docs/design/onenote_object_model/` 固化完整路径、一级子节点、Page 全部后代、`relationship_source`、分页完成性和安全失败码；SectionGroup 作为 Graph 原生递归节点，Page 父关系明确标为本地推导。
- 下一步：编写分页、嵌套 SectionGroup、三级 Page、非法跳级、顺序冲突和跨分页边界的 Mock 测试，然后实现只读层级查询；未获得授权前不做 live 验证。

### 2026-08-04：补充 Windows COM 层级写入候选路线

- 脱敏证据：静态核对微软 OneNote Application 接口的 `UpdateHierarchy` 和 `CreateNewPage`；未对真实 Page 执行排序或层级写入。
- 结论：Graph 的 `level`/`order` 仍为只读；可选 COM adapter 则有官方明确的 Section 内 Page 排序能力，并能在创建 Page 时控制位置和建立子 Page。官方文档没有同等明确保证对既有 Page 执行缩进、取消缩进或跨 Section 保留 ID 移动，因此这些操作仍保持待验证，不能由 XML 字段存在直接推定为可交付。
- 下一步：COM 路线若立项，优先验证保持 Page ID 的 `reorder_page`；再以独立测试覆盖既有 Page 缩进、取消缩进、整棵子树移动和异常层级，验证前不修改 Graph 对象模型的交付状态。
