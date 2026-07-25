"""ColorLab Pro Launcher — 检测/解压/下载/启动 Python Runtime.

启动流程:
1. 检查同级目录是否存在 runtime/ 文件夹 (已解压的 Python 环境)
2. 若不存在，检查同级目录是否存在 runtime.7z (自解压包)
3. 若存在 .7z，解压到 runtime/ 目录
4. 若都不存在，从网络下载 runtime.7z 后解压
5. 使用 runtime/python.exe 启动 ColorLab Pro

打包方式:
- PyInstaller 将本脚本打包为 ColorLabPro.exe
- runtime.7z 作为外部文件与 .exe 同目录分发
- 首次运行时自动解压，后续直接复用 runtime/
"""

from __future__ import annotations

import ctypes
import os
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
# 远程下载地址（可替换为实际托管地址）
RUNTIME_DOWNLOAD_URL = "https://github.com/your-org/colorlab-pro/releases/download/v1.1.0/runtime.7z"
PYTHON_REL_PATH = "python.exe"  # runtime 目录内的 python 路径
APP_ENTRY = "scripts/run_pywebview.py"  # 项目入口（相对工作目录）


def _resource_path(rel: str) -> Path:
    """获取资源路径 — PyInstaller 打包后从 _MEIPASS 获取，开发时从脚本所在目录获取."""
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后的可执行文件所在目录
        base = Path(sys.executable).parent
    else:
        # 开发模式：以项目根目录为基准
        base = Path(__file__).resolve().parent.parent.parent
    return base / rel


def is_admin() -> bool:
    """检测当前进程是否拥有管理员权限."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0  # type: ignore[attr-defined]
    except Exception:
        return False


def check_runtime_exists(base_dir: Path) -> bool:
    """检查 runtime 目录是否已存在且包含 python.exe."""
    runtime_dir = base_dir / RUNTIME_DIR_NAME
    python_exe = runtime_dir / PYTHON_REL_PATH
    return python_exe.is_file()


def check_runtime_archive(base_dir: Path) -> bool:
    """检查同级目录是否存在 runtime.7z."""
    return (base_dir / RUNTIME_ARCHIVE_NAME).is_file()


def extract_7z(archive_path: Path, dest_dir: Path, progress_callback=None) -> bool:
    """解压 .7z 文件到目标目录.

    优先使用系统安装的 7z.exe，否则使用内置的 py7zr 库。
    """
    # 尝试系统 7z
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

    # 回退到 py7zr（如果已安装）
    try:
        import py7zr  # type: ignore[import-untyped]

        with py7zr.SevenZipFile(archive_path, mode="r") as sz:
            sz.extractall(path=dest_dir)
        return True
    except Exception:
        pass

    return False


def download_file(url: str, dest: Path, progress_callback=None) -> bool:
    """下载文件到指定路径，带进度回调.

    progress_callback(percent: int, msg: str) -> None
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{VERSION}"})
        with urllib.request.urlopen(req, timeout=60) as response:
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


def ensure_runtime(base_dir: Path, progress_callback=None) -> Path | None:
    """确保 runtime 目录存在，返回 python.exe 路径或 None.

    流程:
      1. 检查 runtime/ 目录是否存在
      2. 若不存在，检查 runtime.7z 是否存在
      3. 若 .7z 存在，解压
      4. 若都不存在，网络下载 .7z 后解压
    """
    runtime_dir = base_dir / RUNTIME_DIR_NAME
    python_exe = runtime_dir / PYTHON_REL_PATH

    if python_exe.is_file():
        if progress_callback:
            progress_callback(100, "Runtime ready")
        return python_exe

    archive_path = base_dir / RUNTIME_ARCHIVE_NAME

    # 本地自解压包存在
    if archive_path.is_file():
        if progress_callback:
            progress_callback(0, "Extracting runtime...")
        if extract_7z(archive_path, base_dir, progress_callback):
            if python_exe.is_file():
                if progress_callback:
                    progress_callback(100, "Runtime extracted")
                return python_exe
        # 解压失败，删除损坏的 runtime 目录
        import shutil
        shutil.rmtree(runtime_dir, ignore_errors=True)

    # 需要从网络下载
    if progress_callback:
        progress_callback(0, "Downloading runtime...")

    # 下载到临时文件，成功后再移动
    tmp_dir = Path(tempfile.gettempdir()) / "colorlab_pro_download"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_archive = tmp_dir / RUNTIME_ARCHIVE_NAME

    if download_file(RUNTIME_DOWNLOAD_URL, tmp_archive, progress_callback):
        # 下载成功，移动/复制到目标目录
        import shutil
        shutil.copy2(tmp_archive, archive_path)
        if progress_callback:
            progress_callback(90, "Extracting downloaded runtime...")
        if extract_7z(archive_path, base_dir, progress_callback):
            if python_exe.is_file():
                if progress_callback:
                    progress_callback(100, "Runtime ready")
                return python_exe

    return None


