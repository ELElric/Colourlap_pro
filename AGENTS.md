# ColorLab Pro — AI 开发指南

ColorLab Pro 是面向 LED/QD/CF 显示研发的桌面色域分析工具。技术栈：PySide6 + QtWebEngine + ECharts + SQLAlchemy/SQLite + numpy/scipy/colour-science/shapely。

---

## 架构总览

```
MainWindow (PySide6)
  ├── Sidebar Navigation
  ├── QStackedWidget (4 pages)
  │     ├── [0] SpectrumPage        ← ui/web/spectrum_page.html
  │     ├── [1] GamutCalculatorPage ← ui/web/gamut_calculator_page.html
  │     ├── [2] WhitePointPage      ← ui/web/white_point_page.html
  │     └── [3] ThicknessOptimizerPage ← ui/web/thickness_optimizer_page.html
  └── StatusBar (DB/Spectra/Observer/Illuminant)
```

每个页面继承 `WebViewPage`，通过 `QWebEngineView` 渲染 HTML/JS，通过 `QWebChannel` 与 Python Backend 通信。

---

## 六层架构

```
UI (HTML/JS + ECharts)
  ↕ QWebChannel (JSON)
Controller (@Slot 方法，暴露给 JS)
  → Service (业务逻辑)
    → Engine (纯函数，无副作用)
  → Repository (ORM 读写)
    → Database (SQLAlchemy + SQLite)
```

| 层 | 职责 | 关键文件 |
|---|---|---|
| **UI** | HTML/JS 前端，ECharts 图表 | `ui/web/*.html` |
| **Controller** | 桥接 JS 和 Service，JSON 序列化 | `controllers/*.py` |
| **Service** | 业务编排（导入、分析、优化） | `services/*.py` |
| **Engine** | 纯数学/物理计算，无 I/O | `engines/*.py` |
| **Repository** | ORM ↔ DTO 转换，数据库 CRUD | `repositories/*.py` |
| **Database** | 表结构、迁移、会话管理 | `database/*.py` |

---

## QWebChannel 通信机制

### JS 调用 Python

```javascript
new QWebChannel(qt.webChannelTransport, function(channel) {
    channel.objects.backend.method_name(JSON.stringify(args), function(json) {
        var data = JSarson.parse(json);
        // 处理结果
    });
});
```

### Python 端

```python
class PageBackend(QObject):
    @Slot(str, result=str)
    def method_name(self, payload: str) -> str:
        data = json.loads(payload)
        # 处理逻辑
        return json.dumps({"key": "value"})
```

### 关键约束

- Backend 必须注册为 `"backend"`：`self._channel.registerObject("backend", self._backend)`
- 所有数据通过 JSON 字符串传递
- JS 端引用 `qrc:///qtwebchannel/qwebchannel.js`
- HTML 通过 `setUrl(QUrl.fromLocalFile(str(html)))` 加载（非 `setHtml`），保证相对路径资源（JS/CSS/PNG）可访问

---

## 页面生命周期

```
WebViewPage.__init__()
  → _build_ui()           # 创建 QWebEngineView
  → QWebChannel 绑定
  → initialize()          # 注册 Backend + setUrl 加载 HTML
    → _on_load_finished() # 页面加载完成
      → page_script()     # 注入初始 JS（获取数据、渲染）

MainWindow.page_about_to_show(index)
  → connect_auto_refresh() → _on_page_about_to_show()
    → run_javascript()     # 每次切回页面刷新数据
```

---

## 核心 DTO

### Spectrum

```python
@dataclass(frozen=True)
class Spectrum:
    wavelengths: NDArray[np.float64]  # nm, 单调递增
    values: NDArray[np.float64]       # 强度/透射率
    unit: str = "a.u."
    meta: dict[str, Any] = field(default_factory=dict)
```

### XY / Gamut

```python
@dataclass(frozen=True)
class XY:
    x: float  # CIE 1931 x
    y: float  # CIE 1931 y

@dataclass(frozen=True)
class Gamut:
    name: str
    red: tuple[float, float]    # (x, y)
    green: tuple[float, float]
    blue: tuple[float, float]
    white: tuple[float, float]
```

