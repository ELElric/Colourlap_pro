# ColorLab Pro — 发布说明

## V1.1.0

ColorLab Pro 是一款面向显示/光学行业的光谱与色度分析桌面应用，提供光谱数据管理、色度分析、色域计算、白点匹配与彩膜厚度优化等核心功能。

### 新增功能

- **光谱库（Spectrum Library）**
  - 支持 CSV / Excel / 剪贴板粘贴 / 拖拽四种导入方式
  - 光谱预处理：峰值归一化、面积归一化、等距插值（Cubic / PCHIP）、NaN 缺口自动填充
  - 色度信息分析：XYZ 三刺激值、xy 色坐标、u'v' 色坐标、CCT 相关色温、主波长、峰值波长、FWHM 半高宽、激发纯度
  - 通道自动检测（R/G/B 波段峰值判定）
  - 多选批量操作、右键菜单（重命名 / 复制 / 删除 / 导出）

- **色域计算（Gamut Calculator）**
  - 两种模式：RGB + 彩膜 / 白光 + 彩膜
  - Lambert-Beer 滤光计算，彩膜厚度实时调节
  - CIE 1931 与 CIE 1976 色度图同步显示
  - 对 NTSC / DCI-P3 / BT2020 的覆盖率（Coverage）与匹配率（Match）
  - 原始与滤光后 RGB 三角形、白点、光谱轨迹叠加显示
  - 色域结果表与色度数据表（RGBW 的 x, y, u', v', X, Y, CCT）

- **白点计算（White Point）**
  - 正向计算：输入 RGB 坐标 + RGB 比例 → 输出白点（x, y, u', v', CCT）
  - 反向计算：输入 RGB 坐标 + 目标白点 → 输出 RGB 比例（非负最小二乘）
  - 色域覆盖率与匹配率分析

- **厚度优化（Thickness Optimizer）**
  - 四种优化目标：最大化 BT2020 覆盖率、最大化 DCI-P3 覆盖率、目标白点、目标坐标
  - 单通道扫描（固定 RCF/BCF，扫描 GCF 100 步）
  - Top20 结果表 + 三条扫描曲线（覆盖率 / 坐标误差 / 白点轨迹）
  - 后台线程执行，不阻塞 UI

- **项目管理**
  - 多项目支持，项目级光谱数据隔离
  - SQLite 数据库持久化
  - 配置文件 `~/.colorlab_pro/config.yaml`

- **导入导出**
  - CSV / Excel / JSON 三种导出格式
  - 导入导出 round-trip 验证

### 系统要求

- Windows 10/11（64 位）
- 打包版无需安装 Python
- 从源码运行需 Python 3.10 - 3.14

### 安装方式

**打包版（推荐终端用户）**：下载 `ColorLabPro-Setup.exe` 双击安装。

**从源码运行（开发者）**：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
colorlab-pro gui
```

### 数据与配置位置

| 内容 | 路径 |
|------|------|
| 数据库 | `~/.colorlab_pro/data/user/default/colorlab.db` |
| 配置文件 | `~/.colorlab_pro/config.yaml` |
| 日志文件 | `~/.colorlab_pro/logs/colorlab_pro.log` |

### 已知限制

1. **厚度优化为单通道扫描**：当前版本固定 RCF/BCF 于范围中点，仅扫描 GCF。三通道联合优化（L-BFGS-B）已在内置引擎实现，将在后续版本接入 UI。
2. **UI 文本为中英混杂**：后续版本将统一为中文并支持中英双语切换。
3. **无代码签名**：Windows 首次运行可能触发 SmartScreen 警告，点击"仍要运行"即可。

### 反馈与支持

遇到问题请提供 `~/.colorlab_pro/logs/colorlab_pro.log` 日志文件以便排查。

---

## V1.0

- 初版（仅供历史参考）
