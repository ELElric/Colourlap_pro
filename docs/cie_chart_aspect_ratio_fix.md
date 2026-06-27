# CIE 色度图宽高比问题修复记录

## 问题描述

CIE 色度图（马蹄形光谱轨迹）显示比例异常，图形被拉伸变形，不是正确的物理比例。

**期望比例**：
- CIE 1931 xy 色度图：x 范围 0-0.85，y 范围 0-0.95，宽高比应为 0.85/0.95 ≈ 0.89
- CIE 1976 u'v' 色度图：u' 范围 0-0.70，v' 范围 0-0.65，宽高比应为 0.70/0.65 ≈ 1.08

**实际表现**：图形被拉伸，宽高比约为 1.28-1.79（取决于窗口大小）。

---

## 问题原因

### 根本原因

使用了 **CSS `padding-bottom` 技巧** 来设置容器宽高比，但这个方法与 **ECharts 渲染机制** 不兼容。

### 具体分析

**错误的实现方式**（之前版本）：
```html
<!-- 错误：使用 padding-bottom 技巧 -->
<div style="position:relative; width:100%; padding-bottom:112%;">
  <div id="cie-xy-chart" style="position:absolute; top:0; left:0; width:100%; height:100%;"></div>
</div>
```

**问题所在**：
1. `padding-bottom` 技巧创建的容器，其 `height` 在 CSS 计算时为 **0**
2. ECharts 在初始化时需要读取容器的 **像素高度** 来计算渲染区域
3. 当 ECharts 读取到高度为 0 时，会回退使用 **窗口尺寸** 或 **默认尺寸**
4. 这导致图表实际渲染尺寸与容器尺寸不匹配，比例失真

**为什么浏览器开发者工具看不到问题**：
- 在浏览器中直接打开 HTML 文件时，ECharts 会使用默认的窗口尺寸
- 但在 Qt WebEngine 中，由于容器尺寸计算错误，问题会暴露

---

## 解决方案

### 核心思路

**动态计算 + 延迟初始化 + 响应式调整**

### 具体实现

**1. 移除错误的 CSS 技巧**
```html
<!-- 正确：直接设置初始高度，由 JS 动态调整 -->
<div id="cie-xy-chart" style="width:100%; height:400px;"></div>
```

**2. 新增高度计算函数**
```javascript
// 根据容器宽度计算正确高度，保持 CIE 图表比例
function adjustChartHeights() {
    var xyDom = document.getElementById('cie-xy-chart');
    var uvDom = document.getElementById('cie-uv-chart');
    if (!xyDom) return;

    // 获取容器实际宽度
    var containerW = xyDom.parentElement ? xyDom.parentElement.clientWidth : xyDom.clientWidth;
    if (containerW < 100) containerW = 500;

    // 计算 grid 区域宽度（减去 padding）
    var gridPad = { top: 30, right: 20, bottom: 40, left: 45 };
    var gridW = containerW - gridPad.left - gridPad.right;

    // 根据 CIE 标准范围计算高度
    // CIE 1931 xy: x ∈ [0, 0.85], y ∈ [0, 0.95] → ratio 0.85/0.95
    var xyGridH = gridW * (0.95 / 0.85);
    var xyChartH = Math.round(xyGridH + gridPad.top + gridPad.bottom);

    // CIE 1976 u'v': u' ∈ [0, 0.70], v' ∈ [0, 0.65] → ratio 0.70/0.65
    var uvGridH = gridW * (0.65 / 0.70);
    var uvChartH = Math.round(uvGridH + gridPad.top + gridPad.bottom);

    // 设置容器高度
    xyDom.style.height = xyChartH + 'px';
    if (uvDom) uvDom.style.height = uvChartH + 'px';

    // 通知 ECharts 容器尺寸变化
    if (cieXYChart) cieXYChart.resize();
    if (cieUVChart) cieUVChart.resize();
}
```

**3. 延迟初始化确保布局完成**
```javascript
// DOM 加载完成后，等待布局稳定再初始化图表
document.addEventListener('DOMContentLoaded', function() {
    requestAnimationFrame(function() {
        setTimeout(function() {
            adjustChartHeights();  // 先计算高度
            renderCIEBackground(); // 再渲染图表
        }, 100);
    });
});
```

