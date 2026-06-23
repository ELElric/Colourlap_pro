# Gamut Calculator 页面 UI 设计规范

> 文档状态：已确认生效
> 适用范围：`src/colorlab_pro/ui/pages/gamut_calculator_page.py` 及其直接依赖的 `cie_diagram.py` 相关公共接口
> 管理声明：**未经用户明确要求，不得修改本页面 UI 布局、结构、尺寸策略或交互方式。**
>
> 用户已确认的最新变更（2026-06-19）：
> - CIE 区域改为三栏：CIE 1931 xy / RGBW 色坐标数据表 / CIE 1976 u'v'
> - RGBW 数据表格式：Channel, x, y, u', v', X, Y, CCT
> - 控制面板合并为紧凑一栏三列
> - Spectrum Preview 位于 CIE 图下方且高度增加
> - Results 区域仅保留 Gamut Result 表格

## 1. 设计目标

Gamut Calculator 是 ColorLab Pro 的核心色域计算页面，需要同时满足：

- 信息密度高：在单屏内展示光谱选择、彩膜选择、厚度控制、CIE 色度图、光谱预览、色域结果
- 布局清晰：各功能区职责明确，避免用户混淆
- 可自定义：允许用户拖动调整各区域水平宽度，并保存为个人默认布局

## 2. 整体布局（自上而下）

页面采用固定比例的垂直布局（上下不可拖动），从上到下依次为：

```
┌─────────────────────────────────────────────────────┐
│ Mode Selection                                      │  固定高度，不拖动
├─────────────────────────────────────────────────────┤
│ Input Parameters                                    │  水平 QSplitter
│ ├─ Spectrum ─┼─ Color Filter ─┼─ Thickness ─┤      │   (10%)
├─────────────────────────────────────────────────────┤
│ CIE Chromaticity Diagrams                           │  水平 QSplitter
│ ├─ CIE 1931 xy ┼─ RGBW Data Table ┼─ CIE 1976 u'v' ┤│   (35%)
├─────────────────────────────────────────────────────┤
│ Spectrum Preview                                    │  水平 QSplitter
│ ├─ Filtered Spectrum ─┼─ Original Spectrum ─┼─     ││   (35%)
│    Compare Mode                                     ││
├─────────────────────────────────────────────────────┤
│ Gamut Result                                        │  独占整行
└─────────────────────────────────────────────────────┘   (20%)
```

垂直比例：控制面板 10 : CIE 图 35 : Spectrum Preview 35 : Results 20

## 3. 各区域详细规范

### 3.1 Mode Selection

- 位置：页面最顶部，固定高度，不参与 QSplitter 拖动
- 内容：一个 `QComboBox`，包含两个选项
  - `RGB + Color Filter`
  - `White + Color Filter`
- 行为：切换模式时，下方 `Spectrum` 列在 RGB 选择器与白光选择器之间切换

### 3.2 控制面板（Input Parameters）

使用一个 `QGroupBox` 包裹，内部使用水平 `QSplitter` 分为三列：

#### 3.2.1 Spectrum

- 标题：以 QLabel 粗体显示 `Spectrum`
- RGB 模式：三行 `R / G / B` 选择器
- White 模式：一行 `W` 选择器
- 每行组成：
  - 通道标签
  - 下拉框（`QComboBox`，最小宽度 80px，可随面板扩展）
  - `Paste` 按钮（固定宽度，根据字体宽度动态计算，不随面板扩展）
- 列最小宽度：240px

#### 3.2.2 Color Filter

- 标题：以 QLabel 粗体显示 `Color Filter`
- 三行 `RCF / GCF / BCF` 选择器
- 每行组成与 Spectrum 一致
- 列最小宽度：240px

#### 3.2.3 Thickness

- 标题：以 QLabel 粗体显示 `Thickness`
- 三行 `RCF / GCF / BCF` 厚度控制
- 每行组成：
  - 标签 `RCF:` 等
  - `[-]` 按钮（固定宽度，根据字体动态计算）
  - `QDoubleSpinBox`（显示当前膜厚，单位 `X`，固定宽度 86px）
  - `[+]` 按钮（固定宽度）
  - `Step:` 标签
  - Step 设置 `QDoubleSpinBox`（固定宽度 72px）
- 列最小宽度：320px

### 3.3 CIE Chromaticity Diagrams

- 标题：`CIE Chromaticity Diagrams`
- 使用水平 `QSplitter` 并排显示三栏：
  - 第一栏：`CIECanvas(mode="xy")` — CIE 1931 xy 色度图
  - 第二栏：**RGBW Chromaticity Data** — 以表格形式显示 R/G/B/White 的色坐标、XYZ 和 CCT
    - 表格列：`Channel`、`x`、`y`、`u'`、`v'`、`X`、`Y`、`CCT`
    - 表格行：`R`、`G`、`B`、`White`
    - 使用 `QTableWidget`，不可编辑，不可选择，列宽自动拉伸
    - 面板最小宽度：260px
  - 第三栏：`CIECanvas(mode="uv")` — CIE 1976 u'v' 色度图
