# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# --- パス自動解決 ---
SPEC_DIR = os.path.abspath(SPECPATH)
ROOT_DIR = os.path.abspath(os.path.join(SPEC_DIR, '..'))
MAIN_SCRIPT = os.path.join(ROOT_DIR, 'utau_volume_normalizer.py')

# --- 実行プラットフォームの自動判別 ---
IS_WINDOWS = sys.platform.startswith('win')
IS_MAC = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

# --- 追加データの指定 (Languages フォルダを埋め込み) ---
LANGUAGES_DIR = os.path.join(ROOT_DIR, 'Languages')
added_datas = []
if os.path.exists(LANGUAGES_DIR):
    # (元パス, 埋め込み先の相対パス)
    added_datas.append((LANGUAGES_DIR, 'Languages'))

# --- 隠しインポート (Hidden Imports) ---
base_hiddenimports = [
    'importlib.resources',
    'scipy.special.cython_special',
    'scipy.stats._sobol',
    'scipy.signal',
    'scipy.io.wavfile',
    
    # --- Cython(.pyd) 化対策 ---
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',

    # --- librosa 対策 ---
    'librosa',
    'librosa.core',
    'librosa.feature',
    'librosa.filters',
    'librosa.util',
    'librosa.onset',
    'librosa.segment',
    'librosa.sequence',
    'librosa.decompose',
    'librosa.effects',
    'sklearn.utils._weight_vector',

    # --- pyrubberband 対策 ---
    'pyrubberband',
    'pyrubberband.pyrubberband',
]

platform_hiddenimports = []
if IS_WINDOWS:
    platform_hiddenimports.extend([
        'win32ctypes',
    ])

hiddenimports = base_hiddenimports + platform_hiddenimports

# --- OSごとの実行ファイル名設定 ---
app_name = 'utau_volume_normalizer'
exe_name = f'{app_name}.exe' if IS_WINDOWS else app_name

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=added_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# --- EXE 定義 ---
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True if IS_WINDOWS else False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='libraries',  # _internal フォルダを libraries に変更
)

# --- フォルダ（--onedir）ビルド定義 ---
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True if IS_WINDOWS else False,
    upx_exclude=[],
    name=app_name,
)

# --- macOS専用: .app バンドル化処理 ---
if IS_MAC:
    app = BUNDLE(
        coll,
        name=f'{app_name}.app',
        icon=None,
        bundle_identifier=f'com.utau.{app_name}',
    )
