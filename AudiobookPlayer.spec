# -*- mode: python ; coding: utf-8 -*-
# Wspólny spec dla Windows i Linuksa (Linux: `pyinstaller --noconfirm AudiobookPlayer.spec`).
# Na Windows buduje się skryptem build_exe.ps1 (CLI z --specpath build, żeby ten plik
# nie został nadpisany).
import sys

ICON = 'src/icon.ico' if sys.platform == 'win32' else 'src/icon.png'

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    # ikona okna + teksty licencji pokazywane w Pomoc -> Licencje i uznania
    datas=[(ICON, '.'), ('LICENSE', '.'), ('THIRD_PARTY_NOTICES.md', '.')],
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
    a.binaries,
    a.datas,
    [],
    name='AudiobookPlayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX zwiększa liczbę fałszywych alarmów antywirusów
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICON],
)
