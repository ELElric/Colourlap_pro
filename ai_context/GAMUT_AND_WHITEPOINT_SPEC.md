# Gamut Calculator 与 White Point 页面功能及 UI 设计规范

> 本文档面向后续维护该项目的 AI/开发者，说明 ColorLab Pro 中 **Gamut Calculator** 与 **White Point** 两个核心计算页面的功能定位、UI 结构、计算逻辑与代码入口。
> 阅读本文后，应能快速理解这两个页面“做什么”、“怎么布局”、“数据如何流转”。

---

## 1. 页面总览

| 页面 | 入口 | 核心功能 | 主要文件 |
|---|---|---|---|
| **Gamut Calculator** | 左侧导航栏 `Gamut Calculator` | 选择光谱 + 彩膜，计算显示色域、RGBW 色坐标、CCT，绘制 CIE 图 | `src/colorlab_pro/ui/pages/gamut_calculator_page.py` |
| **White Point** | 左侧导航栏 `White Point` | 输入 RGB 坐标与比例，正向/反向计算白点；计算并展示设备色域 | `src/colorlab_pro/ui/pages/white_point_page.py` |

两个页面共用同一套 CIE 色度图组件与色域计算引擎。

---

## 2. Gamut Calculator 页面

### 2.1 功能定位

用户选择一组背光/白光光谱和一组彩膜（Color Filter）光谱，设定膜厚后，计算：

- 经过彩膜过滤后的 RGB 色坐标（x, y, u', v'）
- 合成的 White Point 色坐标与 CCT
- 设备色域与 NTSC / DCI-P3 / BT2020 等标准色域的覆盖率 / 匹配率
- 在 CIE 1931 xy 与 CIE 1976 u'v' 色度图上可视化结果

### 2.2 UI 布局（已锁定）

页面采用**垂直固定比例 + 水平可拖动**布局。从上到下分为 5 个区域：

```
┌─────────────────────────────────────────────────────────────┐
│ Mode Selection                                               │
├─────────────────────────────────────────────────────────────┤
│ Input Parameters（一栏三列）                                  │
│ [ Spectrum | Color Filter | Thickness ]                     │
├─────────────────────────────────────────────────────────────┤
│ CIE Chromaticity Diagrams（一栏三列）                         │
│ [ Chromaticity Data | CIE 1931 xy | CIE 1976 u'v' ]         │
├─────────────────────────────────────────────────────────────┤
│ Spectrum Preview（一栏三列）                                  │
│ [ Filtered | Original | Compare ]                           │
├─────────────────────────────────────────────────────────────┤
│ Gamut Result                                                 │
└─────────────────────────────────────────────────────────────┘
```

- **垂直方向不可拖动**，4 大主区域 stretch 比例为 `10:35:35:20`
- **水平方向**的 Input / CIE / Preview 三栏内部使用 `QSplitter`，用户可拖动
- 详细锁定规则见 `ai_context/GAMUT_UI_LOCK_SPEC.md`，**该页面布局已冻结，未经授权不得修改**

### 2.3 输入参数

| 选择器 | 对应光谱通道 | 说明 |
|---|---|---|
| Spectrum R / G / B | `R` / `G` / `B` | RGB 背光或 QD 发光光谱 |
| Spectrum W | `W` | 白光光谱（White 模式） |
| Color Filter RCF / GCF / BCF | `RCF` / `GCF` / `BCF` | 彩膜透过率光谱 |
| Thickness RCF / GCF / BCF | - | 彩膜厚度，默认 1.0，范围 0.1~5.0 |

模式切换：

- `RGB + Color Filter`：显示 R/G/B 选择器
- `White + Color Filter`：显示 W 选择器，隐藏 R/G/B

### 2.4 计算流程

1. `_recalculate()` 收集所有选择器当前选中的 spectrum_id
2. 从 `SpectrumController` 读取光谱数据
3. 根据 Thickness 对彩膜光谱做缩放（过滤效果）
4. 调用 `ColorController` 计算 RGBW 的 xy / XYZ / CCT
5. 调用 `gamut_calculator` 计算设备色域与标准色域的 coverage / match
6. 更新 Chromaticity Data 表格、Gamut Result 表格、CIE 图、Spectrum Preview

