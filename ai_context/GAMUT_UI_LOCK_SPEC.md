# Gamut Calculator 页面 UI 设计锁定规范

> **锁定状态：FROZEN**
>
> 本页面已按产品要求完成最终布局设计，当前实现是经过多轮调整后的定稿版本。
> **任何 AI 或开发者在未经明确授权的情况下，不得修改本页面的布局、比例、组件顺序、分栏方式、配色或核心交互逻辑。**
> 若确需调整，必须先由产品负责人确认，并同步更新本规范与截图验收。

---

## 1. 页面定位

Gamut Calculator 是 ColorLab Pro 的核心色域计算页面，用于：

- 选择 RGB 背光光谱或白光光谱
- 选择 RCF / GCF / BCF 彩膜光谱
- 设置彩膜厚度
- 计算并展示 CIE 1931 xy、CIE 1976 u'v' 色度图
- 展示 RGBW 色坐标、XYZ、CCT 数据
- 预览原始光谱与过滤后的光谱
- 输出 NTSC / DCI-P3 / BT2020 色域覆盖率与匹配率

---

## 2. 整体布局（严禁改动）

页面采用**垂直固定比例布局**，主区域使用 `QVBoxLayout`，**不允许垂直拖动改变行高**。

从上到下依次分为 5 个区域：

```
┌─────────────────────────────────────────────────────────────┐
│ 0. Mode Selection（固定高度，不拖动）                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Input Parameters（一栏三列，水平可拖动）                    │
│    [ Spectrum | Color Filter | Thickness ]                  │
├─────────────────────────────────────────────────────────────┤
│ 2. CIE Chromaticity Diagrams（一栏三列，水平可拖动）           │
│    [ Chromaticity Data | CIE 1931 xy | CIE 1976 u'v' ]      │
├─────────────────────────────────────────────────────────────┤
│ 3. Spectrum Preview（一栏三列，水平可拖动）                    │
│    [ Filtered | Original | Compare ]                        │
├─────────────────────────────────────────────────────────────┤
│ 4. Gamut Result（独占一行，固定高度）                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 垂直区域比例

主内容区 4 大板块的 stretch 比例为：

| 区域 | stretch | 说明 |
|---|---|---|
| Input Parameters | 10 | 紧凑控制区，刚好容纳一行三列 |
| CIE Chromaticity Diagrams | 35 | CIE 图是信息重点，占比最大 |
| Spectrum Preview | 35 | 与 CIE 图同高，保证预览可读性 |
| Gamut Result | 20 | 结果表格，不需要过大 |

**禁止项**：

- 不得将上述 4 个区域改为 `QSplitter` 垂直拖动
- 不得增加第 5 个垂直区域
- 不得改变各区域的上下顺序
- 不得将 CIE 图与 Preview 互换位置

---

## 3. 各区域详细规范

### 3.1 Mode Selection

- 位于页面最顶部
- 仅包含一个 `QComboBox`，选项为：
  - `RGB + Color Filter`
  - `White + Color Filter`
- 选择模式时切换 Spectrum 区域显示 RGB 选择器或 White 选择器
- **位置与内容不可改动**

### 3.2 Input Parameters（一栏三列）

整体为一个 `QGroupBox("Input Parameters")`，内部使用**水平 `QSplitter`** 分为三列。

#### 第 1 列：Spectrum

- 标题：`Spectrum`
- RGB 模式下显示 R / G / B 三个 `_SpectrumSelector`
- White 模式下显示 W 一个 `_SpectrumSelector`
- 每个选择器由 `QLabel(通道名)` + `QComboBox` + `Paste 按钮` 组成
- Paste 按钮宽度固定，不随 splitter 拉伸

#### 第 2 列：Color Filter

- 标题：`Color Filter`
- 显示 RCF / GCF / BCF 三个 `_SpectrumSelector`

#### 第 3 列：Thickness

- 标题：`Thickness`
- 显示 RCF / GCF / BCF 三个 `_ThicknessControl`
- 每个厚度控制由 `[-]` + `QDoubleSpinBox` + `[+]` + `Step` 组成

**禁止项**：

- 不得将三列拆分为三个独立 GroupBox 上下堆叠
- 不得改变三列顺序
- 不得删除 Paste 按钮或厚度 Step 控件

### 3.3 CIE Chromaticity Diagrams（一栏三列）

整体为一个 `QGroupBox("CIE Chromaticity Diagrams")`，顶部有工具栏，下方使用**水平 `QSplitter`** 分为三列。

#### 工具栏（固定）

从左到右依次为：

- `Show Original`（默认勾选）
- `Show Filtered`（默认勾选）
- `Show White Point`（默认勾选）
- `Show Trajectory`（默认勾选）
- `Show Triangle`（默认勾选）
- 右侧参考色域复选框：`sRGB`、`NTSC`、`DCI-P3`、`BT2020`
  - `sRGB` 默认不勾选
  - `NTSC`、`DCI-P3`、`BT2020` 默认勾选

#### 第 1 列：Chromaticity Data

- 使用 `QGroupBox("Chromaticity Data")`
- 内部是一个 4 行 8 列的 `QTableWidget`
- 表头固定为：`Channel`、`x`、`y`、`u'`、`v'`、`X`、`Y`、`CCT`
- 4 行分别对应：`R`、`G`、`B`、`White`
- 表格只读、不可选择、无垂直表头

#### 第 2 列：CIE 1931 xy

- 使用 `CIECanvas(mode="xy")`
- 默认参考色域：`NTSC`、`DCI-P3`、`BT2020`
- 最小高度：`200`

#### 第 3 列：CIE 1976 u'v'

- 使用 `CIECanvas(mode="uv")`
- 默认参考色域：`NTSC`、`DCI-P3`、`BT2020`
- 最小高度：`200`

**禁止项**：

- 不得将 CIE 1931 与 CIE 1976 上下堆叠
- 不得删除 RGBW 数据表
- 不得改变数据表列顺序或表头
- 不得将 White Point 信息移出此区域（已统一放在 `White` 行）

### 3.4 Spectrum Preview（一栏三列）

整体为一个 `QGroupBox("Spectrum Preview")`，内部使用**水平 `QSplitter`** 分为三栏。

- 第 1 栏：`Filtered Spectrum`
- 第 2 栏：`Original Spectrum`
- 第 3 栏：`Compare Mode`

每栏包含一个标题标签和一个 `SpectrumChartWidget`，最小高度 `200`。

**禁止项**：

- 不得将三栏叠加为一个可切换的图表
- 不得减少为两栏
- 不得改变三栏顺序

### 3.5 Gamut Result

- 单独一个 `QGroupBox("Gamut Result")`
- 内部是一个 `QTableWidget`
- 表头固定为：`Standard`、`Coverage 1931 (%)`、`Match 1931 (%)`、`Coverage 1976 (%)`、`Match 1976 (%)`
- 3 行分别对应：`NTSC`、`DCI-P3`、`BT2020`
- 表格只读、无垂直表头

**禁止项**：

- 不得将 White Point Result 面板重新加回来
- 不得改变表格列顺序

---

## 4. 关键组件规范

### 4.1 _SpectrumSelector

```python
class _SpectrumSelector(QWidget):
    selectionChanged = Signal()
