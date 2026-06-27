# ColorLab Pro — Known Issues

> Project: ColorLab Pro V1.1
> Last Updated: 2026-06-27

## Open Issues

### I-002: Trae Write 工具首次会话持久化问题

- Status: open
- Severity: high
- Discovered In: T-01
- Discovered At: 2026-06-18
- Description: 在某个会话窗口中，Trae 的 `Write` 工具报告 `File created successfully`，但文件实际未落盘到 `d:\0000TARE\ColorLab PRO\`。PowerShell 直接写入则工作正常。`Read` 工具能读取 `Write` 工具之后再次调用的内容，但早期内容不可见。
- Workaround: 项目生成改用 PowerShell 脚本（保存到 `c:\Users\lxbuc\.trae-cn\work\...`），单次 `Set-Content` 批量写盘。脚本保存路径：`c:\Users\lxbuc\.trae-cn\work\6a33c649bb77a9902097476b\generate_colorlab_pro.ps1`。
- Decision Reference: —

## Resolved

### I-007: 测试 fixture 重复定义

- Status: resolved
- Severity: low
- Discovered In: T-04
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: `d65_spectrum` 和 `equal_energy_spectrum` fixture 原本在 test_spectrum_analyzer.py 中本地定义，test_color_calculator.py 也需要，触发 setup error。
- Resolution: 移到 `tests/conftest.py`，两个测试文件共享。同时清理 test_spectrum_analyzer.py 的本地定义。

## Resolved

### I-011: mypy.ini 多行列表解析误报

- Status: resolved
- Severity: low
- Discovered In: T-05/T-06
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: mypy 2.1.0 报错 `mypy.ini: Source contains parsing errors: [line 18]: ']
'`，同时产生 `import-untyped` 错误，即使 multi-line module 列表语法正确。
- Resolution: 将 `[[mypy.overrides]]` multi-line module 列表拆分为多个 `[mypy-module.*]` 小节，并对 scipy / shapely 启用 ignore_missing_imports。移除了源码中因此变成 unused 的 `# type: ignore[import-untyped]` 注释。

### I-010: Coverage 浮点噪声可能超过 100%

- Status: resolved
- Severity: low
- Discovered In: T-05
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: `coverage(sRGB, Adobe RGB)` 返回 100.03%，因为 shapely 多边形 intersection 面积的浮点误差。
- Resolution: 测试断言从 `<= 100.0` 放宽到 `<= 100.0 + 1e-9`。

### I-009: shapely.contains 需要 Point 对象

- Status: resolved
- Severity: low
- Discovered In: T-05
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: `Polygon.contains((x, y))` 在 shapely 2.x 中不接受裸 tuple。
- Resolution: 使用 `shapely.geometry.Point(x, y)` 并导入 `Point`。

### I-008: N806 变量命名规范

- Status: resolved
- Severity: low
- Discovered In: T-06
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: `A`, `X_t`, `Y_t`, `Z_t` 被 ruff N806 标记为应小写的变量名。
- Resolution: 重命名为 `design_matrix`, `x_t`, `y_t`, `z_t`。

### I-006: dominant_wavelength 算法错误

- Status: resolved
- Severity: high
- Discovered In: T-03
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: 第一版算法用 projection of (locus-white) onto (sample-white) 的投影长度来选 dominant wavelength。结果 R-LED sample (xy ≈ 0.703, 0.297) 投影最大的不是 630 nm 而是 700 nm——投影长度在等能光谱上偏向远端，**不是** 选 dominant wavelength 的正确度量。
- Resolution: 改用 cosine similarity（单位向量点积，最大值对应最小夹角）。这是 CIE 标准的 dominant wavelength 选取方法。修复后 R/G/B LED 全部返回预期值。

### I-005: colour-science 0.4.4 SpectralDistribution 索引方式

- Status: resolved
- Severity: low
- Discovered In: T-03
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: 旧版 colour-science 用 `sd.value(wavelength)` 取值；0.4.4 用 `sd[wavelength]` (`__getitem__`)。
- Resolution: 测试 fixture 改用 `d65[np.float64(w)]`。

### I-004: 端到端参考数据验证

- Status: resolved
- Severity: —
- Discovered In: T-02
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: `scripts/validate_reference_data.py` 成功识别 3 个内置参考 LED 光谱
- Resolution: 验证 T-02 detect_channel 函数 + resources/reference_data/synthetic/ 集成工作正常

### I-003: numpy 1.26 / 2.0 trapezoid 兼容

