# 11 AI 开发指南

## 1. AI 上下文

每次会话开始时，AI 应阅读：

1. `ai_context/AI_CONTEXT.md`（项目快照）
2. `ai_context/CURRENT_TASK.md`（当前任务）
3. `ai_context/PROJECT_STATUS.md`（整体进度）
4. `ai_context/KNOWN_ISSUES.md`（已知问题）
5. `ai_context/DOMAIN_KNOWLEDGE.md`（领域知识，色度部分）
6. `ai_context/RELEASE_NOTES.md`（变更日志）

## 2. 任务工作流

1. 阅读 `ai_context/CURRENT_TASK.md` 的 Active Task
2. 阅读相关 `docs/` 章节（由 Reference Documents 字段给出）
3. 实现代码 + 测试
4. 跑测试，确认通过
5. 更新 CURRENT_TASK / PROJECT_STATUS / KNOWN_ISSUES（如有新问题）
6. 如有非平凡决策：追加到 `docs/12_Decision_Log.md`

## 3. 上下文管理

- 一次性不加载超过 5 个大文件
- 长输出用 `ai_context/_summaries/`（如有）
- 关键数值（如 CIE 1931 数据）使用 `colour-science`，不要硬编码

## 4. 决策原则

- 与既有 `D-NNN` 决策冲突时停下报告
- 引入新依赖时评估：维护性、license、大小
- 不要生成测试覆盖率 100% 的代码（无意义），目标是核心 engine ≥ 80%

## 5. 禁止

- 不要"猜测"色度公式（CIE / McCamy 等），全部引用 `DOMAIN_KNOWLEDGE.md`
- 不要修改已 frozen 的 01 / 02 文档
- 不要删除任何已存在的代码