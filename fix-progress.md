# ColorLab Pro 代码审查修复进度

## 审查日期：2026-06-21

## 问题总览

| 优先级 | 数量 | 状态 |
|--------|------|------|
| P0 崩溃 | 6 | 已修复 |
| P1 逻辑错误 | 15 | 已修复 |
| P2 中等 | 20+ | 部分修复 |
| P3 轻微 | 20+ | 部分修复 |

---

## 修复记录

### 批次1：膜厚优化页面 P0 崩溃修复

**状态：** 修复中

**问题列表：**

1. **[P0] d_ref 缺少 None 保护**
   - 文件：`thickness_optimizer_page.py` 第1084行
   - 问题：`_run_coverage_scan` 中 `d_ref = fs.meta.get("thickness_um", 1.0) if fs.meta else 1.0`，当 `thickness_um` 显式为 `None` 时，`.get()` 返回 `None` 而非默认值 `1.0`，导致 `TypeError` 崩溃
   - 修复：添加 `or 1.0` 保护（与 `_apply_filter` 第1225行和 `_run_thickness_optimization` 第891行保持一致）

2. **[P0] 取消操作导致 x/y 长度不匹配**
   - 文件：`thickness_optimizer_page.py` 第1364-1398行
   - 问题：当用户取消扫描时，`scan_values[idx]` 有完整长度（`_SCAN_STEPS` 或 21），但 `scan_coverage[idx]` 等数据数组长度较短（因为循环提前 break），`plot_line` 收到长度不匹配的 x/y 导致 matplotlib 崩溃
   - 修复：在 `_update_scan_curves` 中将 `channel_values[idx]` 截断为与数据数组相同的长度

**测试：** 534 passed, ruff check passed
**提交：** `0e8e74b`

---

### 批次2：色域计算页面 P0 崩溃修复

**状态：** 已完成

**问题列表：**

1. **[P0] 白光模式覆盖 `_original_spectra`**
   - 文件：`gamut_calculator_page.py` 第1082-1087行
   - 问题：白光模式下 `self._original_spectra[ch] = self._white_spectrum` 直接覆盖原始RGB光谱，切回RGB模式时数据丢失
   - 修复：使用局部变量 `active_spectra` 替代直接覆盖

2. **[P0] CF光谱永远无法自动选中**
   - 文件：`gamut_calculator_page.py` 第879-886行
   - 问题：`channel_map` 将 RCF 映射到 "RCF"（CF光谱的channel是"R"不是"RCF"），且未按category过滤
   - 修复：改为 RCF→R/GCF→G/BCF→B，并添加 category="CF" 过滤

3. **[P0] 每次页面显示重置下拉框**
   - 文件：`gamut_calculator_page.py` 第825-865行
   - 问题：`refresh_spectrum_list` 中 `populate()` 清空所有选择，且代码完全重复
   - 修复：添加保存/恢复选择逻辑，去除重复代码块

4. **[P0] 粘贴光谱功能失效**
   - 文件：`gamut_calculator_page.py` 第1033-1067行
   - 问题：粘贴的光谱无channel/category，无法出现在过滤后的选择器中
   - 修复：根据目标选择器设置正确的 channel/category

5. **[P0] `current_id()` 对 id=0 返回 -1**
   - 文件：`gamut_calculator_page.py` 第124行
   - 问题：`0 or -1` 因 0 为 falsy 返回 -1
   - 修复：改为显式 None 检查

**测试：** 534 passed, ruff check passed
**提交：** `972e003`

---

### 批次3：光谱页面 P1 修复

**状态：** 已完成

**问题列表：**

1. **[P1] 搜索用错列号**
   - 文件：`spectrum_page.py` 第679行
   - 问题：`source_item = self._table.item(row, 5)` 取第5列（FWHM），Source在第7列
   - 修复：改为 `self._table.item(row, 7)`

2. **[P1] 多选删除时行索引失效**
   - 文件：`spectrum_page.py` 第556-560行
   - 问题：逐个删除时 `delete_spectrum` 触发表格重建，后续 `row.row()` 指向错误行
   - 修复：先收集所有 sid 再统一删除

3. **[P1] 批量设category时行索引失效**
   - 文件：`spectrum_page.py` 第412-416行
   - 问题：同上根因，`update_category` 触发 refresh 导致行索引失效
   - 修复：先收集 sid 再统一更新，移除冗余 refresh 调用

4. **[P1] `_normalize_spectrum` 空数组崩溃**
   - 文件：`spectrum_page.py` 第793-798行
   - 问题：`np.max(values)` 对空数组抛 ValueError
   - 修复：添加 `size==0` 前置检查，`_update_info_panel` 中 argmax 同样添加保护

