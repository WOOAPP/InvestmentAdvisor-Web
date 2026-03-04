# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = [
    'anthropic', 'openai', 'yfinance', 'bs4', 'matplotlib', 'pandas',
    'schedule', 'fpdf', 'sqlite3', 'tkinter',
    # SSL certificates for HTTPS requests (requests/urllib3)
    'certifi',
    # Timezone data required on Windows (zoneinfo uses tzdata)
    'tzdata',
]
hiddenimports += collect_submodules('yfinance')
hiddenimports += collect_submodules('matplotlib')
hiddenimports += collect_submodules('certifi')
hiddenimports += collect_submodules('tzdata')

# Bundle tzdata zone files and certifi CA bundle as data
datas = [('modules', 'modules')]
datas += collect_data_files('tzdata')
datas += collect_data_files('certifi')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
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
    a.binaries,
    a.datas,
    [],
    name='InvestmentAdvisor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX disabled: Norton and other AV flag UPX-packed EXEs as malware
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
