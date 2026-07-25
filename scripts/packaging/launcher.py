"""ColorLab Pro Launcher — 检测/解压/下载/启动 Python Runtime.

启动流程:
1. 检查同级目录是否存在 runtime/ 文件夹 (已解压的 Python 环境)
2. 若不存在，检查同级目录是否存在 runtime.7z (自解压包) → 解压
3. 若都不存在，从网络下载 runtime.7z 后解压
4. 若下载也失败，使用 pip 在线安装模式：下载 python-embed + 逐包安装依赖
5. 使用 runtime/python.exe 启动 ColorLab Pro

打包方式:
- PyInstaller 将本脚本打包为 ColorLabPro.exe
- runtime.7z 作为外部文件与 .exe 同目录分发（可选）
- 首次运行时自动解压，后续直接复用 runtime/
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# tkinter 是标准库，但在某些精简版 Python 中可能缺失
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
RUNTIME_DIR_NAME = "runtime"
RUNTIME_ARCHIVE_NAME = "runtime.7z"
# 远程下载地址（可选，替换为实际托管地址即可）
RUNTIME_DOWNLOAD_URL = "https://github.com/your-org/colorlab-pro/releases/download/v1.1.0/runtime.7z"
PYTHON_REL_PATH = "python.exe"
APP_ENTRY = "scripts/run_pywebview.py"

# PyPI 国内镜像列表（依次尝试）
PYPI_MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.doubanio.com/simple",
    "https://mirrors.huaweicloud.com/repository/pypi/simple",
    "https://pypi.org/simple",  # 官方源作为最后回退
]

# python-embed 下载地址（无需 GitHub，直接从 python.org 官方 CDN）
PYTHON_EMBED_BASE_URL = "https://www.python.org/ftp/python"

# 项目依赖列表（与 pyproject.toml 保持同步）
PROJECT_DEPS = [
    "numpy>=1.26,<2.3",
    "colour-science>=0.4.4,<0.5",
    "SQLAlchemy>=2.0,<2.1",
    "shapely>=2.0,<2.2",
    "loguru>=0.7,<0.8",
    "scipy>=1.11,<1.18",
    "openpyxl>=3.1,<3.2",
    "pyyaml>=6.0,<6.1",
    "matplotlib>=3.7,<3.12",
    "pywebview",
    "PySide6>=6.6,<6.13",
]

# Python 嵌入版版本映射（当前开发环境对应的版本）
PYTHON_EMBED_VERSIONS = {
    "3.10": "3.10.11",
    "3.11": "3.11.9",
    "3.12": "3.12.7",
}


def _resource_path(rel: str) -> Path:
    """获取资源路径."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / rel


def _get_system_python_version() -> str:
    """获取当前系统 Python 版本（major.minor）."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _get_embed_url(py_version: str) -> str:
    """构建 python-embed zip 下载 URL."""
    full_ver = PYTHON_EMBED_VERSIONS.get(py_version)
    if not full_ver:
        # 回退：尝试 minor.0
        full_ver = f"{py_version}.0"
    return f"{PYTHON_EMBED_BASE_URL}/{full_ver}/python-{full_ver}-embed-amd64.zip"


# ---------------------------------------------------------------------------
# Archive operations
# ---------------------------------------------------------------------------

def check_runtime_exists(base_dir: Path) -> bool:
    """检查 runtime 目录是否已存在且包含 python.exe."""
    runtime_dir = base_dir / RUNTIME_DIR_NAME
    python_exe = runtime_dir / PYTHON_REL_PATH
    return python_exe.is_file()


def check_runtime_archive(base_dir: Path) -> bool:
    """检查同级目录是否存在 runtime.7z."""
    return (base_dir / RUNTIME_ARCHIVE_NAME).is_file()


def extract_7z(archive_path: Path, dest_dir: Path, progress_callback=None) -> bool:
    """解压 .7z 文件到目标目录."""
    seven_z = Path(r"C:\Program Files\7-Zip\7z.exe")
    if not seven_z.is_file():
        seven_z = Path(r"C:\Program Files (x86)\7-Zip\7z.exe")

    if seven_z.is_file():
        cmd = [str(seven_z), "x", str(archive_path), f"-o{dest_dir}", "-y"]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            pass

    try:
        import py7zr  # type: ignore[import-untyped]
        with py7zr.SevenZipFile(archive_path, mode="r") as sz:
            sz.extractall(path=dest_dir)
        return True
    except Exception:
        pass

    return False


def extract_zip(archive_path: Path, dest_dir: Path) -> bool:
    """解压 .zip 文件（使用标准库 zipfile，不依赖外部工具）."""
    import zipfile
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
        return True
    except Exception as exc:
        print(f"Extract zip failed: {exc}", file=sys.stderr)
        return False


def download_file(url: str, dest: Path, progress_callback=None) -> bool:
    """下载文件到指定路径，带进度回调."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{VERSION}"})
        with urllib.request.urlopen(req, timeout=120) as response:
            total = int(response.headers.get("Content-Length", 0))
            chunk_size = 8192
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
                        progress_callback(percent, f"Downloading {percent}%")
        return True
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Online install mode (pip + PyPI mirror)
# ---------------------------------------------------------------------------

