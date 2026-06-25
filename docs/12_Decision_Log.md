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

## D-021：UI 设计冻结

- 日期：2026-06-25
- 决策：所有页面 UI 布局、交互模式、组件排布冻结。后续版本不再修改 UI 元素的位置/样式/布局。
- 理由：UI 经过多轮需求对齐和重构（Gamut Calculator 布局重构、White Point 页面重构），当前实现已满足全部设计要求。冻结 UI 可将后续开发精力集中在功能 Bug 修复和算法改进上。
- 冻结范围：
  - Spectrum Library 页面：光谱导入/列表/预览/ECharts 交互
  - Gamut Calculator 页面：三栏布局（Spectrum Selection / CF Selection / Thickness）、Spectrum Preview 双标签（Original / Filtered）、CIE 1931 + CIE 1976 双图并排、RGB XYZ/色坐标数据面板、Gamut Result + White Point Result 分栏
  - White Point 页面：Forward / Reverse 模式切换、RGBW xy + Ratio 输入表格
  - Thickness Optimizer 页面：参数配置 + 优化结果面板
- 例外：仅允许修复功能性 Bug 所必须的极简 UI 修复（如标签拼写、tooltip 内容、状态显示逻辑），且须在 D-NNN 中记录。
- 影响：`docs/13_UI_Design_Freeze.md` 建立当前 frozen 基线。

## D-022：CIE 色度图固定背景 + 动态叠加

- 日期：2026-06-26
- 决策：CIE 1931 xy 与 CIE 1976 u\'v\' 色度图使用固定背景数据渲染；后端返回的 primaries/white 点仅作为动态层叠加在背景之上。
- 理由：
  - 用户可立即看到完整的色度图轮廓和标准色域参考，无需等待数据。
  - 避免因数据缺失导致坐标轴范围异常、图表空白或变形。
  - 固定坐标轴范围（xy [0,0.85]×[0,0.95]；uv [0,0.70]×[0,0.65]）使不同输入下的视觉对比一致。
- 影响：
  - 新增 `src/colorlab_pro/ui/web/cie_chromaticity_data.js`（由 `colour-science` 生成）。
  - `gamut_calculator_page.html` 与 `white_point_page.html` 的 CIE 渲染逻辑拆分为 `renderCIEBackground()` 与 `renderCIECharts()`。
  - 属于 D-021 UI 设计冻结的例外：功能性 Bug 修复，已记录。
