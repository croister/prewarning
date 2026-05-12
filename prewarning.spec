# -*- mode: python ; coding: utf-8 -*-

import importlib.metadata
import platform
import os
from PyInstaller.utils.hooks import copy_metadata


IS_WINDOWS = platform.system() == 'Windows'
IS_MACOS = platform.system() == 'Darwin'

datas = [
    ('punchsources', 'punchsources'),
    ('startlistsources', 'startlistsources'),
    ('sounds', 'sounds'),
    ('utils', 'utils'),
    ('validators', 'validators'),
    ('config', 'config'),
    ('logs', 'logs'),
    ('favicon.ico', '.'),
]

datas += copy_metadata('prewarning')
for req in (importlib.metadata.requires('prewarning') or []):
    name = req.split(';')[0].split('==')[0].split('>=')[0].split('~=')[0].split('!=')[0].strip()
    try:
        datas += copy_metadata(name)
    except Exception:
        pass

if IS_WINDOWS:
    datas.append(('mpg123', 'mpg123'))

icon = None
if IS_WINDOWS and os.path.exists('favicon.ico'):
    icon = 'favicon.ico'
elif IS_MACOS and os.path.exists('favicon.icns'):
    icon = 'favicon.icns'

a = Analysis(
    ['prewarning.py'],
    pathex=[],
    binaries=[],
    datas=datas,
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
    icon=icon,
)

if IS_MACOS:
    app = BUNDLE(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        name='prewarning.app',
        icon=icon,
        bundle_identifier='com.prewarning.app',
    )
else:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='prewarning',
    )
