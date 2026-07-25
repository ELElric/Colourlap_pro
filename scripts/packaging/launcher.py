"""ColorLab Pro Launcher — 最小化启动器.

目标:
- exe 本身尽量小（约 10MB，只含 Python 标准库 + tkinter）
- 打开时检测本地依赖，缺失的从 PyPI 镜像在线安装
- 显示进度条
- 最后启动 ColorLab Pro

启动流程:
1. 检查本地 runtime 目录（%LOCALAPPDATA%/ColorLabPro/runtime/）
2. 若无 python.exe → 从 python.org 下载 python-embed
3. 逐个检查依赖是否能 import + 版本是否满足
4. 缺失/版本不匹配的依赖从 PyPI 镜像安装
5. 启动 app_pywebview.py
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# tkinter 是标准库，精简版 Python 可能缺失
try:
    from tkinter import Tk, ttk
    _HAS_TKINTER = True
except ImportError:
    _HAS_TKINTER = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
APP_NAME = "ColorLab Pro"
VERSION = "1.1.0"

# runtime 安装位置：用户本地目录（避免权限问题）
RUNTIME_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ColorLabPro" / "runtime"
PYTHON_EXE = RUNTIME_DIR / "python.exe"
SITE_PACKAGES = RUNTIME_DIR / "Lib" / "site-packages"

# 项目源码位置（PyInstaller 打包后从 _MEIPASS 读取；开发模式从项目根目录读取）
APP_ENTRY = "scripts/run_pywebview.py"

# PyPI 国内镜像（依次尝试，选第一个能连通的）
PYPI_MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.doubanio.com/simple",
    "https://mirrors.huaweicloud.com/repository/pypi/simple",
    "https://pypi.org/simple",
]

# python-embed 下载地址（python.org 官方 CDN，非 GitHub）
PYTHON_EMBED_BASE_URL = "https://www.python.org/ftp/python"

# 目标 Python 版本（与开发环境一致，确保包兼容性）
TARGET_PY_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
TARGET_PY_FULL_VERSION = f"{TARGET_PY_VERSION}.{sys.version_info.micro}"

# Python 嵌入版精确版本映射
PYTHON_EMBED_VERSIONS = {
    "3.10": "3.10.11",
    "3.11": "3.11.9",
    "3.12": "3.12.7",
    "3.13": "3.13.1",
}

# 项目依赖（包名, 最低版本, 最高版本, import 名）
# import 名用于检测是否已安装；版本范围用于 pip install 约束
PROJECT_DEPS = [
    ("numpy", "1.26", "2.3", "numpy"),
    ("colour-science", "0.4.4", "0.5", "colour"),
    ("SQLAlchemy", "2.0", "2.1", "sqlalchemy"),
    ("shapely", "2.0", "2.2", "shapely"),
    ("loguru", "0.7", "0.8", "loguru"),
    ("scipy", "1.11", "1.18", "scipy"),
    ("openpyxl", "3.1", "3.2", "openpyxl"),
    ("pyyaml", "6.0", "6.1", "yaml"),
    ("matplotlib", "3.7", "3.12", "matplotlib"),
    ("pywebview", "", "", "webview"),
    ("PySide6", "6.6", "6.13", "PySide6"),
]


def _resource_path(rel: str) -> Path:
    """获取资源路径 — PyInstaller 打包后从 _MEIPASS 获取."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / rel


def _get_embed_url() -> str:
    """构建 python-embed zip 下载 URL."""
    full_ver = PYTHON_EMBED_VERSIONS.get(TARGET_PY_VERSION, TARGET_PY_FULL_VERSION)
    return f"{PYTHON_EMBED_BASE_URL}/{full_ver}/python-{full_ver}-embed-amd64.zip"


