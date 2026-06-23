# ColorLab Pro

> Professional spectral data management and gamut analysis tool for the display industry.

ColorLab Pro 是一款面向显示/光学行业的桌面应用，提供光谱数据管理、色度分析、色域计算、白点匹配与彩膜厚度优化等核心功能。

## 功能概览

- **Spectrum Library（光谱库）** — 支持 CSV/Excel/粘贴/拖拽导入，光谱预处理（归一化/插值/缺口填充），色度信息分析（XYZ、xy、u'v'、CCT、主波长、Peak、FWHM、Purity）。
- **Gamut Calculator（色域计算）** — RGB+彩膜 或 白光+彩膜 两种模式，Lambert-Beer 滤光计算，实时 CIE 1931/1976 色度图，对 NTSC/DCI-P3/BT2020 的覆盖率与匹配率。
- **White Point（白点计算）** — 正向（RGB 比例 → 白点）与反向（目标白点 → RGB 比例，非负最小二乘）计算。
- **Thickness Optimizer（厚度优化）** — 彩膜厚度扫描优化，输出 Top20 结果与扫描曲线。

## 系统要求

- Windows 10/11（64 位）
- Python 3.10 - 3.14（开发环境）
- 打包版无需安装 Python

## 安装

### 方式一：打包版（推荐终端用户）

下载发布包中的 `ColorLabPro-Setup.exe`，双击安装即可。数据库与配置文件自动存放在 `~/.colorlab_pro/`。

### 方式二：从源码运行（开发者）

```powershell
# 1. 创建虚拟环境
py -3.11 -m venv .venv
.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .

# 3. 初始化数据库（可选，首次启动会自动创建）
colorlab-pro init-db

# 4. 启动 GUI
colorlab-pro gui
```

## 快速启动

```powershell
# 启动图形界面
colorlab-pro gui

# 查看版本
colorlab-pro version
```

## 数据与配置位置

| 内容 | 路径 |
|------|------|
| 数据库 | `~/.colorlab_pro/data/user/default/colorlab.db` |
| 配置文件 | `~/.colorlab_pro/config.yaml` |
| 日志文件 | `~/.colorlab_pro/logs/colorlab_pro.log` |

> 注：数据库路径使用用户主目录下的绝对路径，确保无论从哪个工作目录启动应用，数据位置始终一致。

## 目录结构

```
colorlab-pro/
├── src/colorlab_pro/        # 源码
│   ├── config/              # 配置
│   ├── controllers/         # 控制器层
│   ├── database/            # ORM 与会话
│   ├── dto/                 # 数据传输对象
│   ├── engines/             # 核心计算引擎（色度学/色域/优化）
│   ├── exporters/           # 导出器（CSV/XLSX/JSON）
│   ├── importers/           # 导入器（CSV/XLSX）
│   ├── repositories/        # 仓储层
│   ├── services/            # 服务层
│   ├── ui/                  # UI 层（主窗口/页面/对话框/控件）
│   └── utils/               # 工具（日志/路径/校验/错误）
├── tests/                   # 测试（unit/integration/ui）
├── docs/                    # 开发文档（12 篇）
├── scripts/                 # 脚本
└── pyproject.toml           # 项目配置
```

## 技术栈

Python 3.11 · PySide6 · numpy · scipy · colour-science · SQLAlchemy · shapely · openpyxl · matplotlib · loguru

## 打包

使用 PyInstaller 打包为 Windows 可执行文件：

```powershell
pip install pyinstaller
pyinstaller colorlab_pro.spec
```

产物在 `dist/ColorLabPro/` 目录下。

## 许可证

Proprietary — 未经授权不得再分发。

## 技术支持

遇到问题请提供 `~/.colorlab_pro/logs/colorlab_pro.log` 日志文件以便排查。
