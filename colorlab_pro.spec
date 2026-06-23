# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ColorLab Pro.

Build a one-folder Windows distribution:

    pip install pyinstaller
    pyinstaller colorlab_pro.spec

The output is placed under ``dist/ColorLabPro/``.  The main executable is
``dist/ColorLabPro/ColorLabPro.exe``.

Notes
-----
* ``colour-science`` ships data files (CMFs, illuminants) that must be
  collected with ``collect_data_files``.
* ``shapely`` depends on the GEOS shared library; ``collect_dynamic_libs``
  ensures the DLL is bundled.
* PySide6 plugins (platforms, styles, image formats) are pulled in via
  ``collect_submodules`` + ``collect_data_files``.
* The application is built windowed (no console) for end-user distribution.
"""

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

block_cipher = None

hiddenimports = []
hiddenimports += collect_submodules("colour")
hiddenimports += collect_submodules("PySide6")
hiddenimports += collect_submodules("shapely")

datas = []
datas += collect_data_files("colour")
datas += collect_data_files("PySide6")
datas += collect_data_files("colorlab_pro", include_py_files=False)

binaries = []
binaries += collect_dynamic_libs("shapely")
binaries += collect_dynamic_libs("scipy")
binaries += collect_dynamic_libs("numpy")

a = Analysis(
    ["scripts/run_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
        "pytest",
        "mypy",
        "ruff",
        "IPython",
        "matplotlib.tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ColorLabPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed mode — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # set to "src/colorlab_pro/ui/resources/icon.ico" when available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ColorLabPro",
)