---

## 四个页面功能详解

### 1. Spectrum Library（光谱库）

**功能**：光谱数据的导入、浏览、分析、导出

| 功能 | 说明 |
|---|---|
| 文件导入 | CSV/XLSX/TXT，自动检测分隔符、表头、通道 |
| 剪贴板粘贴 | 从文本粘贴波长/值对 |
| 多选汇总 | 选中多条光谱，显示平均 xy/FWHM/purity |
| 信息卡 | xy、u'v'、Peak、FWHM、Dominant λ、Purity |
| 分类过滤 | LED/QD/CF/White/All |
| 通道标签 | R/G/B/W + RCF/GCF/BCF 彩色标签 |
| 图表 | ECharts 折线图，颜色匹配通道，X轴 380-780nm |

**CF 光谱特殊处理**：只显示 xy 色度坐标，u'v'/Peak/FWHM/Dom/Purity 显示 `-`

### 2. Gamut Calculator（色域计算器）

**功能**：计算 RGB 原色经过 CF 滤光片后的色域覆盖

| 功能 | 说明 |
|---|---|
| 两种模式 | RGB+CF（三原色各配一个 CF）/ White+CF（白光配三 CF） |
| Lambert-Beer 滤波 | `filtered = emission × T^d`，T 为 CF 透射率，d 为膜厚(μm) |
| 光谱预览 | 3 标签页：Original(发射谱) / Filtered(过滤后) / Both(发射谱+CF透射率，双Y轴) |
| 参考色域 | sRGB / NTSC / DCI-P3 / BT2020 复选框切换 |
| 结果表格 | CIE 1931 xy + CIE 1976 u'v' 两个表格 |
| CIE 色度图 | ECharts 渲染，PNG 背景图 + 设备三角形 + 参考色域 |
| 步长输入 | 厚度输入框支持自定义步长（spin 按钮按步长增减） |
| 导出 | HTML 报告导出 |

### 3. White Point（白点计算器）

**功能**：从 RGB 原色计算混合白点，或反向求解

| 功能 | 说明 |
|---|---|
| 正向模式 | RGB xy + 混合比例 → 白点 xy/u'v'/CCT + 色域指标 |
| 反向模式 | RGB xy + 目标白点 xy → 求解混合比例 |
| 参考色域 | sRGB/NTSC/DCI-P3/BT2020 checkbox 切换 |
| CIE 图表 | 1931 xy + 1976 u'v' 两个色度图，PNG 背景 |
| 跨页面联动 | 接收 Gamut Calculator 的 RGB 坐标 |

### 4. Thickness Optimizer（膜厚优化）

**功能**：网格搜索最优 CF 膜厚组合

| 功能 | 说明 |
|---|---|
| 网格搜索 | 10×10×10 = 1000 组合，按 delta_xy + coverage 排序 |
| 敏感度分析 | 3 通道同时扫描，显示 Coverage vs Thickness 趋势 |
| 白点敏感度 | 单通道扫描，显示 White x/y vs Thickness |
| 进度条 | Qt 信号驱动，支持用户取消 |
| 最优结果标记 | 图表上标出 best 点 |

---

## 已解决问题记录

### Lambert-Beer 公式错误

**问题**：最初前端和后端都用了错误的公式：
```
alpha = -log10(T)
attenuation = exp(-alpha × d)  // 错！等价于 T^(0.434×d)
```
导致衰减严重偏弱（如 T=0.5, d=1 时得到 0.74 而非正确的 0.5）。

**修复**：统一改为 `attenuation = pow(T, d)`（前端 `Math.pow`，后端 `np.power`）。

### CF 光谱波长插值

**问题**：前端用精确波长查找（`fMap[wl]`），CF 和发射谱波长网格不对齐时返回 1.0。

**修复**：改为二分查找 + 线性插值，与后端 `np.interp` 行为一致。超出 CF 范围返回 1.0（完全透射）。

### 白点页 Loading 卡死

**问题**：`calculate()` 中如果回调抛 JS 错误，`setLoading(false)` 永远不执行，loading overlay 卡住。