# ---------------------------------------------------------------------------
# Network utilities
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, progress_callback=None) -> bool:
    """下载文件，带进度回调."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{VERSION}"})
        with urllib.request.urlopen(req, timeout=120) as response:
            total = int(response.headers.get("Content-Length", 0))
            chunk_size = 65536
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_callback:
                        percent = int(downloaded * 100 / total)
                        progress_callback(percent, f"Downloading... {percent}%")
            return True
    except Exception as exc:
        print(f"[Launcher] Download failed: {url} - {exc}", file=sys.stderr)
        return False


def _find_working_mirror() -> str:
    """尝试找到一个可用的 PyPI 镜像."""
    for mirror in PYPI_MIRRORS:
        try:
            req = urllib.request.Request(
                mirror, headers={"User-Agent": f"{APP_NAME}/{VERSION}"}, method="HEAD"
            )
            urllib.request.urlopen(req, timeout=10)
            return mirror
        except Exception:
            continue
    return PYPI_MIRRORS[0]


def extract_zip(archive_path: Path, dest_dir: Path) -> bool:
    """解压 .zip 文件（标准库 zipfile）."""
    import zipfile
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
        return True
    except Exception as exc:
        print(f"[Launcher] Extract failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Runtime setup
# ---------------------------------------------------------------------------

def check_python_installed() -> bool:
    """检查 runtime 目录是否已有可用的 python.exe."""
    return PYTHON_EXE.is_file()


def install_python_embed(progress_callback=None) -> bool:
    """下载并解压 python-embed 到 runtime 目录."""
    if progress_callback:
        progress_callback(0, f"Downloading Python {TARGET_PY_VERSION}...")

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.gettempdir()) / "colorlab_pro_install"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    embed_zip = tmp_dir / f"python-{TARGET_PY_VERSION}-embed-amd64.zip"

    url = _get_embed_url()
    if not download_file(url, embed_zip, progress_callback):
        # 尝试其他版本
        for alt_ver in ["3.12", "3.11", "3.10"]:
            if alt_ver == TARGET_PY_VERSION:
                continue
            full_ver = PYTHON_EMBED_VERSIONS.get(alt_ver, f"{alt_ver}.0")
            alt_url = f"{PYTHON_EMBED_BASE_URL}/{full_ver}/python-{full_ver}-embed-amd64.zip"
            if progress_callback:
                progress_callback(0, f"Trying Python {alt_ver}...")
            if download_file(alt_url, embed_zip, progress_callback):
                break
        else:
            return False

    if progress_callback:
        progress_callback(80, "Extracting Python...")
    if not extract_zip(embed_zip, RUNTIME_DIR):
        return False

    # 配置 ._pth 文件：启用 site-packages
    if progress_callback:
        progress_callback(90, "Configuring Python...")
    for pth_file in RUNTIME_DIR.glob("python*._pth"):
        try:
            content = pth_file.read_text(encoding="utf-8")
            content = content.replace("#import site", "import site")
            if "Lib/site-packages" not in content:
                content += "\nLib/site-packages\n"
            pth_file.write_text(content, encoding="utf-8")
        except Exception:
            pass

    SITE_PACKAGES.mkdir(parents=True, exist_ok=True)
    return PYTHON_EXE.is_file()


def ensure_pip(progress_callback=None) -> bool:
    """为嵌入式 Python 安装 pip（下载 get-pip.py 并执行）."""
    # 先检查 pip 是否已存在
    try:
        result = subprocess.run(
            [str(PYTHON_EXE), "-m", "pip", "--version"],
            capture_output=True, timeout=10,
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    if progress_callback:
        progress_callback(0, "Installing pip...")

    tmp_dir = Path(tempfile.gettempdir()) / "colorlab_pro_install"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    get_pip_py = tmp_dir / "get-pip.py"

    if not get_pip_py.is_file():
        if not download_file("https://bootstrap.pypa.io/get-pip.py", get_pip_py):
            return False

    try:
        subprocess.run(
            [str(PYTHON_EXE), str(get_pip_py), "-q"],
            check=True, capture_output=True, timeout=120,
        )
        return True
    except Exception as exc:
        print(f"[Launcher] pip install failed: {exc}", file=sys.stderr)
        return False


def check_dependency(python_exe: Path, import_name: str, min_ver: str, max_ver: str) -> bool:
    """检查单个依赖是否已安装且版本满足要求.

    返回 True 表示已安装且版本兼容，False 表示需要安装/升级。
    """
    # 用子进程 import 测试，避免污染当前进程
    script = f"""
import sys
try:
    import {import_name}
    ver = getattr({import_name}, '__version__', '0')
    print(f"OK|{{ver}}")
except ImportError:
    print("MISSING|0")
except Exception as e:
    print(f"ERROR|{{e}}")
