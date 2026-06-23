# 10 开发路线图

> V1.1 任务分解。按顺序执行，每完成一个任务更新 `ai_context/CURRENT_TASK.md`。

## Phase 1：基础设施（T-01）

- **T-01**: 项目骨架引导

## Phase 2：核心算法（T-02 ~ T-06）

- **T-02**: SpectrumNormalizer（归一化、插值、通道检测）
- **T-03**: SpectrumAnalyzer（XYZ/xy/u-prime-v-prime/CCT）
- **T-04**: ColorCalculator（基础色度）
- **T-05**: GamutCalculator（Coverage/Match）
- **T-06**: WhitePointCalculator + ThicknessOptimizer

## Phase 3：数据层（T-07 ~ T-09）

- **T-07**: ORM 模型与迁移
- **T-08**: SpectrumRepository
- **T-09**: ProjectRepository

## Phase 4：服务层（T-10 ~ T-13）

- **T-10**: SpectrumService
- **T-11**: ColorService
- **T-12**: GamutService
- **T-13**: OptimizationService

## Phase 5：UI 框架（T-14 ~ T-16）

- **T-14**: 主窗口与导航
- **T-15**: 主题与样式
- **T-16**: ViewModel 基类

## Phase 6：UI 页面（T-17 ~ T-23）

- **T-17**: Project 页面
- **T-18**: Spectrum 页面
- **T-19**: Mix 页面
- **T-20**: Analyze 页面
- **T-21**: Optimize 页面
- **T-22**: Report 页面
- **T-23**: Settings 页面

## Phase 7：导入导出（T-24 ~ T-26）

- **T-24**: CSV/XLSX Importer
- **T-25**: Exporter（CSV / Excel / 报告）
- **T-26**: 厂商格式适配（可选）

## Phase 8：集成与发布（T-27 ~ T-30）

- **T-27**: 端到端集成测试
- **T-28**: 性能优化
- **T-29**: 打包（PyInstaller）
- **T-30**: V1.1 发布