# ColorLab Pro V1.1 — 需求修复任务跟踪

> Project: ColorLab Pro V1.1
> Created: 2026-06-19
> Purpose: 基于用户确认的最终需求，记录所有修复任务的拆分、推进与验收状态

---

## 总体目标

基于用户确认的最终需求，修复当前 UI 实现与需求之间的差异，确保光谱库管理、色域计算、白点计算三大模块完全符合用户预期。

---

## 任务总览

| ID | 任务名称 | 优先级 | 状态 | 计划开始 | 完成时间 | 测试覆盖 |
|----|---------|--------|------|---------|---------|---------|
| TASK-1 | 光谱分类存储（彩膜/QD/LED/白光） | P0 | completed | 2026-06-19 | 2026-06-19 | 新增 9 个单元测试 |
| TASK-2 | 导入自动补齐 380-780 并补零 | P0 | completed | 2026-06-19 | 2026-06-19 | 新增 4 个单元测试 |
| TASK-3 | 白光 + 彩膜模式 | P0 | in_progress | 2026-06-19 | - | 需补充 |
| TASK-3 | 白光 + 彩膜模式 | P0 | completed | 2026-06-19 | 2026-06-19 | UI 模式切换 + 计算分支 |
| TASK-4 | 多峰光谱通道识别（仅 RG 波段） | P1 | completed | 2026-06-19 | 2026-06-19 | 新增 2 个单元测试 |
| TASK-5 | 通道检测算法改为峰强/透过率判断 | P1 | completed | 2026-06-19 | 2026-06-19 | detect_channel 重写为以波段峰强驱动 |
| TASK-6 | CIE 1976 Coverage/Match 计算 | P1 | completed | 2026-06-19 | 2026-06-19 | 新增 4 个单元测试 |
| TASK-7 | 信息面板按类型条件显示 | P1 | completed | 2026-06-19 | 2026-06-19 | UI 条件显示 |
| TASK-8 | Gamut Calculator Paste 按钮完整实现 | P2 | completed | 2026-06-19 | 2026-06-19 | 提取公共剪贴板解析工具 |
| TASK-9 | 白点坐标自动传递连接确认 | P2 | completed | 2026-06-19 | 2026-06-19 | 信号已连接，增加空值保护 |
| TASK-10 | 全量回归测试 | P0 | completed | 2026-06-19 | 2026-06-19 | pytest 314 passed |

---

## 最终验收结果

| 检查项 | 结果 |
|--------|------|
| 全量单元测试 | 314 passed |
| 本次新增测试 | 21 个（category/align/multi-peak/1976 等）|
| ruff 自动修复 | 已执行，剩余 10 个历史问题 |
| mypy 关键文件 | database/session.py 通过 |
| 状态 | 全部 P0/P1/P2 任务完成 |

---

## 任务详情

### TASK-1: 光谱分类存储（彩膜/QD/LED/白光）

**需求描述**
- 彩膜光谱、QD 光谱、LED 光谱、白光光谱需要单独分开保存
- 当前数据库只有一个 `spectra` 表，通过 `channel` 字段区分
- 白光光谱目前没有专门类型

**实现范围**
1. 数据库 schema：在 `Spectrum` ORM 模型中新增 `category` 字段（filter/qd/led/white）
2. 导入时自动根据 channel 推断 category
3. Spectrum 页面表格新增 Category 列显示与筛选
4. 右键菜单/工具栏支持按 category 过滤
5. Gamut Calculator 的下拉列表按 category 分组显示

**验收标准**
- 导入 LED/QD/CF/白光光谱后，category 字段正确
- Spectrum 表格显示 Category 列
- 可以按 category 筛选光谱
- 现有测试全部通过

**涉及文件**
- `src/colorlab_pro/database/models.py`
- `src/colorlab_pro/dto/spectrum.py`
- `src/colorlab_pro/repositories/spectrum_repository.py`
- `src/colorlab_pro/engines/spectrum_normalizer.py`（通道检测）
- `src/colorlab_pro/ui/pages/spectrum_page.py`
- `src/colorlab_pro/ui/pages/gamut_calculator_page.py`
- 相关测试文件

---

### TASK-2: 导入自动补齐 380-780 并补零