### 2.5 主要输出

- **Chromaticity Data 表格**：R/G/B/White 的 x, y, u', v', X, Y, CCT
- **CIE 1931 xy / CIE 1976 u'v' 图**：RGB 三角、白点、参考色域、可选轨迹
- **Spectrum Preview**：Filtered / Original / Compare 三栏光谱曲线
- **Gamut Result**：NTSC / DCI-P3 / BT2020 的 Coverage 1931/1976 与 Match 1931/1976

### 2.6 默认测试数据

启动时 `src/colorlab_pro/utils/default_data_loader.py` 会自动将 `test_data/` 中的 6 条光谱导入 `Default Demo` 项目：

| 文件 | 通道 |
|---|---|
| BLED.csv | B |
| QD_Red.csv | R |
| QD_Green.csv | G |
| CF_Red.csv | RCF |
| CF_Green.csv | GCF |
| CF_Blue.csv | BCF |

首次切换到 Gamut Calculator 页面时，`_auto_select_default_spectra()` 会按通道自动匹配这些默认光谱并触发计算。

---

## 3. White Point 页面

### 3.1 功能定位

提供两种白点计算模式：

- **Forward Calculation**：输入 RGB 坐标 + RGB 比例，输出混合后的白点（x, y, u', v', CCT）
- **Reverse Calculation**：输入 RGB 坐标 + 目标白点，用优化算法反推 RGB 比例

计算完成后，页面还会构建设备色域，计算与标准色域的覆盖率 / 匹配率，并在 CIE 图上显示。

### 3.2 UI 布局

页面为可滚动垂直布局，从上到下分为 4 个区域：

```
┌─────────────────────────────────────────────────────────────┐
│ Mode Selection                                               │
├─────────────────────────────────────────────────────────────┤
│ Input & Result（一栏三列）                                    │
│ [ RGB Coordinates | RGB Ratios | Result/Target ]            │
├─────────────────────────────────────────────────────────────┤
│ Calculate / Clear buttons                                    │
├─────────────────────────────────────────────────────────────┤
│ Gamut Analysis                                               │
│ [ CIE 1931 xy | CIE 1976 u'v' ] + Gamut Result table        │
└─────────────────────────────────────────────────────────────┘
```

#### Input & Result 一栏三列

| 列 | 内容 |
|---|---|
| 第 1 列：RGB Coordinates | R/G/B 三行，每行输入 x、y |
| 第 2 列：RGB Ratios | R/G/B 三个 0~1 比例输入，**联动且和为 1**，底部显示 `Sum: x.xxxx` |
| 第 3 列：Result | 正向：White Point / x / y / u' / v' / CCT；反向：Target x/y 输入 + R/G/B Ratio / Delta xy |

模式切换时，第 3 列自动在正向结果与反向目标/结果之间切换。

### 3.3 RGB 比例联动逻辑

由 `_RatioPanel` 类管理，规则如下：

- 任一比例变化时，其余两个比例按当前比例缩放，保证 `R + G + B = 1`
- 若其余两个均为 0，则将剩余值平均分配
- 正向计算前会再次归一化，确保数值稳定
- 反向计算输出结果也归一化到 `sum = 1`

### 3.4 计算流程

#### Forward

```
white_xy = mix_xy([r_xy, g_xy, b_xy], weights=[r_ratio, g_ratio, b_ratio])
uprime, vprime = xy_to_uv(white_xy)
cct = xy_to_cct(white_xy)
device_gamut = build_gamut_from_primaries(red=r_xy, green=g_xy, blue=b_xy, white=white_xy)
coverage/match = coverage(target_gamut, device_gamut)
```

#### Reverse

```
minimize ||mix_xy([r_xy, g_xy, b_xy], weights=[wr, wg, wb]) - target_xy||
约束：wr, wg, wb >= 0
输出 weights 归一化到 sum = 1
achieved = mix_xy(..., weights)
device_gamut = build_gamut_from_primaries(red=r_xy, green=g_xy, blue=b_xy, white=achieved)
```

### 3.5 Gamut Analysis 输出

与 Gamut Calculator 一致：

- CIE 1931 xy / CIE 1976 u'v' 图显示 RGB 三角、白点、参考色域
- Gamut Result 表格：NTSC / DCI-P3 / BT2020 的 Coverage 1931/1976 与 Match 1931/1976

