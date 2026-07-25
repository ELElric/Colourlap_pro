# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\0000 AI code\\Colourlap_pro\\scripts\\packaging\\launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\0000 AI code\\Colourlap_pro\\src', 'src'), ('D:\\0000 AI code\\Colourlap_pro\\scripts\\run_pywebview.py', 'scripts'), ('D:\\0000 AI code\\Colourlap_pro\\scripts\\init_db.py', 'scripts')],
    hiddenimports=['tkinter', 'tkinter.ttk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ColorLabPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
