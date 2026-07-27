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
- WebView2 Runtime（Windows 11 已内置；Windows 10 需 [安装](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)）
- 打包版无需安装 Python

## 安装与使用

### 方式一：可执行文件（推荐终端用户）

从 [Releases](../../releases) 下载最新发布包，包含以下文件：

| 文件 | 说明 |
|------|------|
| `ColorLabPro.exe` | 启动器（约 13MB，含项目源码） |
| `runtime.7z` | Python 运行时 + 依赖包（约 210MB，可选，离线安装用） |

**使用方式：**

1. 将 `ColorLabPro.exe` 和 `runtime.7z` 放在同一目录
2. 双击 `ColorLabPro.exe`
3. 首次运行会显示进度条：
   - 若同级目录有 `runtime.7z` → 自动解压（约 30 秒）
   - 若无 `runtime.7z` → 从 PyPI 国内镜像在线下载安装
4. 后续启动自动检测已安装的依赖，缺失的才会下载，已安装的直接跳过

**进度条显示内容：**

```
Downloading Python 3.10...    ← 下载 python-embed（约 10MB）
Configuring Python...        ← 配置 ._pth 启用 site-packages
Installing pip...             ← 安装 pip 包管理器
Checking numpy (1/11)...      ← 逐个检查依赖是否已安装
Installing PySide6 (3/11)...  ← 仅安装缺失的依赖
```

**运行时文件位置：**

```
%LOCALAPPDATA%\ColorLabPro\runtime\       ← Python 解释器 + 依赖库
%LOCALAPPDATA%\ColorLabPro\runtime\Lib\site-packages\  ← pip 安装的第三方包
```

### 方式二：从源码运行（开发者）

```powershell
# 1. 创建虚拟环境
py -3.10 -m venv .venv
.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt
pip install -e .

# 3. 初始化数据库（可选，首次启动会自动创建）
colorlab-pro init-db

# 4. 启动 GUI（pywebview 版本，轻量）
python scripts/run_pywebview.py
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
│   ├── ui/                  # UI 层（pywebview 入口 + API 桥接）
│   │   ├── web/             # 前端页面（HTML/JS/CSS + ECharts）
│   │   ├── app.py           # pywebview 入口
│   │   └── pywebview_api.py # Python↔JS API 桥接
│   └── utils/               # 工具（日志/路径/校验/错误）
├── scripts/                 # 脚本
│   ├── run_pywebview.py     # pywebview 启动脚本
│   └── packaging/           # 打包脚本
│       ├── launcher.py      # 启动器（依赖检测 + 在线安装）
│       ├── build_launcher.py  # PyInstaller 打包脚本
│       └── build_runtime.py   # runtime.7z 依赖包构建脚本
├── tests/                   # 测试
├── docs/                    # 开发文档
└── pyproject.toml           # 项目配置
```

## 技术栈

Python 3.10 · pywebview · ECharts · numpy · scipy · colour-science · SQLAlchemy · shapely · openpyxl · matplotlib · loguru

## 打包与发布

### 构建启动器 EXE

使用 PyInstaller 将 launcher.py + 项目源码打包为单个 exe：

```powershell
python scripts/packaging/build_launcher.py
```

产物：`dist/ColorLabPro.exe`（约 13MB，含项目源码，不含第三方依赖）。

### 构建依赖包（可选）

若需要提供离线安装包，可将 Python 运行时 + 依赖打包为 `runtime.7z`：

```powershell
# 需要先安装 py7zr（或安装 7-Zip）
python -m pip install py7zr

# 一键构建
python scripts/packaging/build_runtime.py
```

产物：`dist/runtime.7z`（约 210MB，包含 Python 3.11 嵌入版 + 全部 11 个依赖）。

**手动打包步骤：**
1. 从 python.org 下载对应版本的 python-embed-amd64.zip
2. 解压到 `runtime/` 目录
3. 修改 `python*._pth` 启用 `import site` 和 `Lib/site-packages`
4. 用 `pip install --target runtime/Lib/site-packages` 安装所有依赖
5. 用 7-Zip 压缩为 `runtime.7z`

### 发布到 GitHub Releases

将 `ColorLabPro.exe` 和 `runtime.7z` 上传到 Release 即可。用户只需下载并放在一起运行。

### 启动器工作原理

```
用户双击 ColorLabPro.exe
        │
        ▼
检查 %LOCALAPPDATA%\ColorLabPro\runtime\python.exe
        │
        ├─ 存在 → 检查 11 个依赖能否 import + 版本兼容
        │         ├─ 全部 OK → 直接启动（秒开，无 UI）
        │         └─ 有缺失  → 只装缺失的包（显示进度条）
        │
        └─ 不存在 → 显示进度条
                  ① 本地有 runtime.7z → 解压
                  ② 否则从 python.org 下载 python-embed
                  ③ 配置 ._pth 启用 site-packages
                  ④ 下载 get-pip.py 安装 pip
                  ⑤ 从 PyPI 镜像逐包安装依赖
                  ⑥ 启动应用
```

### PyPI 镜像源

自动检测并选择最快的一个（依次尝试）：

| 优先级 | 镜像 | 地址 |
|--------|------|------|
| 1 | 清华大学 | https://pypi.tuna.tsinghua.edu.cn/simple |
| 2 | 阿里云 | https://mirrors.aliyun.com/pypi/simple |
| 3 | 豆瓣 | https://pypi.doubanio.com/simple |
| 4 | 华为云 | https://mirrors.huaweicloud.com/repository/pypi/simple |
| 5 | 官方（兜底） | https://pypi.org/simple |

### 依赖版本约束

启动器会检查每个依赖的版本是否在 `[min, max)` 范围内，不满足的会自动安装/升级：

| 包 | 最低版本 | 最高版本 |
|----|----------|----------|
| numpy | 1.26 | 2.3 |
| colour-science | 0.4.4 | 0.5 |
| SQLAlchemy | 2.0 | 2.1 |
| shapely | 2.0 | 2.2 |
| loguru | 0.7 | 0.8 |
| scipy | 1.11 | 1.18 |
| openpyxl | 3.1 | 3.2 |
| pyyaml | 6.0 | 6.1 |
| matplotlib | 3.7 | 3.12 |
| pywebview | — | — |
| PySide6 | 6.6 | 6.13 |

## 许可证

Proprietary — 未经授权不得再分发。

## 技术支持

遇到问题请提供 `~/.colorlab_pro/logs/colorlab_pro.log` 日志文件以便排查。
