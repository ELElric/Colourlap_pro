# 12 决策日志

> 所有架构 / 接口 / 算法的非平凡决策在此记录。
> 编号连续：D-001, D-002, ... 不可重用。

---

## D-001 ~ D-012：V1.0 历史决策

> 来自早期版本，保留以追溯。
> 摘要：项目立项、技术栈选型初版、模块划分第一版、测试策略第一版。

## D-013：6 层架构

- 日期：2026-06-15
- 决策：将原 4 层（UI / Service / Engine / DB）升级为 6 层（UI / Controller / Service / Engine / Repository / Database）
- 理由：Controller 解耦 UI 事件与业务用例；Repository 解耦数据访问与 ORM
- 影响：`docs/03` 全面更新；`src/colorlab_pro/` 新增 `controllers` 与 `repositories` 子包

## D-014：使用 SQLAlchemy ORM

- 日期：2026-06-15
- 决策：使用 SQLAlchemy 2.0+ ORM，取代裸 SQL
- 理由：迁移管理、类型提示、模型可视化
- 影响：`docs/06` 重写数据访问层

## D-015：使用 shapely 做几何运算

- 日期：2026-06-15
- 决策：Coverage / 色域多边形使用 shapely 2.0+
- 理由：成熟、稳定、API 简洁
- 影响：`requirements.txt` 新增 `shapely>=2.0`

## D-016：Coverage / Match 在 xy 空间完成

- 日期：2026-06-15
- 决策：所有 Coverage / Match 计算统一在 CIE 1931 xy 空间
- 理由：业界标准，直观，可视化容易
- 影响：`docs/04` §3 / §4 更新

## D-017：Match 公式

- 日期：2026-06-15
- 决策：`match = (1 - mean_delta_xy / 0.1) * 100%`
- 0.1 = Δxy 饱和值
- 影响：`docs/04` §4.2 公式

## D-018：spectrum + spectrum_point 分表

- 日期：2026-06-15
- 决策：光谱元数据与数值分表存储，不用 BLOB
- 理由：可索引、可分页、备份小、SQL 查询友好
- 影响：`docs/06` §2

## D-019：V1.1 仅 PySide6（无 Web / Electron）

- 日期：2026-06-15
- 决策：V1.1 桌面端只支持 PySide6
- 理由：技术栈统一、维护成本低、单机应用足够
- 影响：UI 部分仅 `PySide6`

## D-020：src 布局

- 日期：2026-06-15
- 决策：使用 `src/colorlab_pro/` 布局，禁用 flat `app/` 布局
- 理由：避免路径冲突、强制 import 走包内
- 影响：`pyproject.toml` `tool.setuptools.packages.find.where = ["src"]`