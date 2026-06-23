# ColorLab Pro V1.1 — Gamut Calculator UI 布局修改报告

> 修改时间：2026-06-19
> 修改文件：
> - `src/colorlab_pro/ui/pages/gamut_calculator_page.py`
> - `src/colorlab_pro/ui/widgets/cie_diagram.py`
> - `src/colorlab_pro/utils/default_data_loader.py`
> - `src/colorlab_pro/ui/app.py`
> - `src/colorlab_pro/controllers/main_controller.py`
>
> **最终布局已锁定，详见 `ai_context/GAMUT_UI_LOCK_SPEC.md`。**

## 修改内容

### 1. 全页面可拖动布局 + 状态保存

- 所有主要区域（控制面板、CIE 图、Spectrum Preview）改用 `QSplitter` 水平分割
- 用户可通过拖动分隔条自由调整各栏宽度
- 所有 `QSplitter` 设置 `setOpaqueResize(False)`，拖动时只显示虚线幻影框，不实时重绘图表，释放鼠标后才刷新
- 主垂直方向采用固定比例布局，不嵌套 `QScrollArea`
- 布局状态自动保存到 `QSettings`（`ColorLabPro/ColorLabPro/gamut_calculator_layout_v2`），下次打开时自动恢复
- 如需恢复默认布局，可删除对应注册表/配置文件项

### 2. 控制面板合并为紧凑一栏三列

- 原来三个独立 `QGroupBox`（Spectrum Selection / Color Filter Selection / Thickness Controls）并排显示，标题和边距占用较多垂直空间
- 现在合并为一个 `Input Parameters` 面板，内部使用水平 `QSplitter` 分为三列
- 每列标题改用粗体 `QLabel`，减少 `QGroupBox` 边距
- 三列默认宽度比例保持约 `2 : 2 : 3`

### 3. CIE 区域改为三栏：CIE 1931 / RGBW 数据表 / CIE 1976

- 原来左侧为 R/G/B 三个独立 GroupBox 的 XYZ/xy/u'v' 数据
- 现在改为单个 `RGBW Chromaticity Data` 表格，列：Channel, x, y, u', v', X, Y, CCT
- 表格行：R, G, B, White
- White 行显示混合白点的 x, y, u', v', X, Y, CCT（其中 X, Y 为 R/G/B 的叠加）
- CIE 1931 色度图位于数据表左侧，CIE 1976 色度图位于右侧

### 4. White Point Result 面板移除

- 原来 Results 区域右侧有独立的 `White Point Result` 面板
- 现在白点信息已整合进 CIE 区域的 RGBW 数据表
- Results 区域仅保留 `Gamut Result` 表格，独占整行

### 5. Spectrum Preview 位置调整与高度增加

- 位置从 CIE 图上方调整至 CIE 图下方
- 保持 Filtered / Original / Compare 三栏并排
- 每个图表最小高度从 120px 提升至 200px
- 垂直方向 stretch 比例从 22 提升至 35

### 6. 垂直比例调整

- 新比例：控制面板 10 : CIE 图 35 : Spectrum Preview 35 : Results 20
- 垂直方向保持不可拖动

### 7. Gamut Result 表格列宽一致

- 原来 `Match 1976` 列使用 `setStretchLastSection(True)`，占比过大
- 现在 5 列全部使用 `QHeaderView.ResizeMode.Stretch`，等分宽度

### 8. CIE 图绘制方式改为自定义 matplotlib 渲染

- 原来使用 `colour.plotting.plot_chromaticity_diagram_CIE1931` / `plot_chromaticity_diagram_CIE1976UCS`
- 现在参考项目根目录 `plot_cie_chromaticity.py` 的实现：
  - 生成 500×500 网格
  - 每个网格点转换为 XYZ 后再转换为 sRGB
  - 对每个像素按最大通道归一化增强显示
  - 使用 `matplotlib.path.Path.contains_points` 判断点是否在光谱轨迹内
  - 马蹄形内部显示颜色填充，外部使用深色背景
  - 绘制光谱轨迹线和 420–700 nm 波长刻度
- 同步修正了 xy → u'v' 转换公式的分母错误（旧代码为 `12y - 16x + 4`，现改为 `-2x + 12y + 3`）
- 坐标轴范围调整为：
  - xy: [0.0, 0.8] × [0.0, 0.9]
  - u'v': [0.0, 0.65] × [0.0, 0.65]

## 新布局自上而下

1. **Mode Selection**（RGB + Color Filter / White + Color Filter）
2. **Input Parameters（一栏三列）**
   - Spectrum
   - Color Filter
   - Thickness
3. **CIE Chromaticity Diagrams（一栏三列）**
   - CIE 1931 xy
   - RGBW Chromaticity Data 表格
   - CIE 1976 u'v'
4. **Spectrum Preview（一栏三列）**
   - Filtered Spectrum
   - Original Spectrum
   - Compare Mode
5. **Gamut Result（独占整行）**

## 验收截图

