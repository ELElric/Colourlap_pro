"""Build All — 一键构建完整分发包.

执行全部构建流程:
1. build_runtime.py  — 构建 Python 运行时包 (runtime.7z)
2. build_launcher.py — 打包启动器 (ColorLabPro.exe)
3. 组装最终分发包

用法:
    python scripts/packaging/build_all.py [--skip-runtime] [--skip-launcher]

选项:
    --skip-runtime   跳过运行时构建（如果已有 runtime.7z）
    --skip-launcher  跳过启动器构建（如果已有 exe）
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGING_DIR = PROJECT_ROOT / "scripts" / "packaging"
DIST_DIR = PROJECT_ROOT / "dist"


def run_script(script_name: str) -> bool:
    """运行指定的构建脚本."""
    script_path = PACKAGING_DIR / script_name
    if not script_path.is_file():
        print(f"[BuildAll] Script not found: {script_path}")
        return False

    print(f"\n{'=' * 60}")
    print(f"[BuildAll] Running {script_name}")
    print("=" * 60)

    result = subprocess.run([sys.executable, str(script_path)])
    return result.returncode == 0


def create_final_package():
    """创建最终 ZIP 分发包（可选）."""
    import shutil

    package_dir = DIST_DIR / "ColorLabPro-v1.1.0-Windows"
    if not package_dir.is_dir():
        print("[BuildAll] Package directory not found, skipping ZIP creation")
        return None

    # 创建 ZIP
    zip_path = DIST_DIR / f"{package_dir.name}"
    shutil.make_archive(str(zip_path), "zip", package_dir)

    zip_file = Path(str(zip_path) + ".zip")
    size_mb = zip_file.stat().st_size / (1024 * 1024)
    print(f"[BuildAll] Created ZIP: {zip_file} ({size_mb:.1f} MB)")
    return zip_file


def print_summary():
    """打印构建摘要."""
    print("\n" + "=" * 60)
    print("Build Summary")
    print("=" * 60)

    files_to_check = [
        ("Launcher EXE", DIST_DIR / "ColorLabPro.exe"),
        ("Runtime Archive", DIST_DIR / "runtime.7z"),
        ("Distribution Package", DIST_DIR / "ColorLabPro-v1.1.0-Windows"),
        ("ZIP Archive", DIST_DIR / "ColorLabPro-v1.1.0-Windows.zip"),
    ]

    total_size = 0
    for name, path in files_to_check:
        if path.is_file():
            size_mb = path.stat().st_size / (1024 * 1024)
            total_size += size_mb
            print(f"  ✓ {name:20s} : {path.name:40s} ({size_mb:6.1f} MB)")
        elif path.is_dir():
            dir_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            size_mb = dir_size / (1024 * 1024)
            total_size += size_mb
            print(f"  ✓ {name:20s} : {path.name:40s} ({size_mb:6.1f} MB)")
        else:
            print(f"  ✗ {name:20s} : {'Not found':40s}")

    print(f"\n  Total size: {total_size:.1f} MB")
    print("=" * 60)


def main() -> int:
    """一键构建入口."""
    parser = argparse.ArgumentParser(description="Build ColorLab Pro distribution package")
    parser.add_argument("--skip-runtime", action="store_true", help="Skip building runtime.7z")
    parser.add_argument("--skip-launcher", action="store_true", help="Skip building launcher EXE")
    parser.add_argument("--no-zip", action="store_true", help="Skip creating final ZIP archive")
    args = parser.parse_args()

    print("=" * 60)
    print("ColorLab Pro — Full Build")
    print("=" * 60)

    success = True

    # Step 1: Build Runtime
    if not args.skip_runtime:
        if not run_script("build_runtime.py"):
            print("[BuildAll] Runtime build failed!")
            success = False
    else:
        print("[BuildAll] Skipping runtime build ( --skip-runtime )")

    # Step 2: Build Launcher
    if success and not args.skip_launcher:
        if not run_script("build_launcher.py"):
            print("[BuildAll] Launcher build failed!")
            success = False
    else:
        print("[BuildAll] Skipping launcher build ( --skip-launcher )")

    # Step 3: Create ZIP
    if success and not args.no_zip:
        create_final_package()

    # Summary
    print_summary()

    if success:
        print("\n✓ Build completed successfully!")
        print(f"  Distribution folder: {DIST_DIR / 'ColorLabPro-v1.1.0-Windows'}")
    else:
        print("\n✗ Build failed. Check logs above.")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