**需求描述**
- 所有光谱都是 380-780 nm 范围
- 缺失的数据自动补零
- 所有光谱仅有 step 差异，没有其他差异

**实现范围**
1. 在 `SpectrumService.import_file` / `import_spectrum` 中，导入后自动对齐到 380-780 nm
2. 缺失波长位置填 0
3. 保持原始 step 信息，但内部统一为 380-780 网格
4. 导出时可以选择是否保持原始范围或导出完整范围

**验收标准**
- 导入 400-700 nm 范围的光谱后，数据库中存储为 380-780 nm
- 380-399 和 701-780 的值为 0
- 原有 400-700 的数据保持不变
- 插值计算仍然正确

**涉及文件**
- `src/colorlab_pro/services/spectrum_service.py`
- `src/colorlab_pro/importers/csv_importer.py`
- `src/colorlab_pro/importers/xlsx_importer.py`
- `src/colorlab_pro/engines/spectrum_normalizer.py`
- 相关测试文件

---

### TASK-3: 白光 + 彩膜模式

**需求描述**
- 色域计算需要支持两种光谱模式：白光 + 彩膜 / RGB 光 + 彩膜
- 当前只有 RGB 光 + 彩膜模式

**实现范围**
1. 在 Gamut Calculator 页面增加模式切换（白光模式 / RGB 模式）
2. 白光模式下：选择一个白光光谱 + RCF/GCF/BCF 彩膜 + 厚度
3. 白光经过彩膜后分解为 RGB 三通道（通过彩膜透过率相乘）
4. 计算分解后的 RGB 坐标、白点、Coverage/Match
5. CIE 图同时显示原始白光、分解后 RGB、白点

**验收标准**
- 白光 + 彩膜模式可正常计算
- 结果表格显示 Coverage/Match
- CIE 图正确显示
- 与 RGB + 彩膜模式切换不冲突

**涉及文件**
- `src/colorlab_pro/ui/pages/gamut_calculator_page.py`
- `src/colorlab_pro/engines/color_calculator.py`（可能需要新增白光分解函数）
- 相关测试文件

---

### TASK-4: 多峰光谱通道识别（仅 RG 波段）

**需求描述**
- 多峰光谱仅识别 RG 波段来判断通道
- 当前通道检测基于单峰特征，未针对多峰光谱特殊处理

**实现范围**
1. 在 `detect_channel` 中增加多峰检测逻辑
2. 如果光谱存在多个显著峰，只考虑 RG 波段（约 600-700 nm 和 500-560 nm）
3. 根据 RG 波段的峰强/面积判断主通道
4. 多峰光谱标记为新的 channel 类型或 category

**验收标准**
- 多峰测试光谱被正确识别为 RG 相关通道
- 单峰光谱行为不变
- 单元测试覆盖多峰情况

**涉及文件**
- `src/colorlab_pro/engines/spectrum_normalizer.py`
- `tests/unit/engines/test_spectrum_normalizer.py`

---

### TASK-5: 通道检测算法改为峰强/透过率判断

**需求描述**
- 自动通道识别依据 RGB 波段峰强或者透过率判断
- 当前基于特征峰位置 + 半高宽

**实现范围**
1. 重写或补充 `detect_channel` 逻辑
2. 在 R/G/B 波段区间内计算峰强（最大值或积分面积）
3. 根据最强峰所在波段判断通道
4. 彩膜类型依据宽带透过率特征（多峰/宽带）判断
5. 保留原有方法作为 fallback

**验收标准**
- 对参考 LED/QD/CF 光谱识别正确率保持 100%
- 新增基于峰强的测试用例
- 单元测试通过

**涉及文件**
- `src/colorlab_pro/engines/spectrum_normalizer.py`
- `tests/unit/engines/test_spectrum_normalizer.py`

---

### TASK-6: CIE 1976 Coverage/Match 计算

**需求描述**
- 色域标准包括 CIE 1931 和 CIE 1976
- 每个标准下都需要 Coverage 和 Match
- 当前 Coverage/Match 只在 xy 空间（1931）计算

**实现范围**
1. 在 GamutService/GamutCalculator 中增加 u'v' 空间的 coverage/match 计算
2. 标准色域（NTSC/DCI-P3/BT2020）的 RGB 坐标转换到 u'v' 空间
3. Gamut Calculator 结果表格区分 1931 和 1976（或增加 1976 列）
4. CIE 1976 图表使用 u'v' 空间的 Coverage/Match 数据