```

- 水平布局：`QLabel(通道名)` + `QComboBox` + `QPushButton("Paste")`
- 通道标签固定宽度 24px，使用通道颜色：
  - R：`#FF4444`
  - G：`#44FF44`
  - B：`#4488FF`
- Paste 按钮宽度按文本自适应，保持固定
- 下拉框最小宽度 80px

### 4.2 _ThicknessControl

```python
class _ThicknessControl(QWidget):
    valueChanged = Signal(float)
```

- 水平布局：`[-]` + `QDoubleSpinBox` + `[+]` + `Step:` + `QDoubleSpinBox`
- 厚度范围：`0.1 ~ 5.0`，默认值 `1.0`，步进 `0.01`
- 后缀为 `X`

### 4.3 QSettings 布局持久化

```python
_SETTINGS_ORG = "ColorLabPro"
_SETTINGS_APP = "ColorLabPro"
_SETTINGS_KEY = "gamut_calculator_layout_v2"
```

- 仅保存水平 splitter 状态
- 垂直比例由代码固定，不保存也不恢复
- 当 QSettings 中无值时使用代码中的默认 splitter sizes

---

## 5. 行为逻辑规范

### 5.1 默认光谱自动选择

首次切换到 Gamut Calculator 页面时，如果当前未选择任何光谱，按通道自动匹配并选择默认光谱：

| UI 通道 | 匹配光谱 channel |
|---|---|
| R | R |
| G | G |
| B | B |
| RCF | RCF |
| GCF | GCF |
| BCF | BCF |

实现要求：

- 批量设置下拉框时必须先 `blockSignals(True)`
- 全部设置完成后再统一加载 Spectrum DTO
- 最后只调用一次 `_recalculate()`
- 如果用户已经手动选择了任意光谱，不得覆盖用户选择

### 5.2 计算触发条件

以下事件会触发 `_recalculate()`：

- RGB 任一通道选择变化
- White 通道选择变化
- Color Filter 任一通道选择变化
- 任一 Thickness 值变化

### 5.3 模式切换

Mode 下拉框切换时：

- `RGB + Color Filter`：显示 R/G/B 选择器，隐藏 W 选择器
- `White + Color Filter`：隐藏 R/G/B 选择器，显示 W 选择器

