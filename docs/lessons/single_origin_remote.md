# 个人项目只保留一个 origin

## 问题

仓库一度同时使用原始项目 `origin` 和个人仓库 `fork`。这种命名适合长期同步上游的传统 fork 工作流，但本项目的实际发布目标始终是个人仓库。双远程会增加以下无收益的复杂度：

- Agent 必须记住 fetch、比较和 push 分别使用哪个 remote。
- `origin` 在不同机器或历史阶段可能指向不同仓库，文档命令容易失效。
- 自动化推送前需要额外判断目标，增加误推送风险。
- 实际不需要直接同步原始项目，却长期保留了上游配置和规则。

## 原因

此前沿用了“上游叫 origin、个人仓库叫 fork”的维护习惯，而没有根据本项目当前唯一发布目标简化远程模型。工具和 Agent 又通常默认把 `origin` 视为主要仓库，导致约定与默认行为相反。

## 解决方式

主仓库只保留一个 remote，仓库身份必须是 `Kaomsos/onenote-mcp-server`。URL 协议由当前机器的认证方式决定，以下两种形式等价：

```text
origin  git@github.com:Kaomsos/onenote-mcp-server.git
origin  https://github.com/Kaomsos/onenote-mcp-server.git
```

`origin` 同时用于 fetch 和 push，当前 `main` 跟踪 `origin/main`。标准更新流程是：

```bash
git remote -v
git status --short
uv run pytest -q
git add <明确文件>
git commit -m "<message>"
git push origin main:main
```

不添加真正上游 remote，不创建 `fork` remote，也不在日常流程中引用原始项目仓库。如果需要研究外部实现，使用浏览器或项目内被忽略的参考 clone；参考目录拥有自己的 Git 状态，不参与主仓库 remote 配置。

## 预防措施

- Agent 每次推送前检查 `git remote -v`，必须只有一个 `origin`。
- 将 scp 风格 SSH、`ssh://` 和 HTTPS URL 规范化为 host/owner/repository 后再比较；不得把协议差异误判为仓库不匹配。
- `origin` 的规范化仓库身份不匹配个人仓库时停止推送，先修复 remote。
- 文档和自动化命令统一使用 `origin`，不得出现 `git push fork`。
- 不因临时比较上游而修改主仓库 remote；使用一次性 URL 查询或独立参考目录。
- 新环境使用该机器已有凭据支持的 HTTPS 或 SSH URL clone 个人仓库，避免继承双远程配置。