def _find_working_mirror() -> str:
    """尝试找到一个可用的 PyPI 镜像源."""
    for mirror in PYPI_MIRRORS:
        try:
            req = urllib.request.Request(
                mirror,
                headers={"User-Agent": f"{APP_NAME}/{VERSION}"},
                method="HEAD",
            )
            urllib.request.urlopen(req, timeout=10)
            return mirror
        except Exception:
            continue
    # 全部超时也返回第一个
    return PYPI_MIRRORS[0]


def _run_pip_install(
    python_exe: Path,
    packages: list[str],
    target_dir: Path,
    mirror: str,
    progress_callback=None,
) -> bool:
    """使用指定 Python 的 pip 安装包列表到目标目录.

    利用 python -m ensurepip 先启用 pip，再用 pip install --target。
    """
    runtime_dir = target_dir

    # Step 1: 启用 pip（嵌入式 Python 默认不含 pip）
    if progress_callback:
        progress_callback(0, "Enabling pip...")

    # 尝试下载 get-pip.py
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    tmp_dir = Path(tempfile.gettempdir()) / "colorlab_pro_install"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    get_pip_py = tmp_dir / "get-pip.py"

    if not get_pip_py.is_file():
        if not download_file(get_pip_url, get_pip_py):
            print("[Launcher] Failed to download get-pip.py", file=sys.stderr)
            return False

    # 使用嵌入式 Python 安装 pip
    cmd = [str(python_exe), str(get_pip_py), "--no-wheel", "-q"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except Exception as exc:
        print(f"[Launcher] get-pip failed: {exc}", file=sys.stderr)
        # 不致命，pip 可能已经存在

    # Step 2: 逐包安装
    total = len(packages)
    site_packages = runtime_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    for i, pkg in enumerate(packages):
        percent = int((i + 1) / total * 100)
        pkg_name = pkg.split(">")[0].split("<")[0].split("=")[0].split("[")[0]
        if progress_callback:
            progress_callback(percent, f"Installing {pkg_name} ({i+1}/{total})...")
        print(f"[Launcher] Installing {pkg} ({i+1}/{total})...")

        cmd = [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "--target",
            str(site_packages),
            "--index-url",
            mirror,
            "--trusted-host",
            mirror.split("//")[1].split("/")[0],
            "--no-cache-dir",
            "--quiet",
            pkg,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                print(f"[Launcher] Warning: pip install {pkg} failed: {result.stderr[:200]}")
                # 继续安装下一个
        except subprocess.TimeoutExpired:
            print(f"[Launcher] Warning: pip install {pkg} timed out")
        except Exception as exc:
            print(f"[Launcher] Warning: pip install {pkg} error: {exc}")

    return True


def _copy_project_to_runtime(base_dir: Path, runtime_dir: Path):
    """将项目源码复制到 runtime 目录."""
    # 复制 src/
    src_dir = runtime_dir / "src"
    project_src = base_dir / "src"
    if project_src.is_dir() and not src_dir.is_dir():
        shutil.copytree(project_src, src_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"[Launcher] Copied src/ -> {src_dir}")

    # 复制 scripts/
    scripts_dir = runtime_dir / "scripts"
    project_scripts = base_dir / "scripts"
    if project_scripts.is_dir() and not scripts_dir.is_dir():
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for script in ["run_pywebview.py", "init_db.py"]:
            src = project_scripts / script
            if src.exists():
                shutil.copy2(src, scripts_dir / script)
        print(f"[Launcher] Copied scripts/ -> {scripts_dir}")

    # 复制 data/（如果有默认数据库）
    data_dir = runtime_dir / "data" / "user" / "default"
    project_data = base_dir / "data" / "user" / "default"
    if project_data.is_dir() and not data_dir.is_dir():
        data_dir.mkdir(parents=True, exist_ok=True)
        for db_file in project_data.glob("*.db"):
            shutil.copy2(db_file, data_dir / db_file.name)
        print(f"[Launcher] Copied data/ -> {data_dir}")


def setup_runtime_online(base_dir: Path, progress_callback=None) -> Path | None:
    """在线安装模式：下载 python-embed + pip 安装所有依赖.

    流程:
      1. 下载 python-embed zip（从 python.org 官方）
      2. 解压到 runtime/ 目录
      3. 修改 python*._pth 解除 import 限制
      4. 安装 get-pip.py 启用 pip
      5. 从 PyPI 国内镜像逐包安装依赖
      6. 复制项目源码到 runtime/
    """
    runtime_dir = base_dir / RUNTIME_DIR_NAME
    runtime_dir.mkdir(parents=True, exist_ok=True)
    python_exe = runtime_dir / PYTHON_REL_PATH

    # Step 1: 下载 python-embed
    py_ver = _get_system_python_version()
    embed_url = _get_embed_url(py_ver)
    if progress_callback:
        progress_callback(0, f"Downloading Python {py_ver} embed...")

    tmp_dir = Path(tempfile.gettempdir()) / "colorlab_pro_install"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    embed_zip = tmp_dir / f"python-{py_ver}-embed-amd64.zip"

    if not download_file(embed_url, embed_zip, progress_callback):
        # 尝试其他版本
        print(f"[Launcher] Failed to download Python {py_ver} embed, trying alternatives...")
        for alt_ver in ["3.12", "3.11", "3.10"]:
            if alt_ver == py_ver:
                continue
            alt_url = _get_embed_url(alt_ver)
            if progress_callback:
                progress_callback(0, f"Downloading Python {alt_ver} embed...")
            if download_file(alt_url, embed_zip, progress_callback):
                py_ver = alt_ver
                embed_url = alt_url
                break
        else:
            print("[Launcher] Failed to download any Python embed version", file=sys.stderr)
            return None

    # Step 2: 解压
    if progress_callback:
        progress_callback(15, "Extracting Python embed...")
    if not extract_zip(embed_zip, runtime_dir):
        print("[Launcher] Failed to extract Python embed", file=sys.stderr)
        return None

    # Step 3: 修改 ._pth 文件以启用 site-packages
    if progress_callback:
        progress_callback(20, "Configuring Python environment...")
    pth_files = list(runtime_dir.glob("python*._pth"))
    for pth_file in pth_files:
        try:
            content = pth_file.read_text(encoding="utf-8")
            # 取消 import site 的注释
            content = content.replace("#import site", "import site")
            # 添加 Lib/site-packages 路径
            if "Lib/site-packages" not in content:
                content += "\nLib/site-packages\n"
            pth_file.write_text(content, encoding="utf-8")
            print(f"[Launcher] Configured {pth_file.name}")
        except Exception as exc:
            print(f"[Launcher] Warning: failed to configure {pth_file.name}: {exc}")

    # 创建 Lib 目录结构
    (runtime_dir / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)

    # Step 4: 查找可用镜像并安装依赖
    if progress_callback:
        progress_callback(25, "Finding PyPI mirror...")
    mirror = _find_working_mirror()
    print(f"[Launcher] Using mirror: {mirror}")

    # Step 5: 逐包安装
    if progress_callback:
        progress_callback(30, "Installing dependencies...")
    _run_pip_install(python_exe, PROJECT_DEPS, runtime_dir, mirror, progress_callback)

    # Step 6: 复制项目源码
    if progress_callback:
        progress_callback(90, "Copying project files...")
    _copy_project_to_runtime(base_dir, runtime_dir)

    # 验证
    if python_exe.is_file():
        if progress_callback:
            progress_callback(100, "Runtime ready")
        return python_exe

    return None


# ---------------------------------------------------------------------------
# Main ensure_runtime (orchestrator)
# ---------------------------------------------------------------------------

def ensure_runtime(base_dir: Path, progress_callback=None) -> Path | None:
    """确保 runtime 目录存在，返回 python.exe 路径或 None.

    流程:
      1. 检查 runtime/ 目录是否存在
      2. 若不存在，检查 runtime.7z 是否存在 → 解压
      3. 若 .7z 不存在，尝试下载 runtime.7z（远程 URL）
      4. 若下载也失败，使用 pip 在线安装模式
    """
    runtime_dir = base_dir / RUNTIME_DIR_NAME
    python_exe = runtime_dir / PYTHON_REL_PATH

    # 已有 runtime
    if python_exe.is_file():
        if progress_callback:
            progress_callback(100, "Runtime ready")
        return python_exe

    archive_path = base_dir / RUNTIME_ARCHIVE_NAME

    # 本地 .7z 存在 → 解压
    if archive_path.is_file():
        if progress_callback:
            progress_callback(0, "Extracting runtime from archive...")
        if extract_7z(archive_path, base_dir, progress_callback):
            if python_exe.is_file():
                if progress_callback:
                    progress_callback(100, "Runtime extracted")
                return python_exe
        shutil.rmtree(runtime_dir, ignore_errors=True)

    # 尝试远程下载 .7z
    if progress_callback:
        progress_callback(0, "Downloading runtime archive...")
    tmp_dir = Path(tempfile.gettempdir()) / "colorlab_pro_download"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_archive = tmp_dir / RUNTIME_ARCHIVE_NAME

    if download_file(RUNTIME_DOWNLOAD_URL, tmp_archive, progress_callback):
        shutil.copy2(tmp_archive, archive_path)
        if progress_callback:
            progress_callback(50, "Extracting downloaded archive...")
        if extract_7z(archive_path, base_dir, progress_callback):
            if python_exe.is_file():
                if progress_callback:
                    progress_callback(100, "Runtime ready")
                return python_exe
        shutil.rmtree(runtime_dir, ignore_errors=True)

    # 全部失败 → 在线安装模式（从 PyPI 镜像逐包安装）
    if progress_callback:
        progress_callback(0, "Archive unavailable, switching to online install...")
    print("[Launcher] Switching to online install mode (PyPI mirror)")
    return setup_runtime_online(base_dir, progress_callback)


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

def launch_app(python_exe: Path, base_dir: Path) -> int:
    """使用指定的 Python 解释器启动 ColorLab Pro."""
    runtime_src = base_dir / RUNTIME_DIR_NAME / "src"
    if runtime_src.is_dir():
        src_dir = runtime_src
        entry_script = base_dir / RUNTIME_DIR_NAME / APP_ENTRY
    else:
        src_dir = base_dir / "src"
        entry_script = base_dir / APP_ENTRY

    if not entry_script.is_file():
        alt_entry = base_dir / RUNTIME_DIR_NAME / "scripts" / "run_pywebview.py"
        if alt_entry.is_file():
            entry_script = alt_entry

    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    if pp:
        env["PYTHONPATH"] = f"{src_dir};{pp}"
    else:
        env["PYTHONPATH"] = str(src_dir)

    cmd = [str(python_exe), str(entry_script)]
    print(f"[Launcher] Starting: {' '.join(cmd)}")
    print(f"[Launcher] PYTHONPATH={env['PYTHONPATH']}")

    proc = subprocess.Popen(cmd, env=env, cwd=str(base_dir))
    proc.wait()
    return proc.returncode


# ---------------------------------------------------------------------------
# GUI Progress Dialog
# ---------------------------------------------------------------------------

class ProgressDialog:
    """简易进度窗口，用于显示安装/解压进度."""

    def __init__(self, title: str):
        self._tk = False
        if _HAS_TKINTER:
            try:
                self.root = Tk()
                self.root.title(title)
                self.root.geometry("420x140")
                self.root.resizable(False, False)
                self.root.attributes("-topmost", True)

                self.root.update_idletasks()
                x = (self.root.winfo_screenwidth() // 2) - 210
                y = (self.root.winfo_screenheight() // 2) - 70
                self.root.geometry(f"+{x}+{y}")

                self.label = ttk.Label(self.root, text="Preparing runtime...", font=("Microsoft YaHei", 11))
                self.label.pack(pady=(15, 5))

                self.progress = ttk.Progressbar(self.root, length=380, mode="determinate")
                self.progress.pack(pady=5)

                self.root.protocol("WM_DELETE_WINDOW", lambda: None)
                self._tk = True
            except Exception:
                pass

        if not self._tk:
            print(f"[Launcher] {title}")
            print("[Launcher] (tkinter not available, using console output)")

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

    def run(self):
        if self._tk:
            self.root.mainloop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Launcher 入口."""
    base_dir = _resource_path("")

    # 静默模式
    if check_runtime_exists(base_dir):
        python_exe = base_dir / RUNTIME_DIR_NAME / PYTHON_REL_PATH
        return launch_app(python_exe, base_dir)

    # 显示进度窗口
    dialog = ProgressDialog(f"{APP_NAME} - Setup")
    dialog.update(0, "Checking runtime environment...")
    if dialog._tk:
        dialog.root.update()

    def _progress(percent: int, msg: str):
        dialog.update(percent, msg)
        if dialog._tk:
            dialog.root.update()

    python_exe = ensure_runtime(base_dir, _progress)
    dialog.close()

    if python_exe is None:
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            "无法准备运行环境。请检查网络连接，或联系技术支持。\n\n"
            "Failed to prepare runtime. Please check your network.",
            f"{APP_NAME} Error",
            0x10,
        )
        return 1

    return launch_app(python_exe, base_dir)


if __name__ == "__main__":
    sys.exit(main())
