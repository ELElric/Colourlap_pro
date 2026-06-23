# ColorLab Pro — AI 上下文索引

> 这是 AI 会话读取的入口。包含项目快照与索引。

## 项目快照

- **项目名**：ColorLab Pro
- **版本**：V1.1
- **类型**：桌面端 Python 应用
- **领域**：显示器件光谱 + 色度分析
- **目标用户**：LED/QD/CF 研发工程师、色彩管理工程师、FAE

## 技术栈

- Python 3.10–3.14（开发目标 3.11）
- PySide6 6.6+
- numpy 1.26.4、scipy 1.11+、colour-science 0.4.4
- SQLAlchemy 2.0+、shapely 2.0+
- loguru、openpyxl

## 关键决策（前缀 D-NNN）

- D-013：6 层架构
- D-014：SQLAlchemy ORM
- D-015：shapely
- D-016：xy 空间
- D-017：Match 公式
- D-018：分表存储
- D-019：仅 PySide6
- D-020：src 布局

详见 `../docs/12_Decision_Log.md`。

## 文件索引

| 关注点 | 入口 |
|--------|------|
| 当前任务 | `CURRENT_TASK.md` |
| 项目状态 | `PROJECT_STATUS.md` |
| 已知问题 | `KNOWN_ISSUES.md` |
| 领域知识（色度）| `DOMAIN_KNOWLEDGE.md` |
| 变更日志 | `RELEASE_NOTES.md` |

## 阅读顺序

`CURRENT_TASK.md` → `PROJECT_STATUS.md` → `KNOWN_ISSUES.md` → `DOMAIN_KNOWLEDGE.md` → 相关 `docs/`。