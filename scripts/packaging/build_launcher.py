"""Build Launcher EXE — 使用 PyInstaller 打包最小化启动器.

输出:
    dist/ColorLabPro.exe — 启动器（约 10MB，含 Python 标准库 + 项目源码）

打包内容:
- launcher.py（启动器逻辑）
- src/（项目源码，作为数据文件打包）
- scripts/run_pywebview.py（入口脚本）

不含:
- 第三方依赖（运行时从 PyPI 镜像在线安装）

用法:
    python scripts/packaging/build_launcher.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LAUNCHER_SCRIPT = PROJECT_ROOT / "scripts" / "packaging" / "launcher.py"
DIST_DIR = PROJECT_ROOT / "dist"
OUTPUT_NAME = "ColorLabPro"
ICON_PATH = PROJECT_ROOT / "src" / "colorlab_pro" / "resources" / "icon.ico"


def check_pyinstaller() -> bool:
    """检查 PyInstaller 是否已安装."""
    try:
        import PyInstaller  # type: ignore[import-untyped]
        return True
    except ImportError:
        return False


def build_exe() -> Path:
    """使用 PyInstaller 打包 launcher.py + 项目源码."""
    if not LAUNCHER_SCRIPT.is_file():
        raise FileNotFoundError(f"Launcher script not found: {LAUNCHER_SCRIPT}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 清理旧的构建目录
    build_dir = PROJECT_ROOT / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # PyInstaller 参数
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", OUTPUT_NAME,
        "--distpath", str(DIST_DIR),
        "--workpath", str(build_dir),
        "--specpath", str(PROJECT_ROOT),
        "--clean",
        "--noconfirm",
    ]

    # 图标
    if ICON_PATH.is_file():
        cmd.extend(["--icon", str(ICON_PATH)])

    # hidden imports
    cmd.extend([
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
    ])

    # 打包项目源码作为数据文件
    # src/ -> _MEIPASS/src/
    src_dir = PROJECT_ROOT / "src"
    if src_dir.is_dir():
        cmd.extend(["--add-data", f"{src_dir};src"])
        print(f"[Build] Including src/ from {src_dir}")

    # scripts/run_pywebview.py -> _MEIPASS/scripts/run_pywebview.py
    scripts_dir = PROJECT_ROOT / "scripts"
    if scripts_dir.is_dir():
        # 只打包必要的脚本
        cmd.extend(["--add-data", f"{scripts_dir / 'run_pywebview.py'};scripts"])
        init_db = scripts_dir / "init_db.py"
        if init_db.is_file():
            cmd.extend(["--add-data", f"{init_db};scripts"])
        print(f"[Build] Including scripts/")

    cmd.append(str(LAUNCHER_SCRIPT))

    print(f"[Build] Running PyInstaller...")
    print(f"[Build] Command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    exe_path = DIST_DIR / f"{OUTPUT_NAME}.exe"
    if not exe_path.is_file():
        raise RuntimeError(f"Build failed: {exe_path} not found")

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[Build] Created: {exe_path} ({size_mb:.1f} MB)")
    return exe_path


def main() -> int:
    """构建启动器 EXE."""
    print("=" * 60)
    print("ColorLab Pro Launcher Builder")
    print("=" * 60)

    if not check_pyinstaller():
        print("[Build] PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    print("\n[Step 1/2] Building EXE with PyInstaller...")
    exe_path = build_exe()

    print("\n[Step 2/2] Done!")
    print(f"[Build] Output: {exe_path}")
    print(f"[Build] Size: {exe_path.stat().st_size / (1024 * 1024):.1f} MB")
    print()
    print("Distribution: just share ColorLabPro.exe")
    print("First run will download Python + dependencies from PyPI mirror.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
