# Graph 写入能力的安全边界

## 问题

项目需求假定基础项目尚未实现 Notebook 和 Section 创建，但当前基线已经包含这两个工具；同时原实现会把 token 明文写入用户目录，并在认证状态中输出账号资料。

## 解决方案

以现有工具为兼容基线，重构为 Device Code Flow + 平台加密 MSAL cache + 统一 Graph 客户端。写工具默认关闭，错误响应与日志不传递认证材料或 Graph 原始正文。

## 预防措施

任何 Graph 创建功能先核对官方可逆性。Notebook/Section 不应承诺自动回滚；真实验收始终使用隔离测试 Notebook，且需用户确认后执行。