**测试：** 534 passed, ruff check passed
**提交：** `0f39758`

---

### 批次4：CIE图 + 白点页面 P1 修复

**状态：** 已完成

**问题列表：**

1. **[P1] CIE图UV模式悬停崩溃**
   - 文件：`cie_diagram.py` 第816行
   - 问题：`self._xy_to_uv(px, py)` 中 `_xy_to_uv` 是模块级函数不是 `CIECanvas` 方法，UV模式悬停时 `AttributeError`
   - 修复：内联 xy→u'v' 转换公式

2. **[P2] 白点页面CCT/u'v'计算未捕获异常**
   - 文件：`white_point_page.py` 第642-645行
   - 问题：极端色度坐标时 `colour.temperature.xy_to_CCT` 抛 ValueError
   - 修复：添加 try/except 保护

3. **[P2] 白点反向计算未验证 x+y<=1**
   - 文件：`white_point_page.py` 第690行
   - 问题：x+y>1 时 Z 分量为负，NNLS 求解无意义
   - 修复：添加 x+y>1.0 前置检查

**测试：** 534 passed, ruff check passed
**提交：** `1153df5`

---

### 批次5：膜厚优化页面 P1 修复

**状态：** 已完成

**问题列表：**

1. **[P1] L-BFGS-B最优结果 `entry` 被丢弃**
   - 文件：`thickness_optimizer_page.py` 第934-948行
   - 问题：`entry` 字典（含最优膜厚、coverage、match等）计算后从未加入 `results` 列表，用户只看到扫描点数据而非最优解
   - 修复：将 `entry` 作为 `results` 首元素插入

2. **[设计权衡] 覆盖率优化仅1D**
   - 文件：`thickness_optimizer_page.py` `_run_coverage_scan`
   - 说明：逐通道独立扫描是设计权衡（O(N) vs O(N³)），非bug，保持不变

3. **[非bug] 白点/坐标目标coverage/match为0**
   - 说明：非gamut目标无参考色域，coverage/match为0是正确行为

4. **[暂不处理] L-BFGS-B优化阶段无法取消**
   - 说明：scipy.optimize.minimize不支持取消回调，需大幅重构

**测试：** 534 passed, ruff check passed
**提交：** `ce1ee54`

---

### 批次6：色域计算页面 P1 修复

**状态：** 已完成

**问题列表：**

1. **[P1] 无滤镜时画布不刷新**
   - 文件：`gamut_calculator_page.py` `_update_cie_diagram`
   - 问题：`set_original_rgb` 后未调用 `refresh()`，无滤镜时原始RGB点不可见
   - 修复：始终在 `_update_cie_diagram` 末尾调用 `refresh()`

2. **[P1] `_clear_results` 清空参考色域**
   - 文件：`gamut_calculator_page.py` `_clear_results`
   - 问题：`canvas.clear_all()` 清除参考色域后未恢复，勾选的参考色域三角形消失
   - 修复：clear 后重新应用参考色域

3. **[P1] 白光模式LED R/G/B复选框无效**
   - 文件：`gamut_calculator_page.py` `_update_visibility`
   - 问题：白光模式下无RGB选择，LED复选框仍可见
   - 修复：在 `_update_visibility` 中设置 LED 复选框 `setVisible(is_rgb)`

4. **[P1] 白点条件检查不足，可能 KeyError**
   - 文件：`gamut_calculator_page.py` 第1178行
   - 问题：`all(v is not None for v in filtered_xys.values())` 只检查已存在的值，缺少key时后续直接访问可能 KeyError
   - 修复：改为 `all(filtered_xys.get(ch) is not None for ch in ("R", "G", "B"))`

5. **[P1] `refresh_spectrum_list` 代码重复**
   - 已在批次2中修复

**测试：** 534 passed, ruff check passed
**提交：** `76049d8`

---

### 批次7：P2 中等问题修复

**状态：** 已完成

**问题列表：**

1. **[P2] 轨迹点无限累积**
   - 文件：`cie_diagram.py` `add_trajectory_point`
   - 问题：每次 `_recalculate` 都调用 `add_trajectory_point` 但从不清理，长时间使用后内存持续增长
   - 修复：添加200点上限，超出时删除最旧的点

2. **[P2] `_refresh_table` 未阻塞信号**
   - 文件：`spectrum_page.py` `_refresh_table`
   - 问题：刷新过程中 `setItem` 触发 `cellChanged` 和 `itemSelectionChanged` 级联信号，导致大量伪计算
   - 修复：添加 `blockSignals(True)`，清理重复的 `setUpdatesEnabled(True)` 调用

