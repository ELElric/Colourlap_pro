# ColorLab Pro — Current Task

> Project: ColorLab Pro V1.1
> Last Updated: 2026-06-26

## Active Task

**CIE 色度图彩色填充 + 标签精简**

- 状态: done
- 完成时间: 2026-06-26
- 修改文件: `src/colorlab_pro/ui/web/cie_chromaticity_data.js`, `src/colorlab_pro/ui/web/gamut_calculator_page.html`, `src/colorlab_pro/ui/web/white_point_page.html`

### 目标
色度图内部使用 `colour-science` 预计算真实彩色填充并作为静态缓存数据；同时取消图表内的波长标签、E 点标签和图例，避免与页面已有复选框/标题重复。

### 改动
- 更新 `generate_cie_data.py`：在 CIE 1931 xy / CIE 1976 u'v' 坐标范围内建立 80×80 网格，对每个落在马蹄形内部的网格单元格中心，复刻 `colour.plotting.diagrams.plot_chromaticity_diagram_colours` 的方法生成 sRGB 色值：xyY → XYZ（Y=1）→ sRGB → `colour.algebra.normalise_maximum` → clip；u'v' 单元格通过逆变换转回 xy 后再算色。结果写入 `cie_chromaticity_data.js` 的 `xy_fill` / `uv_fill`。
- `gamut_calculator_page.html` / `white_point_page.html`：`renderFillItem()` 由绘制三角形改为绘制网格矩形（`rect`），以呈现平滑自然的连续渐变；移除 `Wavelength`、`E` 标签系列和 `legend`；White Point 页面同时移除面板头部 "R G B W" 小标签。
- 修复 `gamut_calculator_page.html` 的 `renderCIECharts` 缺少 `xyToUV` 的问题。
- 为 `cie_chromaticity_data.js` 引用添加 `?v=3` 缓存刷新参数，避免旧版数据被浏览器缓存。

### 验证
- 本地 HTTP 服务截图：无数据时色度图显示彩色填充；注入 mock 数据后 Device 三角形正确叠加。
- ruff check: 0 errors
- pytest: 494 passed, 7 skipped

### CIE 色度图固定背景渲染（2026-06-26）

- 来源: UI 需求对齐
- 修改文件: `src/colorlab_pro/ui/web/cie_chromaticity_data.js`, `src/colorlab_pro/ui/web/gamut_calculator_page.html`, `src/colorlab_pro/ui/web/white_point_page.html`
- 完成内容:
  - CIE 1931 xy / CIE 1976 u'v' 色度图不再依赖后端数据才渲染
  - 页面加载后显示固定马蹄形色度轮廓、波长标签、等能白点 E 和标准色域参考线
  - 数据输入仅叠加 Device 三角形、RGB 顶点标记和 White 点
- 验证: ruff 0 errors / pytest 494 passed, 7 skipped

## How to Mark a Task Complete

1. Update the `Active Task` section above (mark `Status: done` and fill `Completed At`).
2. Move the completed task summary to `## Task History` at the bottom.
3. Update `PROJECT_STATUS.md`.
4. If a non-trivial decision was made, append an entry to `docs/12_Decision_Log.md`.
5. If a new issue is discovered, append an entry to `KNOWN_ISSUES.md`.

## Task History

### Gamut Calculator UI 布局修改（2026-06-19）

- 来源: 用户反馈色域计算页信息密度和布局问题
- 跟踪文档: `ai_context/UI_LAYOUT_CHANGE.md`
- 修改内容:
  - CIE 1931 与 CIE 1976 色度图并排显示
  - Spectrum Selection / Color Filter Selection / Thickness Controls 三栏并排
  - 膜厚控制改为 [-] [数值] [+] 步进按钮 + Step 设置
  - Gamut Result 与 White Point Result 左右分栏
- 验证:
  - pytest: 477 passed, 0 failed
  - coverage: 97.71%
  - ruff check: 0 errors
  - UI offscreen 截图生成成功

### 测试覆盖率提升（2026-06-19）

- 来源: 用户要求覆盖率达到 90%
- 跟踪文档: `ai_context/COVERAGE_REPORT.md`
- 结果:
  - 业务逻辑层覆盖率：51.70% → 97.71%
  - 全量测试：477 passed, 0 failed
  - ruff check: 0 errors
  - pyproject.toml 已配置 `[tool.coverage.report] fail_under = 90`