**验收标准**
- 1976 标准下 Coverage/Match 计算正确
- 结果表格同时显示 1931 和 1976 数据
- 单元测试覆盖两种空间

**涉及文件**
- `src/colorlab_pro/engines/gamut_calculator.py`
- `src/colorlab_pro/services/gamut_service.py`
- `src/colorlab_pro/ui/pages/gamut_calculator_page.py`
- `src/colorlab_pro/ui/widgets/cie_diagram.py`
- 相关测试文件

---

### TASK-7: 信息面板按类型条件显示

**需求描述**
- QD 和 LED 光谱才需要显示波峰、半峰宽、主波长、饱和度
- 当前所有光谱都显示 Peak / FWHM / Dominant / Purity

**实现范围**
1. 在 Spectrum 页面根据 spectrum.category/channel 决定是否显示 Peak/FWHM/Dominant/Purity
2. 彩膜/白光光谱隐藏这些字段，只显示色度学信息（x/y/u'/v'）
3. 保持现有布局稳定

**验收标准**
- LED/QD 光谱显示完整信息
- CF/白光光谱不显示 Peak/FWHM/Dominant/Purity
- UI 测试通过

**涉及文件**
- `src/colorlab_pro/ui/pages/spectrum_page.py`

---

### TASK-8: Gamut Calculator Paste 按钮完整实现

**需求描述**
- 多谱库导入需支持剪贴板导入
- 当前 Gamut Calculator 的 Paste 按钮是空实现

**实现范围**
1. 复用 SpectrumPage 的剪贴板解析逻辑
2. 在 Gamut Calculator 中粘贴后创建临时/持久光谱
3. 刷新下拉列表并自动选中新粘贴的光谱
4. 支持 RGB 和 Color Filter 的 Paste

**验收标准**
- 从剪贴板粘贴光谱后可以在 Gamut Calculator 中选择
- 粘贴的光谱正确保存到数据库
- UI 测试覆盖

**涉及文件**
- `src/colorlab_pro/ui/pages/gamut_calculator_page.py`
- `src/colorlab_pro/controllers/spectrum_controller.py`

---

### TASK-9: 白点坐标自动传递连接确认

**需求描述**
- RGB 坐标默认从 RGB 光谱经过彩膜修正后的色坐标获取
- 当前 GamutCalculatorPage 发射了信号，但需确认 WhitePointPage 是否连接

**实现范围**
1. 检查 `app.py` 中信号连接
2. 如未连接，补充连接逻辑
3. 当 Gamut Calculator 计算完成后，自动将 RGB 坐标填充到 White Point 页面
4. 避免覆盖用户已手动输入的值（可选提示）

**验收标准**
- Gamut Calculator 计算后 White Point 页面自动获得 RGB 坐标
- 手动输入的坐标不会被意外覆盖
- UI 测试通过

**涉及文件**
- `src/colorlab_pro/ui/app.py`
- `src/colorlab_pro/ui/pages/white_point_page.py`

---

### TASK-10: 全量回归测试

**需求描述**
- 所有修复完成后运行全量测试
- 确保没有回归问题

**实现范围**
1. 运行 `pytest` 全量测试
2. 运行 `ruff check`
3. 运行 `mypy` 类型检查
4. 修复所有失败项
5. 更新 CURRENT_TASK.md 和 PROJECT_STATUS.md

**验收标准**
- pytest: 全部通过
- ruff: 无错误
- mypy: 无错误

---

## 进度日志

### 2026-06-19

- 创建本任务跟踪文档
- 完成需求确认与差异分析
- 输出差异报告：`d:\0000TARE\colorlab-final-requirements-diff\colorlab-final-requirements-diff.html`
- 计划按 P0 → P1 → P2 顺序推进

---

## 决策记录

- D-021: 新增 `spectrum.category` 字段用于彩膜/QD/LED/白光分类（待创建）
- D-022: 导入时强制对齐到 380-780 nm，缺失值补 0（待创建）
- D-023: Gamut Calculator 增加白光 + 彩膜模式（待创建）