**修复**：
1. 添加 10 秒安全超时自动隐藏
2. 所有回调加 try-catch
3. 全局 `activeCalcId` 计数器防止 stale 回调

### Both 标签 CF 光谱显示错误

**问题**：Both 标签显示 `emission × T^d`（过滤后发射谱），但图例写的是 CF 名称。

**修复**：
- Both 标签：左侧 Y 轴显示原始发射谱（实线），右侧 Y 轴显示 CF 透射率谱 T（虚线，0-1）
- Filtered 标签：显示 `emission × T^d`（标注为 "filtered"）

### Purity 双重 ×100

**问题**：回退路径 `_compute_chromaticity` 返回 `dist_cw/dist_lw*100`（已是百分比），但 `purity_str` 属性又 `*100`。

**修复**：回退路径改为返回 0~1 范围，与主路径一致。

### 光谱预览区 Checkbox 状态丢失

**问题**：`renderSpectrumPreview()` 先用 `innerHTML` 重建整个 table，checkbox 全部恢复 checked。

**修复**：在 `innerHTML` 重建之前读取所有 checkbox 状态到 `visMap`，重建时恢复。

### 膜厚优化页 CF 下拉框过滤

**问题**：CF 光谱 channel 字段是 `RCF`/`GCF`/`BCF`，但过滤条件写的是精确匹配 `R`/`G`/`B`。

**修复**：改为 `chMatch` 函数，兼容 `RCF||R`、`GCF||G`、`BCF||B`。

### 膜厚优化敏感度分析

**问题**：只能一次扫描一个通道，无法对比 R/G/B 趋势。

**修复**：新增 `sensitivity_all` 后端方法，一次扫描 3 个通道，前端用 3 条彩色曲线展示。

---

## 开发命令

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行 GUI
colorlab-pro-gui
python scripts/run_app.py

# Lint
ruff check src/
ruff format src/

# 类型检查
mypy src/colorlab_pro

# 测试
pytest tests/ -v
pytest --cov=colorlab_pro --cov-fail-under=90

# CLI
colorlab-pro init-db    # 初始化数据库
colorlab-pro gui        # 启动 GUI
colorlab-pro version    # 版本信息
```

---

## 关键公式速查

| 公式 | 用途 | 代码位置 |
|---|---|---|
| `T(d) = T_ref^(d)` | Lambert-Beer 膜厚滤波 | `engines/gamut_calculator.py`, `gamut_calculator_page.html` |
| `xy = XYZ / (X+Y+Z)` | CIE 1931 xy 色度 | `engines/spectrum_analyzer.py:xy()` |
| `u' = 4x / (-2x+12y+3)` | CIE 1976 u' | `engines/gamut_calculator.py:xy_to_uv()` |
| `coverage = ∩(device, target) / target` | 色域覆盖度 | `engines/gamut_calculator.py:coverage()` |
| `CCT ≈ -449n³+3525n²-6823n+5520` | Hernandez 1999 CCT | `colour.temperature.xy_to_CCT()` |

---

## 数据库 Schema

| 表 | 字段 |
|---|---|
| **spectra** | id, name, unit, channel, category, wl_min, wl_max, fwhm_nm, peak_nm, xy_x, xy_y, uv_u, uv_v, dominant_wavelength, purity, meta_json |
| **spectrum_points** | spectrum_id(FK), idx, wavelength, value — 复合主键 |
| **projects** | id, name, created_at |

Schema 版本管理：`database/session.py` 中 `SCHEMA_VERSION` 常量，自动迁移 `v1→v2→v3→v4`。

---

## 前端技术要点

- 所有 HTML 使用暗色主题（`#1e1e1e` 背景）
- 图表统一使用 ECharts（`echarts.min.js`），init 时传 `'dark'` 主题
- CIE 色度图使用预渲染 PNG 作为 CSS 背景图
- 厚度输入框支持 step 输入（`type="number" step="0.1" min="0"`）
- 所有 JS 回调加 try-catch，防止静默失败
- 页面刷新通过 `connect_auto_refresh()` 连接 `page_about_to_show` 信号