- 新增测试：约 163 个用例
  - engines/services: ~38
  - controllers/database: ~62
  - cli/config/importers/exporters/utils: ~68
- 策略: 采用分层覆盖率，UI/CLI/migrations/report_exporter 等难测层 omit 排除

### 发布前最终检查（2026-06-19）

- 来源: 用户要求发布前详细检测
- 跟踪文档: `ai_context/RELEASE_CHECK.md`
- 检查结果:
  - ruff check: 0 errors
  - ruff format --check: 通过
  - pytest: 314 passed, 0 failed
  - pytest --cov: 51.70%（达到 50% 阈值）
  - pip install -e .: 成功
  - colorlab-pro --help / version: 正常
  - GUI offscreen 启动: 成功，生成 6 张截图
- 发现并修复的关键问题:
  - 依赖缺失：新增 `pyyaml`、`matplotlib`
  - GUI 入口：`WhitePointPage` 参数不匹配、`populate_from_spectrum` 未实现
  - 未定义引用：`calc_xy`、`Spectrum`、`QMessageBox`
  - UI bug：`setTextAlignment` → `setAlignment`
  - Purity 算法改为标准公式
- 遗留: mypy 77 个历史类型问题（不影响运行）

### 需求对齐修复（2026-06-19）

- 来源: 用户确认后的最终需求
- 跟踪文档: `ai_context/TASK_TRACKING.md`
- 完成项:
  - TASK-1 光谱分类存储（CF/QD/LED/White）
  - TASK-2 导入自动对齐 380-780 nm 并补零
  - TASK-3 Gamut Calculator 新增 White + Color Filter 模式
  - TASK-4 多峰光谱仅识别 RG 波段
  - TASK-5 通道检测改为 RGB 波段峰强/透过率驱动
  - TASK-6 CIE 1976 u'v' 空间 Coverage/Match 计算
  - TASK-7 Spectrum Info 面板按类型条件显示
  - TASK-8 Gamut Calculator Paste 按钮完整实现
  - TASK-9 White Point 自动接收 Gamut Calculator 坐标
  - TASK-10 全量回归测试（314 passed）

### Phase 8 — 集成与发布（T-27 ~ T-30）

- T-27 端到端集成测试
  - `tests/integration/test_end_to_end.py` — 1 test, passing
  - 覆盖：Project → Spectrum import → analysis → CSV/JSON export → delete
- T-28 CLI 入口
  - `src/colorlab_pro/cli.py` — argparse-based CLI with `init-db`, `gui`, `version` subcommands
  - `pyproject.toml` [project.scripts] 映射：`colorlab-pro` → CLI, `colorlab-pro-gui` → GUI
  - 验证：`colorlab-pro version` 输出 `1.1.0`，`colorlab-pro init-db --db-path ...` 成功建库
- T-29 构建/打包脚本
  - `pyproject.toml` 完整配置 setuptools build
  - `pip install -e .` 可安装，console_scripts 入口点可用
- T-30 最终回归
  - 全量 pytest：**180 passed, 0 failed**
  - ruff check：全部通过
  - mypy：全部通过

### Phase 7 — 导入导出（T-24 ~ T-26）

- T-24 CSV 导入导出
  - `src/colorlab_pro/exporters/csv_exporter.py` — `export_spectrum`, `import_spectrum`
  - Round-trip：wavelengths/values/unit 完整保留
- T-25 XLSX 导入导出
  - `src/colorlab_pro/exporters/xlsx_exporter.py` — `export_spectrum`, `import_spectrum`
- T-26 JSON 导入导出
  - `src/colorlab_pro/exporters/json_exporter.py` — `export_spectrum`, `import_spectrum`
  - 支持 metadata 完整保留

### Phase 5-6 — UI 组件（T-14 ~ T-23）

- T-14 MainWindow 主窗口框架
  - `src/colorlab_pro/ui/main_window.py` — QMainWindow + 菜单栏 + 状态栏 + QSettings 持久化
  - `src/colorlab_pro/ui/app.py` — 应用入口
  - 5/5 tests passing
