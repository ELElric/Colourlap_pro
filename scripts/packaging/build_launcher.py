"""Build Launcher EXE — 使用 PyInstaller 将 launcher.py 打包为独立可执行文件.

输出:
    dist/ColorLabPro.exe — 启动器（约 5-10MB，不含 Python 运行时）

用法:
    python scripts/packaging/build_launcher.py

前置条件:
    pip install pyinstaller
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
    """使用 PyInstaller 打包 launcher.py."""
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
        "--onefile",  # 单文件模式
        "--windowed",  # Windows 子系统（不显示控制台窗口）
        "--name", OUTPUT_NAME,
        "--distpath", str(DIST_DIR),
        "--workpath", str(build_dir),
        "--specpath", str(PROJECT_ROOT),
        "--clean",  # 清理缓存
        "--noconfirm",
    ]

    # 如果有图标则添加
    if ICON_PATH.is_file():
        cmd.extend(["--icon", str(ICON_PATH)])

    # 添加 hidden imports（tkinter 相关）
    cmd.extend([
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
    ])

    cmd.append(str(LAUNCHER_SCRIPT))

    print(f"[BuildLauncher] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    exe_path = DIST_DIR / f"{OUTPUT_NAME}.exe"
    if not exe_path.is_file():
        raise RuntimeError(f"Build failed: {exe_path} not found")

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[BuildLauncher] Created: {exe_path} ({size_mb:.1f} MB)")
    return exe_path


def create_distribution_package(exe_path: Path):
    """创建最终分发包目录，包含 exe 和 runtime.7z."""
    package_dir = DIST_DIR / f"{OUTPUT_NAME}-v1.1.0-Windows"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    # 复制 exe
    shutil.copy2(exe_path, package_dir / exe_path.name)

    # 复制 runtime.7z（如果存在）
    runtime_archive = DIST_DIR / "runtime.7z"
    if runtime_archive.is_file():
        shutil.copy2(runtime_archive, package_dir / runtime_archive.name)
        archive_size = runtime_archive.stat().st_size / (1024 * 1024)
        print(f"[BuildLauncher] Included runtime.7z ({archive_size:.1f} MB)")
    else:
        print("[BuildLauncher] Warning: runtime.7z not found in dist/")
        print("[BuildLauncher] Run build_runtime.py first to include runtime.")

    # 创建 README
    readme = package_dir / "README.txt"
    readme.write_text(
        f"""ColorLab Pro v1.1.0
===================

启动方式:
1. 双击 ColorLabPro.exe 直接运行
2. 首次运行会自动解压 runtime.7z（约需 30 秒）
3. 后续启动将直接使用已解压的运行时，无需等待

文件说明:
- ColorLabPro.exe : 启动器（约 {exe_path.stat().st_size / (1024 * 1024):.1f} MB）
- runtime.7z      : Python 运行时 + 依赖（约 {runtime_archive.stat().st_size / (1024 * 1024):.1f} MB）

注意:
- 首次运行时需要解压 runtime.7z，请耐心等待
- 如果删除了 runtime/ 文件夹，下次启动会自动重新解压
- 如果没有 runtime.7z，启动器会尝试从网络下载

系统要求:
- Windows 10/11 64-bit
- WebView2 Runtime（Windows 11 已内置，Windows 10 需安装）
""",
        encoding="utf-8",
    )

    print(f"[BuildLauncher] Distribution package: {package_dir}")
    return package_dir


def main() -> int:
    """构建启动器 EXE."""
    print("=" * 60)
    print("ColorLab Pro Launcher Builder")
    print("=" * 60)

    if not check_pyinstaller():
        print("[BuildLauncher] PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    print("\n[Step 1/3] Building EXE with PyInstaller...")
    exe_path = build_exe()

    print("\n[Step 2/3] Creating distribution package...")
    package_dir = create_distribution_package(exe_path)

    print("\n[Step 3/3] Done!")
    print(f"[BuildLauncher] Output: {package_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
