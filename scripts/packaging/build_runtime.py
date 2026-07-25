"""Build Python Runtime — 构建可移植的 Python + 依赖包.

执行步骤:
1. 创建虚拟环境（或使用已有的）
2. 安装项目全部依赖（含 pywebview）
3. 复制项目源码到 runtime/src/
4. 打包整个 runtime 目录为 runtime.7z

输出:
    dist/runtime.7z — 自解压/可直接解压的运行时包
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DIST_DIR = PROJECT_ROOT / "dist"
OUTPUT_ARCHIVE = DIST_DIR / "runtime.7z"

# 额外需要但不在 pyproject.toml 的依赖
EXTRA_DEPS = ["pywebview", "py7zr"]


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True):
    """运行命令并打印."""
    print(f"[Build] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=check)


def get_python_version() -> str:
    """获取当前 Python 版本（如 3.11）."""
    v = sys.version_info
    return f"{v.major}.{v.minor}"


def create_runtime_structure() -> Path:
    """创建运行时目录结构.

    复制当前 Python 安装到 runtime/ 目录（仅站点包，不复制标准库）。
    更简单的做法：直接使用虚拟环境。
    """
    if RUNTIME_DIR.exists():
        print(f"[Build] Removing old runtime dir: {RUNTIME_DIR}")
        shutil.rmtree(RUNTIME_DIR)

    RUNTIME_DIR.mkdir(parents=True)

    # 使用当前 Python 的可执行文件路径
    python_exe = Path(sys.executable)
    python_root = python_exe.parent.parent  # e.g. C:\Python311

    print(f"[Build] Python root: {python_root}")
    print(f"[Build] Python exe: {python_exe}")

    # 复制核心文件和目录
    core_items = ["python.exe", "pythonw.exe", "DLLs", "Lib"]
    for item in core_items:
        src = python_root / item
        dst = RUNTIME_DIR / item
        if src.is_file():
            shutil.copy2(src, dst)
            print(f"[Build] Copied file: {item}")
        elif src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            print(f"[Build] Copied dir: {item}")
        else:
            print(f"[Build] Warning: {item} not found at {src}")

    # 复制所有 DLL 文件（python3x.dll, vcruntime 等）
    for dll in python_root.glob("*.dll"):
        shutil.copy2(dll, RUNTIME_DIR / dll.name)
        print(f"[Build] Copied DLL: {dll.name}")

    # 复制其他必要文件
    for extra in ["python3.dll", "python310.dll", "python311.dll", "python312.dll"]:
        src = python_root / extra
        if src.is_file() and not (RUNTIME_DIR / extra).exists():
            shutil.copy2(src, RUNTIME_DIR / extra)
            print(f"[Build] Copied: {extra}")

    # 创建 site-packages 目录
    site_packages = RUNTIME_DIR / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    return RUNTIME_DIR


def install_dependencies(target_dir: Path):
    """安装项目依赖到目标运行时目录.

    使用 pip install --target 将所有依赖安装到 runtime/Lib/site-packages。
    """
    site_packages = target_dir / "Lib" / "site-packages"
    pyproject = PYPROJECT

    # 先升级 pip
    run_cmd([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

    # 从 pyproject.toml 安装依赖
    # 使用 pip install . --target 方式
    # 但由于 pyproject.toml 依赖解析较复杂，我们分步安装

    deps = [
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
        "py7zr",
        "PySide6>=6.6,<6.13",  # MainController 依赖 QObject/Signal
    ]

    print(f"[Build] Installing dependencies to {site_packages}...")

    # 分批次安装避免单次命令过长
    batch_size = 4
    for i in range(0, len(deps), batch_size):
        batch = deps[i : i + batch_size]
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(site_packages),
            "--no-deps",  # 先不装依赖，避免冲突
            *batch,
        ]
        try:
            run_cmd(cmd, check=False)
        except Exception as exc:
            print(f"[Build] Warning: batch install failed: {exc}")

    # 再次安装，允许解析依赖
    print("[Build] Resolving transitive dependencies...")
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(site_packages),
        *deps,
    ]
    run_cmd(cmd, check=False)

    # 安装项目本身（editable 模式无法用于打包，使用 pip install .）
    print("[Build] Installing colorlab-pro package...")
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(site_packages),
        "--no-deps",
        str(PROJECT_ROOT),
    ]
    run_cmd(cmd, check=False)


def copy_project_source():
    """复制项目源码到 runtime/src/ 以便 launcher 直接使用 PYTHONPATH."""
    src_dir = RUNTIME_DIR / "src"
    if src_dir.exists():
        shutil.rmtree(src_dir)

    project_src = PROJECT_ROOT / "src"
    if project_src.exists():
        shutil.copytree(project_src, src_dir)
        print(f"[Build] Copied project src -> {src_dir}")

    # 同时复制 scripts 目录（启动器需要 run_pywebview.py）
    scripts_dir = RUNTIME_DIR / "scripts"
    if scripts_dir.exists():
        shutil.rmtree(scripts_dir)
    project_scripts = PROJECT_ROOT / "scripts"
    if project_scripts.exists():
        # 只复制必要的脚本
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for script in ["run_pywebview.py", "init_db.py"]:
            src = project_scripts / script
            if src.exists():
                shutil.copy2(src, scripts_dir / script)
        print(f"[Build] Copied scripts -> {scripts_dir}")

    # 复制 pyproject.toml（用于版本信息）
    shutil.copy2(PYPROJECT, RUNTIME_DIR / "pyproject.toml")
    print("[Build] Copied pyproject.toml")


def clean_unnecessary_files():
    """清理不必要的文件以减小体积."""
    patterns_to_remove = [
        "**/*.pyc",
        "**/__pycache__",
        "**/*.pyi",
        "**/*.pxd",
        "**/tests",
        "**/test",
        "**/docs",
        "**/doc",
        "**/examples",
        "**/demo",
        "**/.git",
        "**/*.egg-info",
    ]

    removed = 0
    for pattern in patterns_to_remove:
        for path in RUNTIME_DIR.rglob(pattern):
            if path.is_file():
                path.unlink()
                removed += 1
            elif path.is_dir() and pattern.endswith("__pycache__"):
                shutil.rmtree(path, ignore_errors=True)
                removed += 1

    print(f"[Build] Cleaned {removed} unnecessary files")


def create_archive() -> Path:
    """将 runtime 目录打包为 runtime.7z."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_ARCHIVE.exists():
        OUTPUT_ARCHIVE.unlink()

    # 尝试使用系统 7z
    seven_z = Path(r"C:\Program Files\7-Zip\7z.exe")
    if not seven_z.is_file():
        seven_z = Path(r"C:\Program Files (x86)\7-Zip\7z.exe")

    if seven_z.is_file():
        cmd = [
            str(seven_z),
            "a",
            "-t7z",
            "-m0=lzma2",
            "-mx=7",  # 压缩级别 7（平衡速度和体积）
            str(OUTPUT_ARCHIVE),
            f"{RUNTIME_DIR}\\*",
        ]
        run_cmd(cmd, cwd=PROJECT_ROOT)
    else:
        # 回退到 py7zr
        try:
            import py7zr  # type: ignore[import-untyped]

            with py7zr.SevenZipFile(OUTPUT_ARCHIVE, mode="w") as sz:
                sz.writeall(RUNTIME_DIR, arcname="runtime")
            print(f"[Build] Created archive with py7zr: {OUTPUT_ARCHIVE}")
        except Exception as exc:
            print(f"[Build] Failed to create archive: {exc}")
            raise

    size_mb = OUTPUT_ARCHIVE.stat().st_size / (1024 * 1024)
    print(f"[Build] Archive created: {OUTPUT_ARCHIVE} ({size_mb:.1f} MB)")
    return OUTPUT_ARCHIVE


