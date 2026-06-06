# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Quartz application

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('quartz.png', '.'),
        ('pyproject.toml', '.'),
    ],
    hiddenimports=[
        'openpyxl',  # Required for Excel file import/export
        'pandas',  # Required for search filtering
        'PySide6.QtCharts',  # Required for charts dialog
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Unused Qt modules (major size savings)
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebChannel',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.Qt3D',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DExtras',
        'PySide6.QtLocation',
        'PySide6.QtPositioning',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtNfc',
        'PySide6.QtBluetooth',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickTemplates2',
        'PySide6.QtQuick3D',
        'PySide6.QtQuick3DAssetUtils',
        'PySide6.QtQuick3DEffects',
        'PySide6.QtQuick3DHelpers',
        'PySide6.QtQuick3DParticles',
        'PySide6.QtQuick3DRuntimeRender',
        'PySide6.QtQuick3DUtils',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtStateMachine',
        'PySide6.QtTextToSpeech',
        'PySide6.QtDataVisualization',
        'PySide6.QtGamepad',
        'PySide6.QtHelp',
        'PySide6.QtDesigner',
        'PySide6.QtUiTools',
        'PySide6.QtXmlPatterns',
        'PySide6.QtWebSockets',
        'PySide6.QtNetworkAuth',
        'PySide6.QtPurchasing',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtWebView',
        'PySide6.QtWebViewWidgets',
        
        # Unused pandas components (if any remain)
        'pandas.tests',
        'pandas._testing',
        
        # Unused numpy components (if not needed)
        'numpy.tests',
        'numpy.f2py',
        
        # Other unused modules
        'matplotlib',  # Not used
        'IPython',  # Not used
        'jupyter',  # Not used
        'notebook',  # Not used
        'pytest',  # Testing only
        'setuptools',  # Build only
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Quartz',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression (requires UPX installed)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='quartz.png',  # Application icon
)

