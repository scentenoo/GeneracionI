# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# El calendario de cierre (tkcalendar) usa babel para los nombres de meses
# en español, y babel trae sus datos de locale en archivos que PyInstaller
# no detecta solo. collect_all los junta (datos + submódulos ocultos).
datas = [('../templates', 'templates')]
binaries = []
hiddenimports = ['babel.numbers']
for _paquete in ('tkcalendar', 'babel'):
    _d, _b, _h = collect_all(_paquete)
    datas += _d
    binaries += _b
    hiddenimports += _h


a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='GeneracionI-Planeaciones',
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
    icon='assets/icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeneracionI-Planeaciones',
)