"""
    try:
        result = subprocess.run(
            [str(python_exe), "-c", script],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "PYTHONPATH": str(SITE_PACKAGES)},
        )
        output = result.stdout.strip()
        if not output:
            return False
        status, ver = output.split("|", 1)
        if status != "OK":
            return False
        # 版本检查
        if min_ver or max_ver:
            return _version_satisfies(ver, min_ver, max_ver)
        return True
    except Exception:
        return False


def _version_satisfies(current: str, min_ver: str, max_ver: str) -> bool:
    """检查 current 版本是否在 [min_ver, max_ver) 范围内."""
    def parse(v: str) -> tuple:
        parts = []
        for p in v.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                # 处理类似 "1.26.0rc1" 的情况
                num = ""
                for ch in p:
                    if ch.isdigit():
                        num += ch
                    else:
                        break
                parts.append(int(num) if num else 0)
        return tuple(parts)

    cur = parse(current)
    if min_ver:
        if cur < parse(min_ver):
            return False
    if max_ver:
        if cur >= parse(max_ver):
            return False
    return True


def install_dependencies(progress_callback=None) -> bool:
    """检查并安装缺失的依赖，返回是否全部成功."""
    # 1. 找到可用镜像
    if progress_callback:
        progress_callback(0, "Finding PyPI mirror...")
    mirror = _find_working_mirror()
    print(f"[Launcher] Using mirror: {mirror}")
    trusted_host = mirror.split("//")[1].split("/")[0]

    # 2. 逐个检查依赖
    missing = []
    total = len(PROJECT_DEPS)
    for i, (pkg_name, min_ver, max_ver, import_name) in enumerate(PROJECT_DEPS):
        if progress_callback:
            progress_callback(int(i / total * 30), f"Checking {pkg_name} ({i+1}/{total})...")
        if check_dependency(PYTHON_EXE, import_name, min_ver, max_ver):
            print(f"[Launcher] OK: {pkg_name}")
        else:
            print(f"[Launcher] Missing/old: {pkg_name}")
            missing.append((pkg_name, min_ver, max_ver))

    if not missing:
        if progress_callback:
            progress_callback(100, "All dependencies ready")
        return True

    # 3. 安装缺失的依赖
    print(f"[Launcher] Need to install {len(missing)} packages")
    install_total = len(missing)
    for i, (pkg_name, min_ver, max_ver) in enumerate(missing):
        # 构建版本约束
        if min_ver and max_ver:
            spec = f"{pkg_name}>={min_ver},<{max_ver}"
        elif min_ver:
            spec = f"{pkg_name}>={min_ver}"
        elif max_ver:
            spec = f"{pkg_name}<{max_ver}"
        else:
            spec = pkg_name

        percent = 30 + int(i / install_total * 65)
        if progress_callback:
            progress_callback(percent, f"Installing {pkg_name} ({i+1}/{install_total})...")
        print(f"[Launcher] Installing {spec} ({i+1}/{install_total})...")

        cmd = [
            str(PYTHON_EXE), "-m", "pip", "install",
            "--target", str(SITE_PACKAGES),
            "--index-url", mirror,
            "--trusted-host", trusted_host,
            "--no-cache-dir",
            "--quiet",
            spec,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                stderr = result.stderr[:300] if result.stderr else "unknown"
                print(f"[Launcher] Warning: install {spec} failed: {stderr}")
        except subprocess.TimeoutExpired:
            print(f"[Launcher] Warning: install {spec} timed out")
        except Exception as exc:
            print(f"[Launcher] Warning: install {spec} error: {exc}")

    if progress_callback:
        progress_callback(100, "Dependencies installed")
    return True


# ---------------------------------------------------------------------------
# Launch app
# ---------------------------------------------------------------------------

def _get_src_dir() -> Path:
    """获取项目源码目录."""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包：源码在 _MEIPASS/src
        meipass = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(sys.executable).parent
        return meipass / "src"
    else:
        return Path(__file__).resolve().parent.parent.parent / "src"


def _get_entry_script() -> Path:
    """获取入口脚本路径."""
    if getattr(sys, "frozen", False):
        meipass = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(sys.executable).parent
        return meipass / APP_ENTRY
    else:
        return Path(__file__).resolve().parent.parent.parent / APP_ENTRY


def launch_app() -> int:
    """启动 ColorLab Pro."""
    src_dir = _get_src_dir()
    entry_script = _get_entry_script()

    if not entry_script.is_file():
        print(f"[Launcher] Entry script not found: {entry_script}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    if pp:
        env["PYTHONPATH"] = f"{src_dir};{pp}"
    else:
        env["PYTHONPATH"] = str(src_dir)

    cmd = [str(PYTHON_EXE), str(entry_script)]
    print(f"[Launcher] Starting: {' '.join(cmd)}")
    print(f"[Launcher] PYTHONPATH={env['PYTHONPATH']}")

    proc = subprocess.Popen(cmd, env=env)
    proc.wait()
    return proc.returncode


# ---------------------------------------------------------------------------
# GUI Progress Dialog
# ---------------------------------------------------------------------------

class ProgressDialog:
    """进度窗口 — tkinter 不可用时回退到控制台."""

    def __init__(self, title: str):
        self._tk = False
        if _HAS_TKINTER:
            try:
                self.root = Tk()
                self.root.title(title)
                self.root.geometry("440x160")
                self.root.resizable(False, False)
                self.root.attributes("-topmost", True)

                self.root.update_idletasks()
                x = (self.root.winfo_screenwidth() // 2) - 220
                y = (self.root.winfo_screenheight() // 2) - 80
                self.root.geometry(f"+{x}+{y}")

                self.label = ttk.Label(
                    self.root, text="Initializing...",
                    font=("Microsoft YaHei", 11), wraplength=400,
                )
                self.label.pack(pady=(20, 8))

                self.progress = ttk.Progressbar(self.root, length=400, mode="determinate")
                self.progress.pack(pady=5)

                self.detail = ttk.Label(
                    self.root, text="", font=("Microsoft YaHei", 9),
                    foreground="#666",
                )
                self.detail.pack(pady=(0, 10))

                self.root.protocol("WM_DELETE_WINDOW", lambda: None)
                self._tk = True
            except Exception:
                pass

        if not self._tk:
            print(f"[Launcher] {title}")
            print("[Launcher] (console mode)")

    def update(self, percent: int, message: str):
        if self._tk:
            try:
                self.progress["value"] = percent
                self.label["text"] = message
                self.root.update_idletasks()
            except Exception:
                pass
        else:
            print(f"[Launcher] {percent}% - {message}")

    def close(self):
        if self._tk:
            try:
                self.root.destroy()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Launcher 入口."""
    # 检查 runtime 是否完全就绪（python + 所有依赖）
    python_ok = check_python_installed()
    deps_ok = False
    if python_ok:
        deps_ok = all(
            check_dependency(PYTHON_EXE, imp, mn, mx)
            for _, mn, mx, imp in PROJECT_DEPS
        )

    # 全部就绪 → 直接启动（静默，无 UI）
    if python_ok and deps_ok:
        print("[Launcher] Runtime ready, starting app...")
        return launch_app()

    # 需要安装 → 显示进度窗口
    dialog = ProgressDialog(f"{APP_NAME} - Setup")
    if dialog._tk:
        dialog.root.update()

    def _progress(percent: int, msg: str):
        dialog.update(percent, msg)
        if dialog._tk:
            dialog.root.update()

    # Step 1: 安装 Python
    if not python_ok:
        _progress(0, f"Installing Python {TARGET_PY_VERSION}...")
        if not install_python_embed(_progress):
            dialog.close()
            _show_error("Failed to download Python. Check your network connection.")
            return 1

    # Step 2: 安装 pip
    _progress(0, "Preparing pip...")
    if not ensure_pip(_progress):
        dialog.close()
        _show_error("Failed to install pip. Check your network connection.")
        return 1

    # Step 3: 检查并安装依赖
    if not install_dependencies(_progress):
        dialog.close()
        _show_error("Some dependencies failed to install. Check your network connection.")
        return 1

    dialog.close()
    return launch_app()


def _show_error(message: str):
    """显示错误对话框."""
    try:
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            f"{message}\n\n无法准备运行环境，请检查网络连接。",
            f"{APP_NAME} Error",
            0x10,  # MB_ICONERROR
        )
    except Exception:
        print(f"[Launcher] ERROR: {message}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