---

## 4. 共享组件与引擎

### 4.1 CIE 色度图组件

文件：`src/colorlab_pro/ui/widgets/cie_diagram.py`

| 类/方法 | 作用 |
|---|---|
| `CIECanvas(mode="xy" \| "uv")` | 绘制 CIE 1931 xy 或 1976 u'v' 色度图 |
| `set_original_rgb(r, g, b, white_xy)` | 设置原始 RGB 三角与白点 |
| `set_filtered_rgb(r, g, b, white_xy)` | 设置过滤后 RGB 三角与白点 |
| `set_reference_gamuts([...])` | 设置参考色域（NTSC/DCI-P3/BT2020） |
| `set_show_triangle/show_white_point/show_trajectory/...` | 控制图层显示 |
| `refresh()` | 重绘 |

### 4.2 色域计算引擎

文件：`src/colorlab_pro/engines/gamut_calculator.py`

| 函数 | 作用 |
|---|---|
| `build_gamut_from_primaries(name, red, green, blue, white)` | 由三基色和白点构建设备色域 |
| `standard_gamuts(name)` | 获取标准色域（NTSC / DCI-P3 / BT2020） |
| `coverage(target, device)` / `coverage_1976(...)` | 设备对目标色域的覆盖率 |
| `match(target, device)` / `match_1976(...)` | 设备对目标色域的匹配率 |
| `xy_to_uv(xy)` | xy 转 u'v' |

### 4.3 颜色计算工具

文件：`src/colorlab_pro/engines/color_calculator.py`

| 函数 | 作用 |
|---|---|
| `mix_xy(xy_list, weights)` | 按权重混合多个 xy 坐标，得到混合色坐标 |

---

## 5. 代码入口速查

| 需求 | 入口 |
|---|---|
| 修改 Gamut Calculator 布局 | `src/colorlab_pro/ui/pages/gamut_calculator_page.py`（需参考锁定规范） |
| 修改 White Point 布局 | `src/colorlab_pro/ui/pages/white_point_page.py` |
| 修改 CIE 图渲染 | `src/colorlab_pro/ui/widgets/cie_diagram.py` |
| 修改色域计算逻辑 | `src/colorlab_pro/engines/gamut_calculator.py` |
| 修改默认测试数据 | `src/colorlab_pro/utils/default_data_loader.py` + `test_data/` |
| 新增标准色域 | `src/colorlab_pro/engines/gamut_calculator.py` 的 `_GAMUT_SPECS` |

---

## 6. 修改约束

- **Gamut Calculator 页面**：布局已锁定，详见 `ai_context/GAMUT_UI_LOCK_SPEC.md`。未经授权不得修改分栏、比例、组件顺序。
  - 性能优化后，首次切换到 Gamut Calculator 约 1.3 秒；优化前因 `MainWindow.set_page()` 重复触发事件导致 `_recalculate()` 被调用 3 次，耗时约 3.8 秒。详见 `ai_context/UI_LAYOUT_CHANGE.md` 第 12 节。
- **White Point 页面**：目前处于活跃迭代状态，可调整布局与交互，但建议保持“一栏三列”的 Input & Result 结构，保持与 Gamut Calculator 一致的视觉风格。
- 两个页面共用 `CIECanvas` 与 `gamut_calculator`，修改时需同时验证两个页面的显示是否正常。

---

## 7. 验收截图

| 页面 | 截图路径 |
|---|---|
| Gamut Calculator 默认数据自动计算 | `acceptance_screenshots/page_1_default_data_auto.png` |
| White Point 正向计算 + 色域分析 | `acceptance_screenshots/page_2_whitepoint_compact.png` |

---

## 8. 给 AI 的阅读提示

- 先读 `GAMUT_UI_LOCK_SPEC.md` 了解 Gamut Calculator 为什么不能动
- 再读 `UI_LAYOUT_CHANGE.md` 了解历次布局/功能变更历史
- 读本文档理解两个页面的整体结构与数据流
- 修改代码前，先跑 `tests/unit/ui` 确保现有测试通过
- 任何布局变更都应重新生成验收截图并更新本文档第 7 节
