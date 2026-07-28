"""Build runtime.7z — 打包 Python 嵌入版 + 所有依赖为离线安装包.

用法: python scripts/packaging/build_runtime.py
前置: pip install py7zr 或安装 7-Zip

输出:
    dist/runtime.7z — 离线依赖包（Python embed + 所有 pip 依赖）
    分发方式: 上传到 GitHub Release 作为 asset，launcher 自动下载
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUNTIME_DIR = PROJECT_ROOT / "build_runtime"
DIST_DIR = PROJECT_ROOT / "dist"
OUTPUT_ARCHIVE = DIST_DIR / "runtime.7z"

TARGET_PY = "3.11"

# 自动检测当前设备架构
def _detect_arch() -> str:
    """检测 CPU 架构，返回 python-embed 后缀."""
    machine = platform.machine().lower()
    if "arm" in machine or "aarch64" in machine:
        return "arm64"
    return "amd64"

ARCH = _detect_arch()
EMBED_URL = f"https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-{ARCH}.zip"

DEPS = [
    "numpy>=1.26,<2.3",
    "colour-science>=0.4.4,<0.5",
    "SQLAlchemy>=2.0,<2.1",
    "shapely>=2.0,<2.2",
    "loguru>=0.7,<0.8",
    "scipy>=1.11,<1.18",
    "openpyxl>=3.1,<3.2",
    "pyyaml>=6.0,<6.1",
    "matplotlib>=3.7,<3.12",
    "pywebview>=5.0",
]


def main():
    print("=" * 50)
    print(f"Building runtime.7z (arch={ARCH})")
    print("=" * 50)

    runtime_dir = PROJECT_ROOT / "build_runtime"
    if runtime_dir.exists():
        try:
            shutil.rmtree(runtime_dir)
        except PermissionError:
            print(f"WARNING: Cannot remove {runtime_dir} (file in use), using build_runtime2")
            runtime_dir = PROJECT_ROOT / "build_runtime2"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(exist_ok=True)

    # 1. 下载 python-embed
    import urllib.request, tempfile, zipfile
    tmp_dir = Path(tempfile.mktemp())
    tmp_dir.mkdir()
    embed_zip = tmp_dir / "embed.zip"

    print(f"\n[1/5] Downloading python-embed from {EMBED_URL}")
    urllib.request.urlretrieve(EMBED_URL, embed_zip)
    with zipfile.ZipFile(embed_zip) as zf:
        zf.extractall(runtime_dir)
    shutil.rmtree(tmp_dir)
    print(f"   Extracted to {runtime_dir}")

    # 2. 配置 ._pth
    print("[2/5] Configuring ._pth")
    for pth in runtime_dir.glob("python*._pth"):
        content = pth.read_text("utf-8")
        content = content.replace("#import site", "import site")
        if "Lib/site-packages" not in content:
            content += "\nLib/site-packages\n"
        pth.write_text(content, "utf-8")
    (runtime_dir / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)

    # 3. 安装 pip
    print("[3/5] Installing pip")
    get_pip = runtime_dir / "get-pip.py"
    urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip)
    python_exe = runtime_dir / "python.exe"
    subprocess.run([str(python_exe), str(get_pip), "-q"], check=True, capture_output=True)
    get_pip.unlink()

    # 4. 安装依赖
    print("[4/5] Installing dependencies...")
    # 使用国内镜像加速
    mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
    trusted = "pypi.tuna.tsinghua.edu.cn"
    site_pkgs = runtime_dir / "Lib" / "site-packages"
    for i, dep in enumerate(DEPS):
        print(f"   [{i+1}/{len(DEPS)}] Installing {dep}...")
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "install",
             "--target", str(site_pkgs),
             "--index-url", mirror,
             "--trusted-host", trusted,
             "--no-cache-dir", "-q", dep],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            print(f"   WARNING: {dep} failed: {result.stderr[:200]}")
        else:
            print(f"   OK: {dep}")

    # 5. 清理 + 打包
    print("[5/5] Creating runtime.7z")
    # 清理缓存
    for p in list(site_pkgs.glob("**/__pycache__")):
        shutil.rmtree(p, ignore_errors=True)
    for p in list(site_pkgs.glob("**/*.pyc")):
        p.unlink()

    if OUTPUT_ARCHIVE.exists():
        OUTPUT_ARCHIVE.unlink()

    # 尝试 7z
    seven_z = Path(r"C:\Program Files\7-Zip\7z.exe")
    if not seven_z.is_file():
        seven_z = Path(r"C:\Program Files (x86)\7-Zip\7z.exe")

    if seven_z.is_file():
        subprocess.run([
            str(seven_z), "a", "-t7z", "-m0=lzma2", "-mx=7",
            str(OUTPUT_ARCHIVE), f"{runtime_dir}\\*"
        ], check=True, cwd=PROJECT_ROOT)
    else:
        try:
            import py7zr
            with py7zr.SevenZipFile(OUTPUT_ARCHIVE, "w") as sz:
                sz.writeall(runtime_dir, arcname="runtime")
        except ImportError:
            print("ERROR: Neither 7-Zip nor py7zr found. Install one of them.")
            print("  pip install py7zr")
            print("  Or install 7-Zip from https://7-zip.org")
            return 1

    size_mb = OUTPUT_ARCHIVE.stat().st_size / (1024 * 1024)
    print(f"\nDone! {OUTPUT_ARCHIVE} ({size_mb:.1f} MB)")

    # Cleanup
    shutil.rmtree(runtime_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
