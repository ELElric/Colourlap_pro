# White Point 页面 UI 设计锁定规范

> **锁定状态：FROZEN**
>
> 本页面已按产品要求完成最终布局设计。
> **任何 AI 或开发者在未经明确授权的情况下，不得修改本页面的布局、比例、组件顺序、分栏方式或核心交互逻辑。**

---

## 1. 页面定位

White Point 是 ColorLab Pro 的白点计算页面，用于：

- Forward Calculation：输入 RGB 坐标 + 比例 → 输出白点 (x, y)
- Reverse Calculation：输入 RGB 坐标 + 目标白点 → 输出 R/G/B 比例
- 色域覆盖率分析（sRGB / NTSC / DCI-P3 / BT2020）
- CIE 1931 xy 和 CIE 1976 u'v' 色度图可视化

## 2. 整体布局

```
Mode Selection (Forward/Reverse + 色域标准复选框)
┌──────────────────────────┬────────────────────┐
│ RGBW Input               │ Gamut Results      │
│ Ch │  x  │  y  │ Ratio  │ Standard │1931│1976│
│ R  │     │     │0.3333  │ sRGB     │ -- │ -- │
│ G  │     │     │0.3333  │ NTSC     │ -- │ -- │
│ B  │     │     │0.3333  │ DCI-P3   │ -- │ -- │
│ W  │     │     │  --    │ BT2020   │ -- │ -- │
├──────────────────────────┴────────────────────┤
│ CIE 1931 xy          │ CIE 1976 u'v'         │
└──────────────────────┴───────────────────────┘
```

## 3. 交互逻辑

- Forward：R/G/B x y Ratio 可编辑，W x y 禁用（灰色背景，显示计算结果）
- Reverse：R/G/B x y 可编辑，W x y 可编辑，Ratio 禁用（灰色背景，显示计算结果）
- 输入变化自动计算，无按钮
- Mode Selection 右侧有 sRGB / NTSC / DCI-P3 / BT2020 复选框，控制色度图中标准三角形的显示/隐藏

## 4. 涉及文件

| 文件 | 修改限制 |
|---|---|
| `src/colorlab_pro/ui/pages/white_point_page.py` | **禁止修改布局与核心逻辑** |

## 5. 锁定规则

1. 不得修改页面垂直布局结构
2. 不得改变组件顺序或分栏方式
3. 不得删除 CIE 图或 Gamut Results 表格
4. 不得恢复 Calculate / Clear 按钮
5. 不得修改 RGBW 表格为非表格形式（如嵌入 QLineEdit/QDoubleSpinBox）
6. 未经授权仅允许修复功能性 bug

## 6. 变更历史

| 日期 | 变更内容 | 负责人 |
|---|---|---|
| 2026-06-22 | 页面 UI 重构：表格布局、Forward/Reverse 交互、自动计算 | AI Assistant |
| 2026-06-22 | 新增 sRGB 标准、色域标准复选框 | AI Assistant |
| 2026-06-22 | 页面 UI 锁定 | AI Assistant |
