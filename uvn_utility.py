# uvn_utility.py

import os
import sys
import zipfile
import shutil
import importlib.util
import numpy as np

from scipy.signal import butter, filtfilt
from Plugins.utau_volume_normalizer_plugin_decoder.utau_volume_normalizer_plugin_decoder import parse_uvn_file

# -------------------------------------------------------------------
# .uvn スクリプトで共有利用できる標準ヘルパー関数群
# -------------------------------------------------------------------
def highpass_filter(data, cutoff=80.0, sr=44100, order=5):
    """ローカット（ハイパス）フィルター"""
    nyq = 0.5 * sr
    normal_cutoff = cutoff / nyq
    if normal_cutoff >= 1.0 or normal_cutoff <= 0.0:
        return data
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    return filtfilt(b, a, data, axis=0)

def lowpass_filter(data, cutoff=12000.0, sr=44100, order=5):
    """ハイカット（ローパス）フィルター"""
    nyq = 0.5 * sr
    normal_cutoff = cutoff / nyq
    if normal_cutoff >= 1.0 or normal_cutoff <= 0.0:
        return data
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data, axis=0)

def apply_gain_db(data, gain_db=0.0):
    """dB 単位でゲインを適用"""
    gain = 10 ** (gain_db / 20.0)
    return data * gain

def clip_protection(data, threshold=0.99):
    """音割れ（クリッピング）防止"""
    return np.clip(data, -threshold, threshold)

# Standard utilities dictionary injected to .uvn scope
BUILTIN_UTILITIES = {
    "highpass_filter": highpass_filter,
    "lowpass_filter": lowpass_filter,
    "apply_gain_db": apply_gain_db,
    "clip_protection": clip_protection,
    "np": np
}

# -------------------------------------------------------------------
# Plugins & PluginsZipper フォルダのスキャン & パス・ライブラリ設定
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(BASE_DIR, "Plugins")
PLUGINS_ZIPPER_DIR = os.path.join(BASE_DIR, "PluginsZipper")

def extract_and_register_zips(plugins_root, zipper_root, log_func=print):
    """Plugins内の .zip ファイルを検索し、PluginsZipper/ 内へ解凍してパスを通す"""
    if not os.path.exists(zipper_root):
        os.makedirs(zipper_root, exist_ok=True)

    for root, dirs, files in os.walk(plugins_root):
        for file in files:
            if file.endswith(".zip"):
                zip_path = os.path.join(root, file)
                zip_name = os.path.splitext(file)[0]
                extract_target_dir = os.path.join(zipper_root, zip_name)
                
                try:
                    # 解凍先が存在しないか、空の場合のみ解凍処理を実行
                    if not os.path.exists(extract_target_dir) or not os.listdir(extract_target_dir):
                        os.makedirs(extract_target_dir, exist_ok=True)
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(extract_target_dir)
                        log_func(f"[ZIP Plugin] PluginsZipper/ への展開完了: {file} -> {zip_name}")
                except Exception as e:
                    log_func(f"⚠️ ZIPファイルの展開に失敗しました ({file}): {e}")

def init_plugins_environment(plugins_root, zipper_root, log_func=print):
    """Plugins および PluginsZipper 内を走査してパス登録とプラグイン初期化を行う"""
    uvn_parsers = []
    custom_hooks = []

    if not os.path.exists(plugins_root):
        os.makedirs(plugins_root, exist_ok=True)

    extract_and_register_zips(plugins_root, zipper_root, log_func)

    target_roots = [plugins_root]
    if os.path.exists(zipper_root):
        target_roots.append(zipper_root)

    for search_dir in target_roots:
        for root, dirs, files in os.walk(search_dir):
            if root not in sys.path:
                sys.path.insert(0, root)

            os.environ["PATH"] = root + os.path.pathsep + os.environ.get("PATH", "")

            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(root)
                except Exception:
                    pass

            for file in files:
                file_path = os.path.join(root, file)

                if file.endswith(".py") and not file.startswith("__") and file != os.path.basename(__file__):
                    module_name = os.path.splitext(file)[0]
                    try:
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)

                        # ユーティリティ登録関数の有無をチェック
                        if hasattr(mod, "register_uvn_utilities"):
                            try:
                                utilities = mod.register_uvn_utilities()
                                if isinstance(utilities, dict):
                                    BUILTIN_UTILITIES.update(utilities)
                            except Exception as e:
                                log_func(f"⚠️ ユーティリティ登録エラー {file_path}: {e}")

                        if hasattr(mod, "parse_uvn_file"):
                            uvn_parsers.append(mod.parse_uvn_file)
                        if hasattr(mod, "register_plugin"):
                            custom_hooks.append(mod.register_plugin())
                    except Exception as e:
                        log_func(f"⚠️ プラグイン読み込み失敗 {file_path}: {e}")

                elif file.endswith(".pyd"):
                    module_name = os.path.splitext(file)[0]
                    try:
                        mod = importlib.import_module(module_name)
                        if hasattr(mod, "register_plugin"):
                            custom_hooks.append(mod.register_plugin())
                            log_func(f"[PYD Plugin] 登録完了: {file}")
                    except Exception as e:
                        pass

    # デフォルトの簡易UVNパーサー（カスタムパーサーが未登録の場合のデフォルト）
    def default_uvn_parser(path):
        def uvn_hook(data, sr, filename):
            local_scope = dict(BUILTIN_UTILITIES)
            local_scope.update({"data": data, "sample_rate": sr, "filename": filename})
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            exec(code, local_scope)
            if "process_audio_hook" in local_scope and callable(local_scope["process_audio_hook"]):
                return local_scope["process_audio_hook"](data, sr, filename)
            return data, sr
        return uvn_hook

    try:
        uvn_parsers.append(parse_uvn_file)
    except Exception:
        uvn_parsers.append(default_uvn_parser)

    for search_dir in target_roots:
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.endswith(".uvn"):
                    uvn_path = os.path.join(root, file)
                    parsed_ok = False
                    for parser in uvn_parsers:
                        try:
                            hook = parser(uvn_path)
                            if hook:
                                custom_hooks.append(hook)
                                parsed_ok = True
                                log_func(f"[UVN Plugin] 読み込み成功: {file}")
                                break
                        except Exception as e:
                            log_func(f"⚠️ UVN解析エラー ({file}): {e}")
                    if not parsed_ok and len(uvn_parsers) > 1:
                        log_func(f"⚠️ UVN解析スキップ: 有効なパーサーで処理できませんでした ({file})")

    return uvn_parsers, custom_hooks

# -------------------------------------------------------------------
# 音声処理エンジン (pyrubberband -> librosa フォールバック)
# -------------------------------------------------------------------
PITCH_ENGINE = None

rubberband_exe_folder = os.path.join("Plugins", "rubberband")
rubberband_path = os.path.join(BASE_DIR, rubberband_exe_folder)

# rubberband.exe の存在チェック
has_rubberband_exe = os.path.exists(os.path.join(rubberband_path, "rubberband.exe")) or shutil.which("rubberband") is not None

if has_rubberband_exe:
    if os.path.exists(rubberband_path):
        os.environ["PATH"] = rubberband_path + os.pathsep + os.environ["PATH"]
    try:
        import pyrubberband as pyrb
        PITCH_ENGINE = "pyrubberband"
    except Exception:
        PITCH_ENGINE = None

# rubberband が無ければ librosa がインストールされているかチェック
if PITCH_ENGINE is None:
    if importlib.util.find_spec("librosa") is not None:
        PITCH_ENGINE = "librosa"