def launch_app(python_exe: Path, base_dir: Path) -> int:
    """使用指定的 Python 解释器启动 ColorLab Pro.

    设置 PYTHONPATH 后启动 run_pywebview.py。
    优先使用 runtime/src/（如果存在），否则使用项目根目录的 src/。
    """
    # 优先使用 runtime 内嵌的 src（随 runtime.7z 分发）
    runtime_src = base_dir / RUNTIME_DIR_NAME / "src"
    if runtime_src.is_dir():
        src_dir = runtime_src
        entry_script = base_dir / RUNTIME_DIR_NAME / APP_ENTRY
    else:
        src_dir = base_dir / "src"
        entry_script = base_dir / APP_ENTRY

    # 如果 entry_script 不存在，尝试查找替代入口
    if not entry_script.is_file():
        # 尝试从 runtime 内部启动
        alt_entry = base_dir / RUNTIME_DIR_NAME / "scripts" / "run_pywebview.py"
        if alt_entry.is_file():
            entry_script = alt_entry

    env = os.environ.copy()
    # 将项目 src 目录加入 PYTHONPATH
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
# GUI Progress Dialog (tkinter, 内置于 Python 标准库)
# ---------------------------------------------------------------------------

class ProgressDialog:
    """简易进度窗口，用于显示解压/下载进度.

    如果 tkinter 不可用，回退到命令行进度显示。
    """

    def __init__(self, title: str):
        self._tk = False
        if _HAS_TKINTER:
            try:
                self.root = Tk()
                self.root.title(title)
                self.root.geometry("400x120")
                self.root.resizable(False, False)
                self.root.attributes("-topmost", True)

                # 居中
                self.root.update_idletasks()
                x = (self.root.winfo_screenwidth() // 2) - (400 // 2)
                y = (self.root.winfo_screenheight() // 2) - (120 // 2)
                self.root.geometry(f"+{x}+{y}")

                self.label = ttk.Label(self.root, text="Preparing runtime...", font=("Microsoft YaHei", 11))
                self.label.pack(pady=(15, 5))

                self.progress = ttk.Progressbar(self.root, length=360, mode="determinate")
                self.progress.pack(pady=5)

                self.root.protocol("WM_DELETE_WINDOW", lambda: None)  # 禁止关闭
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
            print(f"[Launcher] {percent}% — {message}")

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

    # 静默模式：若 runtime 已就绪，不显示任何 UI 直接启动
    if check_runtime_exists(base_dir):
        python_exe = base_dir / RUNTIME_DIR_NAME / PYTHON_REL_PATH
        return launch_app(python_exe, base_dir)

    # 需要解压或下载，显示进度窗口
    dialog = ProgressDialog(f"{APP_NAME} — First Run Setup")
    dialog.update(0, "Checking runtime environment...")
    dialog.root.update()

    def _progress(percent: int, msg: str):
        dialog.update(percent, msg)
        dialog.root.update()

    python_exe = ensure_runtime(base_dir, _progress)

    dialog.close()

    if python_exe is None:
        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            "无法准备运行环境。请检查网络连接，或联系技术支持。\n\n"
            "Failed to prepare runtime environment. Please check your network connection.",
            f"{APP_NAME} Error",
            0x10,  # MB_ICONERROR
        )
        return 1

    return launch_app(python_exe, base_dir)


if __name__ == "__main__":
    sys.exit(main())