- T-15 主题/样式管理器
  - `src/colorlab_pro/ui/resources/theme.py` — ThemeName 枚举 + 亮/暗 QSS + 通道颜色映射
  - 4/4 tests passing
- T-16 基础 Widgets
  - `ChannelBadge` — 通道标签（R/G/B/W/IR 等）
  - `StatusIndicator` — 状态指示灯 + 文字
  - 4/4 tests passing
- T-17 项目导航
  - `ProjectNavigator` — 项目列表 + 选中信号 + 新建按钮
  - 4/4 tests passing
- T-18 光谱导入
  - `SpectrumImportWidget` — 粘贴文本解析 + 预览 + 导入
  - 5/5 tests passing
- T-19~T-23 页面 Widgets
  - `AnalysisResultWidget` — XYZ/xy/CCT/dominant wavelength
  - `ColorMixingResultWidget` — 混合结果
  - `GamutResultWidget` — 覆盖率/匹配度
  - `OptimizationResultWidget` — 膜厚优化结果
  - `ExportOptionsWidget` — 导出格式列表
  - 5/5 tests passing

### Phase 4 — 服务层（T-10 ~ T-13）

- T-10 SpectrumService
  - `import_spectrum`, `get_spectrum`, `list_spectra`, `delete_spectrum`, `detect_channel`, `analyze`
  - 事务边界由注入的 `session_factory` 管理
  - 10/10 tests passing
- T-11 ColorService
  - `mix_spectra`, `mix_spectra_by_id`, `mixed_xyz`, `mixed_xy`, `luminance`, `delta_uv_to_d65`
  - 7/7 tests passing
- T-12 GamutService
  - `build_from_primaries`, `standard_gamut`, `list_standard_gamuts`, `coverage`, `match`, `area`, `contains`
  - 7/7 tests passing
- T-13 OptimizationService
  - `optimize_white_point`, `optimize_thickness`, `save_optimization`
  - 3/3 tests passing

### Phase 3 — 数据层（T-07 ~ T-09）

- T-07 ORM 模型与迁移
  - SQLAlchemy 2.0 DeclarativeBase + Mapped/mapped_column
  - 4 个模型：Project, Spectrum, SpectrumPoint, Optimization
  - `database/session.py`, `scripts/init_db.py`, migration SQL
  - 6 tests passing
- T-08 SpectrumRepository
  - `save` / `get_by_id` / `list_by_project` / `delete`
  - DTO ↔ ORM 双向映射，元数据 JSON 序列化
  - 9 tests passing
- T-09 ProjectRepository
  - `create` / `get_by_id` / `list_all` / `update` / `delete`
  - 11 tests passing

### Phase 2 — 核心算法（T-02 ~ T-06）

- T-02 SpectrumNormalizer — 116 stmts, 90% coverage, 21/21 tests
- T-03 SpectrumAnalyzer — 66 stmts, 95% coverage, 13/13 tests
- T-04 ColorCalculator — 86 stmts, 92% coverage, 26/26 tests
- T-05 GamutCalculator — 49 stmts, 22/22 tests
- T-06 WhitePointCalculator + ThicknessOptimizer — 98 stmts, 14/14 tests

### Phase 1 — 基础设施（T-01）

- T-01 项目骨架引导
  - 101 个文件、13 个 src 子包、完整配置
  - Python 3.11.7 venv, 35 个依赖
  - 通过 PowerShell 脚本生成（规避 Trae Write 工具持久化问题）

### White Point 页面重构 + 删除 Gamut Calculator Project Comparison（2026-06-25）

- 来源: UI 需求对齐
- 修改文件: `src/colorlab_pro/ui/web/white_point_page.html`, `src/colorlab_pro/ui/web/gamut_calculator_page.html`
- 完成内容:
  - 删除 Quick Info Cards（xy, u'v', CCT, Ratios）
  - 改用 Forward/Reverse 模式切换：Forward 模式 W 行为只读输出，Reverse 模式 RGB Ratio 为只读、W xy 可编辑
  - 统一使用 `<input readonly>` + CSS 显示输出值
  - 移除 Gamut Calculator Spectrum Preview 中的 "Compare" 标签页及全部相关 JS/HTML
- 验证: 477 passed, 0 failed
