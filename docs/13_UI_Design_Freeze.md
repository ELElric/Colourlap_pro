# 13 UI 设计冻结基线

> 本文件记录 ColorLab Pro V1.1 所有页面 UI 的最终设计状态。
> **UI 已冻结**：后续版本不再对布局、交互模式、组件排布做任何改动。
> 仅允许修复功能性 Bug 所必须的极简 UI 修正。

---

## 1. 全局框架

| 区域 | 描述 |
|------|------|
| TopBar | 品牌标识 "ColorLab Pro" + 状态指示灯 "Ready" |
| Sidebar | 4 个导航按钮：Spectrum Library / Gamut Calculator / White Point / Thickness Optimizer，固定宽度 200px |
| 内容区 | QStackedWidget + QWebEngineView 承载页面 HTML |
| StatusBar | 5 个永久指示器：DB / Spectra / Observer / Illuminant / Calc time |
| 主题 | 暗色默认（QSS + ECharts dark theme） |

---

## 2. Spectrum Library 页面

**文件**: `spectrum_page.html`, `spectrum_page.py`

### 功能
- 光谱导入（CSV / XLSX 粘贴文本，批量导入）
- 光谱列表展示（类型、通道、峰值波长、半高宽）
- 光谱预览 ECharts（多光谱重叠显示）
- 自动分类（CF / QD / LED / White）
- 自动对齐 380–780 nm 并补零
- 通道检测（R / G / B / W / IR）
- 光谱删除、全选/取消全选
- 加载时自动全选所有光谱

### UI 布局
- 左栏：光谱列表（多选）
- 右栏：光谱预览图表
- 顶部：导入按钮 + 操作工具栏
- 支持拖拽导入

---

## 3. Gamut Calculator 页面

**文件**: `gamut_calculator_page.html`, `gamut_calculator_page.py`

### 功能
- 三基色选择（R / G / B 各从光谱库选一条）
- Color Filter 选择（可选）
- 膜厚控制（[-] 数值 [+] 步进按钮 + Step 设置）
- Spectrum Preview（Original / Filtered 两个标签页，ECharts 显示）
- CIE 1931 xy 色度图 + CIE 1976 u'v' 色度图并排
- RGB XYZ / 色坐标数据面板
- Coverage / Match 计算（vs sRGB / DCI-P3 / Adobe RGB / NTSC）
- Gamut Result 表格 + White Point Result 分栏
- Paste 按钮：将白点坐标发到 White Point 页面
- QSplitter 可拖动布局，状态自动保存

### UI 布局（三栏布局）
```
| Spectrum Selection (2) | Color Filter (2) | Thickness Controls (3) |
| CIE 1931 xy | Data Panel | CIE 1976 u'v' |
| Gamut Result | White Point Result |
| Spectrum Preview (Original / Filtered tabs) |
```

---

## 4. White Point 页面

**文件**: `white_point_page.html`, `white_point_page.py`

### 功能
- Forward 模式：输入 RGB xy + Ratio → 计算 W xy（只读输出）
- Reverse 模式：输入 RGB xy + W xy → 计算 RGB Ratio（只读输出）
- 支持从 Gamut Calculator 接收 RGB 坐标（Paste 信号）

### UI 布局
- 顶部：模式选择（Forward / Reverse 单选按钮）
- 中间：RGBW 输入表格
  - Forward：R/G/B xy + Ratio 可编辑，W xy 只读
  - Reverse：R/G/B xy + W xy 可编辑，RGB Ratio 只读
- 底部：Calculate 按钮 + 状态日志

---

## 5. Thickness Optimizer 页面

**文件**: `thickness_optimizer_page.html`, `thickness_optimizer_page.py`

### 功能
- Color Filter 光谱选择
- 目标参数配置（目标白点 / 目标色域）
- 膜厚优化计算
- 优化结果展示

### UI 布局
- 左栏：参数配置面板
- 右栏：优化结果面板（图表 + 数据表格）

---

## 6. 设计冻结约定

1. **不再改动的范围**：所有页面组件的位置、大小比例、颜色、字体、间距、交互流程
2. **允许的例外**：修复 Bug 所需的极简 UI 变动（拼写修正、超链接修复、状态反馈逻辑），须在 D-NNN 决策日志中记录
3. **后续版本方向**：仅功能性改进（算法精度、计算性能、数据兼容性、Bug 修复），禁止 UI 重构或布局调整
4. **新功能**：如需新增功能页面，应保持与现有框架一致的视觉风格和布局规范，不修改已有页面
