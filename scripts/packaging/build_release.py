"""Build Release — 一键打包发布 ColorLab Pro.

输出两个独立文件到 dist/:
  1. ColorLabPro.exe — 程序包（含源码，不含依赖，约 10-15MB）
  2. runtime.7z      — 依赖包（Python embed + 所有 pip 依赖，约 200-300MB）

分发方式:
  - 程序包: ColorLabPro.exe 直接发送给用户
  - 依赖包: runtime.7z 上传到 GitHub Release 作为 asset
  - 用户首次运行 ColorLabPro.exe 时:
    a. 先查找本地 runtime.7z（与 EXE 同目录）
    b. 若无，从 GitHub Release 下载 runtime.7z
    c. 若 GitHub 也不可用，在线从 PyPI 镜像安装

用法:
    python scripts/packaging/build_release.py [--skip-runtime] [--skip-launcher]

    --skip-runtime   跳过构建 runtime.7z（只构建 EXE）
    --skip-launcher  跳过构建 EXE（只构建 runtime.7z）

前置:
    pip install pyinstaller py7zr
    或安装 7-Zip (https://7-zip.org)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = PROJECT_ROOT / "dist"

LAUNCHER_SCRIPT = PROJECT_ROOT / "scripts" / "packaging" / "build_launcher.py"
RUNTIME_SCRIPT = PROJECT_ROOT / "scripts" / "packaging" / "build_runtime.py"


def _print_header(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _check_file(path: Path, label: str) -> bool:
    if path.is_file():
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"  [OK] {label}: {path.name} ({size_mb:.1f} MB)")
        return True
    print(f"  [FAIL] {label}: {path} not found")
    return False


def build_launcher() -> bool:
    """构建程序包 ColorLabPro.exe."""
    _print_header("Step 1/2: Building Program Package (ColorLabPro.exe)")
    if not LAUNCHER_SCRIPT.is_file():
        print(f"  [ERROR] Build script not found: {LAUNCHER_SCRIPT}")
        return False

    print(f"  Running: {LAUNCHER_SCRIPT.name}")
    result = subprocess.run(
        [sys.executable, str(LAUNCHER_SCRIPT)],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print("  [ERROR] Launcher build failed")
        return False

    return _check_file(DIST_DIR / "ColorLabPro.exe", "Program package")


def build_runtime() -> bool:
    """构建依赖包 runtime.7z."""
    _print_header("Step 2/2: Building Dependency Package (runtime.7z)")
    if not RUNTIME_SCRIPT.is_file():
        print(f"  [ERROR] Build script not found: {RUNTIME_SCRIPT}")
        return False

    print(f"  Running: {RUNTIME_SCRIPT.name}")
    result = subprocess.run(
        [sys.executable, str(RUNTIME_SCRIPT)],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print("  [ERROR] Runtime build failed")
        return False

    return _check_file(DIST_DIR / "runtime.7z", "Dependency package")


def print_summary(launcher_ok: bool, runtime_ok: bool) -> None:
    """打印发布摘要."""
    _print_header("Build Summary")
    print()
    if launcher_ok:
        exe_path = DIST_DIR / "ColorLabPro.exe"
        size = exe_path.stat().st_size / (1024 * 1024)
        print(f"  Program:   {exe_path} ({size:.1f} MB)")
    else:
        print("  Program:   NOT BUILT")

    if runtime_ok:
        rt_path = DIST_DIR / "runtime.7z"
        size = rt_path.stat().st_size / (1024 * 1024)
        print(f"  Runtime:   {rt_path} ({size:.1f} MB)")
    else:
        print("  Runtime:   NOT BUILT")

    print()
    print("  Distribution guide:")
    print("    1. Share ColorLabPro.exe with users (small, ~10-15MB)")
    print("    2. Upload runtime.7z to GitHub Release as an asset")
    print("    3. Users run ColorLabPro.exe:")
    print("       a. Checks local runtime.7z (same folder as EXE)")
    print("       b. Downloads runtime.7z from GitHub Release")
    print("       c. Falls back to online PyPI mirror install")
    print()
    print("  GitHub Release upload:")
    print("    gh release create v1.x.x dist/ColorLabPro.exe dist/runtime.7z")
    print("    Or upload manually at:")
    print("    https://github.com/ELElric/Colourlap_pro/releases/new")


def main() -> int:
    args = sys.argv[1:]
    skip_runtime = "--skip-runtime" in args
    skip_launcher = "--skip-launcher" in args

    start_time = time.time()

    _print_header("ColorLab Pro Release Builder")
    print(f"  Output directory: {DIST_DIR}")
    print(f"  Skip runtime:  {skip_runtime}")
    print(f"  Skip launcher: {skip_launcher}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    launcher_ok = False
    runtime_ok = False

    if not skip_launcher:
        launcher_ok = build_launcher()
    else:
        print("\n  [SKIP] Launcher build skipped")

    if not skip_runtime:
        runtime_ok = build_runtime()
    else:
        print("\n  [SKIP] Runtime build skipped")

    elapsed = time.time() - start_time
    print(f"\n  Total time: {elapsed:.0f}s")

    print_summary(launcher_ok, runtime_ok)

    # Exit code: 0 if all requested builds succeeded
    success = True
    if not skip_launcher and not launcher_ok:
        success = False
    if not skip_runtime and not runtime_ok:
        success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