3. **[P2] filter选择变化双重触发 `_recalculate`**
   - 文件：`gamut_calculator_page.py` `_on_filter_selection_changed`
   - 问题：`set_value` 触发 `valueChanged` → `_on_thickness_changed` → `_recalculate`，随后又调用 `_recalculate`
   - 修复：阻塞 spinbox 信号避免双重触发

**测试：** 534 passed, ruff check passed
**提交：** `e8a7df6`

---

### 批次8：P3 轻微问题修复

**状态：** 已完成

**问题列表：**

1. **[P3] `_compute_purity` 重复导入 numpy**
   - 文件：`spectrum_page.py` 第948行
   - 问题：函数内 `import numpy as _np` 但顶部已有 `import numpy as np`
   - 修复：移除函数内导入，统一使用 `np`

2. **[P3] `_xy_to_cct` docstring 不一致**
   - 文件：`white_point_page.py` 第766行
   - 问题：docstring 写 "Ohno 2013"，实际用 "Hernandez 1999"
   - 修复：修正 docstring

3. **[P3] `_calculate_reverse` 冗余计算**
   - 文件：`white_point_page.py` 第716行
   - 问题：`total` 恒等于1.0，除以1.0无意义
   - 修复：简化为直接赋值

4. **[P3] `_pp_btn` 和 `_channel_btn` 初始未禁用**
   - 文件：`spectrum_page.py` 第236/248行
   - 问题：按钮初始状态未禁用，UX不佳
   - 修复：添加 `setEnabled(False)` 初始状态

**测试：** 534 passed, ruff check passed
**提交：** `b996bba`

---

## 修复总结

| 批次 | 优先级 | 修复数 | 提交 |
|------|--------|--------|------|
| 1 | P0 | 2 | `0e8e74b` |
| 2 | P0 | 5 | `972e003` |
| 3 | P1 | 4 | `0f39758` |
| 4 | P1 | 3 | `1153df5` |
| 5 | P1 | 1 (+3说明) | `ce1ee54` |
| 6 | P1 | 4 (+1已修复) | `76049d8` |
| 7 | P2 | 3 | `e8a7df6` |
| 8 | P3 | 4 | `b996bba` |
| 9 | P2 | 3 | `82bd8d6` |
| 10 | P2 | 2 (+1暂缓) | `18648ab` |
| 11 | P2/P3 | 5 | `bf4fd9e` |
| 12 | P2 | 3 | `852f101` |
| 13 | P3/P1/P3/P2 | 4 | `45c671a` `07635ba` `7b045e7` `cefd5a7` |
| 14 | P0 | 3 | `66dd7cc` |
| 15 | P1 | 8 | `061536f` `22d0cf1` |
| 16 | P2 | 3 | `5040935` |
| **合计** | | **57项修复** | **22次提交** |

所有534个测试通过，ruff代码检查通过。

---

### 批次13：剩余未修复项全部修复

**状态：** 已完成

**问题列表：**

1. **[P3] `_on_paste` 访问私有属性 `_spinbox`**
   - 文件：`gamut_calculator_page.py`
   - 修复：`_ThicknessControl` 添加 `block_signals()` 公共方法，替换 `ctrl._spinbox.blockSignals()` 调用
   - 提交：`45c671a`

2. **[P1] L-BFGS-B 优化阶段无法取消**
   - 文件：`thickness_optimizer.py` + `thickness_optimizer_page.py`
   - 修复：引擎 `optimize_thickness_display` 添加 `cancel_callback` 参数，每次迭代后调用。页面传入 `_cancel_cb` 检查 `self._cancelled`，若为 True 则抛出 `OptimizationCancelledError` 终止 minimize
   - 提交：`07635ba`

3. **[P3] 白点页面比例联动策略不对称**
   - 文件：`white_point_page.py`
   - 修复：`_on_ratio_changed` 改为等比缩放——另外两个通道保持原有相对比例，总和缩放为 `1 - new_value`。同时修复 `_calculate_forward` 异常分支引用不存在的 `self._status_label` 的 AttributeError
   - 提交：`7b045e7`

4. **[P2] `analyze` 同步调用卡死UI**
   - 文件：`spectrum_viewmodel.py` + `analyze_viewmodel.py` + `spectrum_service.py` + `spectrum_page.py`
   - 修复：`SpectrumViewModel.analyze()` 和 `AnalyzeViewModel.analyze()` 改用 `run_in_background` 异步执行，结果通过信号回传。purity 计算移入 Service 层，消除 UI 线程 401 次循环
   - 提交：`cefd5a7`

---

### 批次14：代码审查 P0 严重 Bug 修复

**状态：** 已完成

**问题列表：**