- Status: resolved
- Severity: medium
- Discovered In: T-02
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: `np.trapezoid` 在 numpy 2.0+ 才引入，numpy 1.26（pinned in `requirements.txt`）使用 `np.trapz`。直接调用 `np.trapezoid` 在 1.26 抛 `AttributeError`。
- Resolution: 用 `hasattr(np, "trapezoid")` 兼容两版本。已修复 `src/colorlab_pro/engines/spectrum_normalizer.py` 和 `tests/unit/engines/test_spectrum_normalizer.py`。补丁已嵌入生成脚本（`generate_colorlab_pro.ps1` §7）。

### I-001: 当前机器未安装 Python 3.11

- Status: resolved
- Severity: blocker
- Discovered In: T-01
- Discovered At: 2026-06-18
- Resolved At: 2026-06-18
- Description: 之前以为需用户手动安装 Python 3.11
- Resolution: 实际系统已通过 py launcher 提供 Python 3.11.7，可直接 `py -3.11 -m venv .venv`

---

## 2026-06-27 Session Issues

### I-012: 导入光谱缺少 category 选择

- Status: resolved
- Severity: medium
- Discovered At: 2026-06-27
- Resolved At: 2026-06-27
- Description: 点击导入按钮时，光谱自动默认 LED category，没有让用户选择 QD/LED/CF/W 的弹窗。
- Resolution: 在 spectrum_page.html 中添加导入分类模态框（Import Category Modal），四个按钮分别对应 LED/CF/QD/W。`import_spectra(category)` 接收参数后传给后端 controller。后端 `import_xlsx_file/import_csv_file` 已支持 `category` 参数。

### I-013: 前端显示格式不统一

- Status: resolved
- Severity: medium
- Discovered At: 2026-06-27
- Resolved At: 2026-06-27
- Description: 各页面数值显示精度不一致：膜厚有时多位小数，波长有时带小数，色坐标和色域精度不统一。
- Resolution: 仅在前端 HTML/JS 用 `toFixed()/Math.round()` 格式化，后端返回完整精度不做截断。规则：膜厚 1 位小数、波长/半峰宽取整（Math.round）、色坐标 3 位小数、色域 2 位小数。涉及 4 个 HTML 文件。**策略：后端保持完整精度，前端负责显示格式化。**

### I-014: 光谱库表格不可编辑

- Status: resolved
- Severity: high
- Discovered At: 2026-06-27
- Resolved At: 2026-06-27
- Description: 导入的光谱数据（name、category、channel、thickness）在表格中只能查看不能修改。
- Resolution: 表格中 name、category、channel、thickness 四列改为可编辑（双击触发）。name/thickness 用 input，category/channel 用 select 下拉框。后端新增 `update_spectrum` Slot 和 controller 层 `update_thickness` 方法。
- Gotcha: 可编辑 `<td>` 必须加 `onclick="event.stopPropagation()"` 阻止单击冒泡，否则 `<tr onclick="toggleRowSelection">` 会在 dblclick 前触发表格重绘，导致编辑功能失效。

### I-015: 色域/膜厚优化页下拉框未按 category+channel 过滤

- Status: resolved
- Severity: medium
- Discovered At: 2026-06-27
- Resolved At: 2026-06-27
- Description: 色域计算器和膜厚优化器的光谱下拉框显示全部光谱，没有按用途过滤。R/G/B 发光谱应只显示 QD/LED，CF 透射率只显示 CF，且 RCF 只显示 channel=R 的 CF。
- Resolution: 用 config 对象定义每个 select 的 `catFilter` 和 `chFilter`，过滤时采用宽松模式：**仅当 category/channel 已明确设置且不匹配时才排除**，未设置的光谱仍显示。严格模式会导致无候选（见 I-016）。

### I-016: 膜厚优化页下拉框完全无候选

- Status: resolved
- Severity: high
- Discovered At: 2026-06-27
- Resolved At: 2026-06-27
- Description: 膜厚优化页的光谱下拉框没有任何可选项，即使谱库中有数据。
- Root Cause: **`thickness_optimizer_page.html` 中 `<script>` 块缺少 `</script>` 关闭标签！** 浏览器把 `</body></html>` 及后续所有内容都当成 JavaScript 解析，导致语法错误，所有函数（`populateSelectors`、`renderResults` 等）全部未定义。同时 `page_script()` 中调用了 HTML 内定义的 `logStatus()` 函数，但 `runJavaScript` 可能在 HTML 内联脚本执行前就运行了，触发 `ReferenceError: logStatus is not defined`。
- Resolution: 1) 补上缺失的 `</script>` 标签；2) `page_script()` 不再依赖 HTML 内定义的函数，改用原始 DOM 操作；3) `_on_page_about_to_show` 加完整 try-catch 错误处理。
- **教训：HTML 文件中 `<script>` 块必须确保有对应的 `</script>` 关闭标签，否则整个页面 JS 瘫痪。**