def main() -> int:
    """构建运行时包."""
    print("=" * 60)
    print("ColorLab Pro Runtime Builder")
    print("=" * 60)

    print(f"[Build] Python: {sys.executable}")
    print(f"[Build] Version: {get_python_version()}")
    print(f"[Build] Project: {PROJECT_ROOT}")

    # 步骤 1: 创建运行时目录
    print("\n[Step 1/6] Creating runtime directory structure...")
    create_runtime_structure()

    # 步骤 2: 安装依赖
    print("\n[Step 2/6] Installing dependencies...")
    install_dependencies(RUNTIME_DIR)

    # 步骤 3: 复制项目源码
    print("\n[Step 3/6] Copying project source...")
    copy_project_source()

    # 步骤 4: 清理
    print("\n[Step 4/6] Cleaning unnecessary files...")
    clean_unnecessary_files()

    # 步骤 5: 打包
    print("\n[Step 5/6] Creating archive...")
    archive = create_archive()

    # 步骤 6: 报告
    print("\n[Step 6/6] Done!")
    runtime_size = sum(
        f.stat().st_size for f in RUNTIME_DIR.rglob("*") if f.is_file()
    )
    print(f"[Build] Runtime dir size: {runtime_size / (1024*1024):.1f} MB")
    print(f"[Build] Archive size: {archive.stat().st_size / (1024*1024):.1f} MB")
    print(f"[Build] Archive location: {archive}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