**4. 窗口大小变化时自动调整**
```javascript
window.addEventListener('resize', function() {
    if (cieXYChart || cieUVChart) {
        adjustChartHeights();
        // 重新渲染背景（因为高度变了）
        _cieBgRendered = { xy: false, uv: false };
        renderCIEBackground();
    }
});
```

---

## 关键技术要点

### 1. ECharts 容器尺寸要求

- ECharts 初始化时必须读取容器的 **像素高度**
- CSS 的 `padding-bottom` 技巧会让 `height` 为 0，导致 ECharts 无法正确初始化
- 必须使用 `style.height = 'xxxpx'` 设置明确的像素值

### 2. 计算时机很重要

- **不能在 DOMContentLoaded 立即计算**：此时布局可能还未完成
- **必须使用 requestAnimationFrame + setTimeout**：确保浏览器已完成布局计算
- **首次计算后要 resize()**：通知 ECharts 容器尺寸已变化

### 3. 响应式设计

- 窗口大小变化时必须重新计算高度
- 重新计算后要调用 `chart.resize()` 更新 ECharts
- 如果图表有背景渲染，需要重新渲染（清除缓存标志）

### 4. CIE 色度图标准比例

| 图表类型 | x/u' 范围 | y/v' 范围 | 正确宽高比 |
|---------|-----------|-----------|-----------|
| CIE 1931 xy | 0 - 0.85 | 0 - 0.95 | 0.89 |
| CIE 1976 u'v' | 0 - 0.70 | 0 - 0.65 | 1.08 |

---

## 验证方法

### 1. 浏览器控制台验证

在开发者工具 Console 中执行：
```javascript
var el = document.getElementById('cie-xy-chart');
console.log('Container size:', el.offsetWidth, 'x', el.offsetHeight);
console.log('Aspect ratio:', el.offsetWidth / el.offsetHeight);
```

期望输出：
```
Container size: 379 x 421
Aspect ratio: 0.90
```

### 2. 像素分析验证

```python
from PIL import Image
import numpy as np

img = Image.open('screenshot.png')
arr = np.array(img)

# 找到马蹄形轮廓的边界
# 计算宽高比是否接近 0.89
```

---

## 常见陷阱

### ❌ 错误做法

```html
<!-- 错误 1：使用 padding-bottom 技巧 -->
<div style="padding-bottom: 112%;">
  <div id="chart" style="position: absolute; width: 100%; height: 100%;"></div>
</div>

<!-- 错误 2：直接在 DOMContentLoaded 初始化 -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    echarts.init(document.getElementById('chart'));
});
</script>

<!-- 错误 3：使用 CSS aspect-ratio -->
<div style="aspect-ratio: 0.89;"></div>
```

### ✅ 正确做法

```html
<!-- 正确：设置初始高度，由 JS 动态调整 -->
<div id="chart" style="width: 100%; height: 400px;"></div>

<script>
// 正确：延迟初始化，确保布局完成
document.addEventListener('DOMContentLoaded', function() {
    requestAnimationFrame(function() {
        setTimeout(function() {
            adjustChartHeights();
            echarts.init(document.getElementById('chart'));
        }, 100);
    });
});

// 正确：响应式调整
window.addEventListener('resize', function() {
    adjustChartHeights();
    chart.resize();
});
</script>
```

---

## 相关文件

- `src/colorlab_pro/ui/web/gamut_calculator_page.html` - 色域计算页面
- `src/colorlab_pro/ui/web/white_point_page.html` - 白点分析页面

---

## 修复版本

- **修复日期**: 2026-06-27
- **修复人**: AI Assistant
- **验证状态**: ✅ 已验证通过

---

## 扩展阅读

- [ECharts 容器尺寸问题](https://echarts.apache.org/handbook/en/concepts/chart-size)
- [CSS Padding-Bottom 技巧](https://css-tricks.com/aspect-ratio-boxes/)
- [CIE 1931 色度图标准](https://en.wikipedia.org/wiki/CIE_1931_color_space)
- [CIE 1976 UCS 色度图标准](https://en.wikipedia.org/wiki/CIE_1976_UCS)
