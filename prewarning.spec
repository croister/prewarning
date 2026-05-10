# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['prewarning.py'],
    pathex=[],
    binaries=[],
    datas=[('punchsources', 'punchsources'), ('startlistsources', 'startlistsources'), ('sounds', 'sounds'), ('utils', 'utils'), ('mpg123', 'mpg123'), ('validators', 'validators'), ('config', 'config'), ('logs', 'logs'), ('favicon.ico', '.')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='prewarning',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['favicon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='prewarning',
)