---

## 6. 涉及文件

| 文件 | 作用 | 修改限制 |
|---|---|---|
| `src/colorlab_pro/ui/pages/gamut_calculator_page.py` | 页面主实现 | **禁止修改布局与核心逻辑** |
| `src/colorlab_pro/ui/widgets/cie_diagram.py` | CIE 图绘制 | 仅可修复渲染 bug，不得改坐标范围/背景算法 |
| `src/colorlab_pro/ui/widgets/spectrum_chart.py` | 光谱图绘制 | 仅可修复渲染 bug |
| `src/colorlab_pro/utils/default_data_loader.py` | 默认测试数据加载 | 可更新光谱文件映射，但不得改加载时机 |
| `src/colorlab_pro/ui/app.py` | 应用启动入口 | 默认数据加载调用不可删除 |
| `src/colorlab_pro/controllers/main_controller.py` | 数据库初始化 | 已改为 `init_schema`，不得回退 |
| `ai_context/GAMUT_UI_SPEC.md` | 原始 UI 规范 | 已由本文档替代 |
| `ai_context/UI_LAYOUT_CHANGE.md` | 布局变更历史 | 可继续追加变更记录 |
| `ai_context/GAMUT_UI_LOCK_SPEC.md` | 本文档 | 每次授权变更后必须更新 |

---

## 7. 锁定规则（必读）

以下事项**绝对禁止**：

1. 修改 Gamut Calculator 页面的垂直布局结构
2. 将 4 大主区域改为可垂直拖动的 splitter
3. 改变 Input Parameters / CIE Diagrams / Spectrum Preview 的一栏三列结构
4. 删除或重排 Chromaticity Data 表格的列
5. 将 White Point 信息从 Chromaticity Data 表格中移出
6. 删除 Spectrum Preview 三栏中的任意一栏
7. 将三栏 Preview 改为叠加/切换模式
8. 重新添加独立的 White Point Result 面板
9. 改变 Mode Selection 的位置或选项
10. 删除 Paste 按钮或 Thickness 的 Step 控件
11. 修改默认参考色域勾选状态
12. 改变通道颜色常量 `_CHANNEL_COLORS`

以下事项**需产品授权**：

1. 调整最小高度/宽度数值
2. 调整 splitter 默认 sizes
3. 修改垂直 stretch 比例
4. 修改表格样式（字体、颜色、对齐方式）
5. 新增或删除工具栏选项
6. 修改默认测试数据映射

---

## 8. 验收截图

当前定稿截图保存于：

```
acceptance_screenshots/page_1_default_data_auto.png
```

该截图是使用默认测试数据（QD_Red / QD_Green / BLED + CF_Red / CF_Green / CF_Blue）自动选择并计算后的标准效果。任何后续改动都必须与此截图视觉一致，除非产品明确要求变更。

---

## 9. 变更历史

| 日期 | 变更内容 | 负责人 |
|---|---|---|
| 2026-06-20 | 完成新布局：控制面板/CIE/Preview 均为一栏三列；White Point 信息并入 RGBW 数据表；取消垂直拖动 | AI Assistant |
| 2026-06-20 | CIE 图改用 `plot_cie_chromaticity.py` 的自定义 matplotlib 渲染方式 | AI Assistant |
| 2026-06-20 | RGBW 色坐标表格改为 8 列：Channel / x / y / u' / v' / X / Y / CCT | AI Assistant |
| 2026-06-20 | 生成 BLED / QD / CF 默认测试数据，支持 CSV / TXT / Excel 导入 | AI Assistant |
| 2026-06-20 | 增加默认数据自动加载与自动选谱功能 | AI Assistant |
| 2026-06-20 | 修复默认数据自动选谱时信号风暴导致的卡死问题 | AI Assistant |
| 2026-06-20 | 建立本锁定规范文档 | AI Assistant |

---

## 10. 例外申请流程

如果确实需要修改本页面：

1. 由产品负责人书面确认变更范围
2. 同步更新本文档的相关章节
3. 重新生成验收截图
4. 在变更历史中追加记录
5. 未经过上述流程的修改，开发/AI 应直接拒绝

---

## 11. 给 AI 的明确指令

> 如果你正在阅读本文件，说明 Gamut Calculator 页面的 UI 已经定型。
> 请不要以“优化布局”、“改进信息层次”、“让页面更紧凑”等理由修改 `gamut_calculator_page.py` 的布局、分栏、比例或组件顺序。
> 如果用户要求你修改该页面，请先引用本文件并说明页面处于锁定状态，确认用户是否已获得产品授权。
> 未经授权，仅允许修复功能性 bug（如计算错误、崩溃、导入失败、渲染异常）。