1. **[P0] `analyze_page` Analyze 按钮完全失效**
   - 文件：`analyze_page.py` + `analyze_viewmodel.py`
   - 问题：`hasattr(self._view_model.target, "id")` 永远返回 False（Spectrum DTO 无 id 属性），导致 Analyze 按钮和 Observer/Illuminant 切换完全失效
   - 修复：添加 `ViewModel.target_id` 属性，使用 `_target_summary.id` 获取光谱 ID

2. **[P0] `_populate_delta_reference_combo` 未排除当前 target**
   - 文件：`analyze_page.py`
   - 问题：同根因——`getattr(target, "id", None)` 返回 None，参考列表包含当前光谱
   - 修复：改用 `target_id` 属性

3. **[P0] `white_point _update_gamut_analysis` 缺 `set_reference_gamuts`**
   - 文件：`white_point_page.py`
   - 问题：`clear_all()` 清空参考色域后未恢复，每次正向/反向计算后 CIE 图上的参考色域三角形消失
   - 修复：添加 `set_reference_gamuts(["NTSC", "DCI-P3", "BT2020"])` 恢复调用

**测试：** 534 passed, ruff check passed
**提交：** `66dd7cc`

---

### 批次15：代码审查 P1 中等 Bug 修复

**状态：** 已完成

**问题列表：**

1. **[P1] `_refresh_table` blockSignals(False) 在恢复选中之前**
   - 文件：`spectrum_page.py`
   - 问题：`selectRow` 触发 `itemSelectionChanged` → `analyze` + `_update_charts`，每次刷新都触发不必要重分析
   - 修复：将 `blockSignals(False)` 移到恢复选中之后

2. **[P1] 异步分析竞态——旧结果覆盖新选中**
   - 文件：`spectrum_viewmodel.py` + `spectrum_controller.py`
   - 问题：快速切换选中时旧分析结果可能覆盖新选中的数据
   - 修复：添加 `_analysis_request_id` 跟踪最新请求，回调中校验 `result["spectrum_id"]` 是否匹配，不匹配则丢弃。Controller 结果中添加 `spectrum_id` 字段

3. **[P1] `_update_info_panel` 数据不一致**
   - 文件：`spectrum_page.py`
   - 问题：result 色度数据和 `selected_spectrum` 的 Peak/FWHM 可能来自不同光谱
   - 修复：添加 `spectrum_id` 校验，不匹配则跳过更新

4. **[P1] 取消消息被 "completed with no results" 覆盖**
   - 文件：`thickness_optimizer_page.py`
   - 修复：取消后设置 `_cancelled=True`，`_on_optimization_complete` 检查标志显示正确消息

5. **[P1] `d_ref` 用 `or 1.0` 不捕获负数**
   - 文件：`thickness_optimizer_page.py`
   - 修复：改为显式 `None` 和 `<= 0` 检查

6. **[P1] ratio 计算条件与 white_xy 不一致（负权重场景）**
   - 文件：`thickness_optimizer_page.py`
   - 修复：统一条件为 `total_w > 0 and all(w >= 0 for w in weights)`

7. **[P1] `_compute_white_xy` 主路径缺少 NaN 检查**
   - 文件：`thickness_optimizer_page.py`
   - 修复：NaN 检查提到所有路径之前

8. **[P1] `_run_coverage_scan` 中 ratio 同样修复条件不一致**
   - 文件：`thickness_optimizer_page.py`

**测试：** 534 passed, ruff check passed
**提交：** `061536f` `22d0cf1`

---

### 批次16：代码审查 P2 轻微问题修复

**状态：** 已完成

**问题列表：**

1. **[P2] `_compute_purity` 死代码（52行）**
   - 文件：`spectrum_page.py`
   - 问题：purity 已移至 Service 层计算，UI 层的 `_compute_purity` 不再被调用
   - 修复：删除死代码

2. **[P2] `_on_header_clicked` 排序方向/列丢失**
   - 文件：`spectrum_page.py`
   - 问题：点击 col 0 时用 Qt 当前方向（已被切换），且硬编码回退到 col 1
   - 修复：保存上次非零排序列和方向，点击 col 0 时恢复到之前的排序状态

3. **[P2] `_on_paste` 双重 `_recalculate`**
   - 文件：`gamut_calculator_page.py`
   - 问题：`set_current_id` 已通过信号链触发 `_recalculate`，显式调用 `target_callback` 导致重复计算
   - 修复：移除冗余 callback 调用和未使用的 `target_callback` 变量

**测试：** 534 passed, ruff check passed
**提交：** `5040935`

---

### 未修复项

所有此前列出的未修复项均已修复。当前无已知未修复项。