截图位置：`d:\0000TARE\ColorLab PRO\acceptance_screenshots\`

- `page_1_new_layout.png` — 新布局完整截图

## 测试验证

```powershell
.venv\Scripts\python.exe -m pytest -q --cov
```

结果：

```
477 passed, 0 failed
TOTAL 1750 statements, 40 missed, 97.71% coverage
Required test coverage of 90.0% reached.
```

```powershell
.venv\Scripts\python.exe -m ruff check src tests
```

结果：`All checks passed!`

## 9. 默认测试光谱数据

为便于反复测试 Gamut Calculator，新增默认测试数据自动加载机制：

- 新增 `src/colorlab_pro/utils/default_data_loader.py`
  - 在 `test_data/` 目录中查找 6 组光谱：
    - `BLED.csv` → 通道 B
    - `QD_Red.csv` → 通道 R
    - `QD_Green.csv` → 通道 G
    - `CF_Red.csv` → 通道 RCF
    - `CF_Green.csv` → 通道 GCF
    - `CF_Blue.csv` → 通道 BCF
  - 自动创建名为 `Default Demo` 的项目（如不存在）
  - 幂等：已存在同名光谱时跳过，不会重复导入
- 修改 `src/colorlab_pro/ui/app.py`
  - 在 `main_ctrl.initialize()` 之后调用 `load_default_spectra(main_ctrl)`
  - 首次启动或删除默认数据库后，打开应用即可直接看到预置光谱
- 修改 `src/colorlab_pro/controllers/main_controller.py`
  - 使用 `database.session.init_schema()` 初始化数据库，确保旧数据库自动迁移（例如补全 `spectra.category` 列）

测试数据文件位置：`d:\0000TARE\ColorLab PRO\test_data\`

## 10. White Point 页面增加色域分析功能

在 `src/colorlab_pro/ui/pages/white_point_page.py` 中新增 **Gamut Analysis** 区域：

- 输入 RGB 坐标后点击 Calculate，自动完成以下计算与展示：
  - 正向/反向计算得到白点 xy
  - 使用 `engines.gamut_calculator.xy_to_uv` 将 xy 转换为 u'v'
  - 使用 `build_gamut_from_primaries` 构建设备色域
  - 使用 `coverage` / `match` / `coverage_1976` / `match_1976` 计算与 NTSC / DCI-P3 / BT2020 的色域覆盖率和匹配率
  - 使用 `CIECanvas` 绘制 CIE 1931 xy 与 CIE 1976 u'v' 色度图，显示 RGB 三角、白点和参考色域
- 新增 `Gamut Result` 表格，列与 Gamut Calculator 保持一致：
  - Standard / Coverage 1931 (%) / Match 1931 (%) / Coverage 1976 (%) / Match 1976 (%)
- 同步在 `src/colorlab_pro/engines/gamut_calculator.py` 的 `_GAMUT_SPECS` 中补全 `BT2020` 标准色域数据

## 11. White Point 页面布局压缩与比例归一化

将 White Point 页面原本垂直堆叠的 **RGB Coordinates**、**RGB Ratios**、**Result/Target** 三个区域合并为 **一栏三列** 的 `Input & Result` 面板，显著减少纵向占用：

- 第 1 列：`RGB Coordinates`（R/G/B 的 x、y 输入）
- 第 2 列：`RGB Ratios`（R/G/B 比例输入，联动且和为 1，底部显示 `Sum: x.xxxx`）
- 第 3 列：`Result`
  - 正向模式：显示 White Point、x、y、u'、v'、CCT
  - 反向模式：显示 Target x/y 输入 + R/G/B Ratio、Delta xy

新增 `_RatioPanel` 辅助类，实现比例联动逻辑：

- 任一比例变化时，自动按其余两者当前比例缩放，确保 `R + G + B = 1`
- 当其余两者均为 0 时，将剩余值平均分配
- 底部 Sum 标签在误差小于 0.001 时显示绿色，否则显示红色

计算逻辑调整：

- 正向计算从 `_ratio_panel.values()` 读取比例，计算前再次归一化，确保数值稳定
- 反向计算输出比例改为归一化到 `sum = 1`，与面板显示一致

验收截图：`acceptance_screenshots/page_2_whitepoint_compact.png`

## 12. Gamut Calculator 性能优化

针对点击 Gamut Calculator 页面卡顿的问题进行 profiling，发现主要瓶颈：

1. `src/colorlab_pro/ui/main_window.py` 中 `set_page()` 既直接 emit `page_about_to_show`，又更新 sidebar 触发 `_on_nav_changed()` 再次 emit，导致 `_on_page_show()` 被执行 3 次，`_recalculate()` 被调用 3 次
2. `src/colorlab_pro/ui/widgets/cie_diagram.py` 的 CIE 背景每次渲染都重新计算 500×500 像素 horseshoe

优化措施：

- 修改 `MainWindow.set_page()`：仅更新 sidebar current row，页面切换和信号统一由 `_on_nav_changed()` 处理，消除重复事件
- 修改 `CIECanvas`：
  - 新增 `_bg_cache`，对 xy/uv 静态背景图、光谱轨迹、波长标签进行实例级缓存
  - 光谱轨迹 `_compute_spectrum_locus_xy()` 使用模块级全局缓存
  - CIE 背景分辨率从 500 降至 200，背景渲染时间大幅下降
- 优化效果：首次切换到 Gamut Calculator 耗时从约 3800 ms 降至约 1300 ms；重复计算次数从 3 次降至 1 次

验收截图：`acceptance_screenshots/page_1_default_data_auto.png`

## 备注

- offscreen 环境下中文字体渲染为方块，这是环境字体缺失问题，不影响真实桌面显示。
- 线框图文件：`wireframe_gamut_page.html`（已过期，以本文档描述为准）