- 背景绘制：使用项目根目录 `plot_cie_chromaticity.py` 中的自定义 matplotlib 渲染方式
  - 生成 500×500 的 xy（或 u'v'）网格
  - 每个网格点转换为 XYZ 后再转换为 sRGB 显示色
  - 对每个像素按最大通道归一化，增强颜色显示效果
  - 使用 `matplotlib.path.Path.contains_points` 判断点是否在光谱轨迹多边形内
  - 多边形内部显示颜色填充，外部使用页面背景色（`#1E1E1E`）
  - 绘制光谱轨迹线（黑色/主题色）和紫线（380 nm 与 780 nm 连线）
  - 在轨迹上标注 420–700 nm 的主波长刻度
- 坐标轴范围：
  - CIE 1931 xy：`x ∈ [0.0, 0.8]`，`y ∈ [0.0, 0.9]`
  - CIE 1976 u'v'：`u' ∈ [0.0, 0.65]`，`v' ∈ [0.0, 0.65]`
- 顶部工具栏：
  - `Show Original` / `Show Filtered` / `Show White Point`
  - `Show Trajectory` / `Show Triangle`
  - 参考色域复选框：`sRGB`、`NTSC`、`DCI-P3`、`BT2020`

### 3.4 Spectrum Preview

- 标题：`Spectrum Preview`
- 使用水平 `QSplitter` 三栏并排，不使用 Tab：
  - `Filtered Spectrum`
  - `Original Spectrum`
  - `Compare Mode`
- 每个图表使用 `SpectrumChartWidget`，设置 `Expanding` size policy
- 每个图表最小高度：200px
- 位于 CIE 图之下

### 3.5 Results 区域

独占整行，仅保留 Gamut Result：

- 标题：`Gamut Result`
- 使用 `QTableWidget`，5 列：
  - `Standard`
  - `Coverage 1931 (%)`
  - `Match 1931 (%)`
  - `Coverage 1976 (%)`
  - `Match 1976 (%)`
- 列宽策略：`QHeaderView.ResizeMode.Stretch`，5 列等分
- 行：NTSC、DCI-P3、BT2020

## 4. 尺寸与缩放策略

### 4.1 控件固定策略

以下控件应使用固定宽度，不随 splitter 拖动而大幅变化：

- `Paste` 按钮
- `[-]` / `[+]` 按钮
- 通道标签 `R / G / B / W / RCF / GCF / BCF`
- 膜厚 `QDoubleSpinBox`
- Step `QDoubleSpinBox`

### 4.2 控件扩展策略

以下控件应随面板宽度扩展：

- `Spectrum` 和 `Color Filter` 列中的下拉框
- `SpectrumChartWidget` 三个图表
- `CIECanvas` 两个色度图
- `RGBW Chromaticity Data` 表格
- `Gamut Result` 表格整体

### 4.3 最小宽度限制

| 区域 | 最小宽度 |
|------|---------|
| Spectrum 列 | 240px |
| Color Filter 列 | 240px |
| Thickness 列 | 320px |
| RGBW Chromaticity Data 面板 | 260px |
| Gamut Result 表格 | 500px |

## 5. 可拖动布局与状态保存

### 5.1 QSplitter 使用规则

- **水平方向**使用 `QSplitter` 分割（控制面板三列、Spectrum Preview 三栏、CIE 图三栏）
- **垂直方向**采用固定比例布局，**不可拖动**
- `setChildrenCollapsible(False)`，防止用户把某个区域完全收起
- `setHandleWidth(5-6)`，提供清晰的拖动条
- 水平 `QSplitter` 设置 `setOpaqueResize(False)`：拖动时仅显示虚线幻影框，不实时调整子控件大小，不触发图表重绘；释放鼠标后才应用新布局并刷新

### 5.2 状态保存

- 保存方式：`QSettings("ColorLabPro", "ColorLabPro")`
- 键名：`gamut_calculator_layout_v2`
- 保存内容：所有**水平** `QSplitter` 的 `saveState()`（垂直方向不再保存，因为不可拖动）
- 触发时机：任意 splitter 的 `splitterMoved` 信号
- 恢复时机：页面构造完成后调用 `_restore_layout()`

### 5.3 默认布局

首次打开或未找到保存状态时，使用代码中的默认尺寸：

- 垂直方向比例：`10 : 35 : 35 : 20`（控制面板 : CIE 图 : Spectrum Preview : Results）
- 控制面板水平 splitter：`[180, 180, 260]`
- CIE 图水平 splitter：`[240, 260, 380]`
- Spectrum Preview 水平 splitter：`[270, 270, 270]`

## 6. 修改限制声明

**本页面的 UI 布局、结构、尺寸策略、交互方式已经过用户确认并写入本文档。**

**未经用户明确要求，不得进行以下修改：**

- 调整各区域的排列顺序
- 增删主要功能区域
- 修改 QSplitter 的层级关系
- 改变控件固定/扩展策略
- 调整各面板最小宽度阈值
- 修改状态保存键名或保存格式

如果用户提出新的布局需求，应：

1. 先与用户确认具体变更内容
2. 必要时重新绘制线框图
3. 修改代码
4. 更新本文档

## 7. 相关文件

- `src/colorlab_pro/ui/pages/gamut_calculator_page.py`
- `src/colorlab_pro/ui/widgets/cie_diagram.py`
- `ai_context/UI_LAYOUT_CHANGE.md`（修改历史）
