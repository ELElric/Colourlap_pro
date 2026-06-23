# ColorLab Pro V1.1 — 需求/代码/UI 对齐检查报告

> 检查时间：2026-06-19
> 检查方式：代码走查 + UI offscreen 截图验收 + 全量测试

## 总体结论

9 项核心需求在引擎、服务、Repository、UI 页面层面**已全部对齐**。UI 可正常启动，全量测试通过。

```
pytest -q
314 passed, 0 failed
```

## 逐条对齐检查

| # | 需求 | 代码实现 | UI 体现 | 状态 |
|---|------|---------|---------|------|
| 1 | 光谱分类存储（彩膜/QD/LED/白光） | `Spectrum` ORM 新增 `category` 字段；`detect_category()` 自动识别；Repository 读写 category | Spectrum 表格显示 Category 列 | 已对齐 |
| 2 | 导入自动补齐 380-780 并补零 | `align_to_standard_range()` 默认 380-780，缺失值补 0；导入时强制调用 | 无单独 UI，属于后台行为 | 已对齐 |
| 3 | 白光 + 彩膜模式 | 白光模式下用同一 White 光谱分别经 RCF/GCF/BCF 计算 RGB 三通道 | Gamut Calculator Mode 下拉可切换 "White + Color Filter" | 已对齐 |
| 4 | 多峰光谱仅识别 RG 波段 | `_is_multi_peak()` + `_find_peak_in_band()`；多峰时只比较 R/G 波段 | 导入时自动识别通道 | 已对齐 |
| 5 | 通道检测改为峰强/透过率 | `detect_channel()` 基于 R/G/B 波段最强峰及 FWHM 判定 | 导入时自动分类 | 已对齐 |
| 6 | CIE 1976 Coverage/Match | `xy_to_uv()` / `gamut_to_uv()` / `coverage_1976()` / `match_1976()` | 结果表格含 Coverage 1931/Match 1931/Coverage 1976/Match 1976 四列 | 已对齐 |
| 7 | 信息面板按类型条件显示 | `show_shape = category in ("LED", "QD")` 控制 Peak/FWHM/Dominant/Purity 显示 | Spectrum Info 面板非 LED/QD 时隐藏上述字段 | 已对齐 |
| 8 | Gamut Calculator Paste 按钮 | 公共剪贴板解析工具 `clipboard_parser.py`；`_on_paste()` 导入光谱 | 每个选择器右侧 Paste 按钮可用 | 已对齐 |
| 9 | 白点坐标自动传递 | `white_point_calculated` 信号连接至 `set_rgb_coordinates()`；含空值保护 | White Point 页面自动接收 Gamut 计算的 RGB 坐标 | 已对齐 |

## 检查过程中发现并修复的问题

### 1. GUI 入口 `app.py` 构造参数不匹配（严重）

- **问题**：`WhitePointPage(color_ctrl, page_index=2)` 与 `WhitePointPage.__init__(page_index, parent)` 签名不匹配
- **修复**：改为 `WhitePointPage(page_index=2)`
- **文件**：`src/colorlab_pro/ui/app.py`

### 2. Cross-page 调用未实现的方法（严重）

- **问题**：`app.py` 中连接了 `gamut_page.populate_from_spectrum(info.id)`，但该方法不存在
- **修复**：移除此段无效 cross-page wiring（该联动不在本次需求范围内）
- **文件**：`src/colorlab_pro/ui/app.py`

### 3. `QLabel.setTextAlignment` 方法不存在（严重）

- **问题**：`QLabel` 没有 `setTextAlignment` 方法，导致页面构建失败
- **修复**：改为 `setAlignment`
- **文件**：`src/colorlab_pro/ui/pages/gamut_calculator_page.py`、`src/colorlab_pro/ui/pages/white_point_page.py`

### 4. Purity 算法非标准（中等）

- **问题**：`_compute_purity()` 使用向量投影公式，而非标准 excitation purity
- **修复**：改为标准公式 `purity = |sample - white| / |locus - white|`
- **文件**：`src/colorlab_pro/ui/pages/spectrum_page.py`

## 验收截图

截图保存在 `d:\0000TARE\ColorLab PRO\acceptance_screenshots\`：

- `page_0_.png` — Spectrum 页面
- `page_1_.png` — Gamut Calculator RGB 模式
- `page_1_gamut_white_mode.png` — Gamut Calculator 白光模式
- `page_2_.png` — White Point 页面
- `page_3_.png` — Thickness Optimizer 页面
- `page_4_.png` — Settings 页面

> 注：offscreen 无头环境下中文字体渲染为方块，这是环境字体缺失导致的显示问题，不影响真实桌面环境。

## 待处理遗留项

| 优先级 | 事项 | 说明 |
|--------|------|------|
| P2 | ruff 剩余 10 个历史问题 | 不影响功能 |
| P2 | mypy 部分 UI 文件历史类型问题 | 不影响运行 |
| P2 | 真实桌面环境 UI 验收 | 当前环境为无头 offscreen，中文显示方块；建议在真实桌面环境重新截图验证标签文本 |

## 最终结论

需求、代码、UI 已对齐。GUI 入口修复后可正常启动，核心功能实现完整，全量测试通过。
