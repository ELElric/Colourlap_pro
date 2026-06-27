## Why

ColorLab Pro 的 4 个 UI 页面已投入使用，但审计发现多个已有功能存在实现异常：按钮无功能、数据未回显、信号泄漏等。需要逐一修复这些"看着能用但实际有问题"的功能。

## What Changes

### 🔴 HIGH
- (已修复) 膜厚优化 Target White Point/Coordinate 模式崩溃
- **Run Sensitivity 按钮在 Coverage 标签下点击无效** — 切换到 coverage 标签时只渲染图表，不触发敏感性分析

### 🟠 MEDIUM
- (已修复) 光谱库多选信息卡片 xy/u'v' 标注互错
- (已修复) 色域 CIE 图白点标记计算错误
- (已修复) 膜厚优化 progress 信号累积连接
- (已修复) Run Sensitivity 缓存不更新
- (已修复) 粘贴光谱后未自动选中
- **色域 Trajectory 复选框存在但从未被读取** — 勾选/取消无任何视觉效果
- **色域 RGB Spectrum Data 表格从未被填充** — 前后端都缺失，永远显示 "No data"
- **白点 status-primaries/status-white 永远显示 "-"** — 状态项无更新逻辑
- **白点 CCT 值后端返回但前端未显示** — 后端计算了 CCT，前端忽略了该字段
- **runSensitivity() progress 信号累积泄漏** — 每次调用新增匿名 handler 不断开

### 🟢 LOW
- (已修复) W/Pasted 类别徽章 + 分类过滤器缺 W
- (已修复) 参考色域复选框双重渲染 + 导出按钮背景色
- (已修复) BT2020 预设说明 + 敏感性硬编码
- **Settings 按钮无功能** — 仅显示 "Settings not available yet"
- **compare_configurations Slot 未接入前端** — 后端完整但无 UI 调用
- **refreshData() 死代码** — 无 UI 触发器

## Impact

- **修改文件**: 4 个 HTML + 2 个 Python 页面模块
- **依赖**: 无新依赖
- **风险**: 均为前端修复，不影响数据库和后端计算逻辑
