# utau_volume_normalizer_plugin_decoder.py

import os
import sys
import configparser
import importlib.util
import zipfile
import ctypes
import numpy as np
from scipy.signal import butter, lfilter

# -------------------------------------------------------------------
# 1. 基本の標準組み込みユーティリティ関数群
# -------------------------------------------------------------------
def uvn_highpass_filter(data, cutoff, sr, order=5):
    """ローカット（ハイパス）フィルター"""
    if cutoff <= 0 or cutoff >= (sr / 2):
        return data
    nyq = 0.5 * sr
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    if data.ndim > 1:
        return np.vstack([lfilter(b, a, data[:, c]) for c in range(data.shape[1])]).T
    return lfilter(b, a, data)

def uvn_lowpass_filter(data, cutoff, sr, order=5):
    """ハイカット（ローパス）フィルター"""
    if cutoff <= 0 or cutoff >= (sr / 2):
        return data
    nyq = 0.5 * sr
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    if data.ndim > 1:
        return np.vstack([lfilter(b, a, data[:, c]) for c in range(data.shape[1])]).T
    return lfilter(b, a, data)

def uvn_apply_gain_db(data, gain_db):
    """ゲイン調整 (dB指定)"""
    if gain_db == 0.0:
        return data
    return data * (10 ** (gain_db / 20.0))

def uvn_clip_protection(data, threshold=1.0):
    """クリッピング（音割れ）防止"""
    return np.clip(data, -threshold, threshold)

# 基本ユーティリティ辞書
BASE_UVN_UTILITIES = {
    "highpass_filter": uvn_highpass_filter,
    "lowpass_filter": uvn_lowpass_filter,
    "apply_gain_db": uvn_apply_gain_db,
    "clip_protection": uvn_clip_protection,
}


# -------------------------------------------------------------------
# 2. Plugins/ から Pythonユーティリティプラグインを自動ロードする機構
# -------------------------------------------------------------------
def load_uvn_utility_plugins():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    plugins_dir = os.path.join(base_dir, "Plugins")
    if not os.path.exists(plugins_dir):
        plugins_dir = base_dir

    zipper_root = os.path.join(plugins_dir, "NormalizerPluginsZipper")
    os.makedirs(zipper_root, exist_ok=True)

    custom_utils = BASE_UVN_UTILITIES.copy()

    # 1. ZIPの自動解凍 (.dll, .pyd, .py, .uvn などが同梱されたZIPに対応)
    for root, _, files in os.walk(plugins_dir):
        for file in files:
            if file.endswith(".zip"):
                zip_path = os.path.join(root, file)
                zip_name = os.path.splitext(file)[0]
                extract_target = os.path.join(zipper_root, zip_name)
                try:
                    if not os.path.exists(extract_target):
                        os.makedirs(extract_target, exist_ok=True)
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(extract_target)
                        print(f"[ZIP Plugin] 展開完了: {file}")
                except Exception as e:
                    print(f"⚠️ ZIP解凍失敗 ({file}): {e}")

    target_roots = [plugins_dir, zipper_root]

    # 2. .py / .pyd / .dll / .uvn の読み込み処理
    for search_dir in target_roots:
        if not os.path.exists(search_dir):
            continue
            
        for root, _, files in os.walk(search_dir):
            if root not in sys.path:
                sys.path.insert(0, root)

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                file_path = os.path.join(root, file)
                module_name = os.path.splitext(file)[0]

                # 特殊ファイルや自分自身をスキップ
                if file.startswith("__") or file == os.path.basename(__file__):
                    continue

                # --- A. Pythonスクリプト (.py) および C拡張モジュール (.pyd) の読み込み ---
                if ext in [".py", ".pyd"]:
                    try:
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)

                        if hasattr(mod, "register_uvn_utilities"):
                            registered_dict = mod.register_uvn_utilities()
                            if isinstance(registered_dict, dict):
                                custom_utils.update(registered_dict)
                                print(f"[Python/PYD Plugin] ロード成功 ({file}): {list(registered_dict.keys())}")
                    except Exception as e:
                        print(f"⚠️ Python/PYD 読み込みエラー ({file}): {e}")

                # --- B. C/C++ DLL (.dll) の読み込み ---
                elif ext == ".dll":
                    try:
                        # Cライブラリのロード
                        dll_obj = ctypes.CDLL(file_path)
                        # 例: DLL側で exported_func という関数がある場合の登録
                        if hasattr(dll_obj, "process_audio_c"):
                            custom_utils[f"dll_{module_name}"] = dll_obj.process_audio_c
                            print(f"[DLL Plugin] ロード成功: {file}")
                    except Exception as e:
                        print(f"⚠️ DLL 読み込みエラー ({file}): {e}")

                # --- C. UVN設定ファイル (.uvn) の読み込み ---
                elif ext == ".uvn":
                    parsed = parse_uvn_file(file_path)
                    if parsed and isinstance(parsed, dict):
                        custom_utils[parsed["name"]] = parsed["hook"]

    return custom_utils

# -------------------------------------------------------------------
# 3. ハイブリッド .uvn パーサー
# -------------------------------------------------------------------
def parse_uvn_file(uvn_path):
    """
    .uvn ファイル（Python形式 / INI形式）を解析するメインパーサー
    """
    if not os.path.exists(uvn_path):
        return None

    filename = os.path.basename(uvn_path)

    try:
        with open(uvn_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️ .uvn 読み込みエラー ({filename}): {e}")
        return None

    # 動的にユーティリティ関数群を Plugins/ および NormalizerPluginsZipper/ から収集してセットアップ
    uvn_utilities = load_uvn_utility_plugins()

    # 1. Pythonスクリプト形式の .uvn として解析
    uvn_globals = {
        "__file__": uvn_path,
        "__name__": f"uvn_module_{os.path.splitext(filename)[0]}",
        "sys": sys,
        "os": os,
        "np": np,
    }
    # 自動収集されたユーティリティ関数群をグローバル空間に全展開
    uvn_globals.update(uvn_utilities)

    try:
        exec(content, uvn_globals)
        if "process_audio_hook" in uvn_globals and callable(uvn_globals["process_audio_hook"]):
            enabled = uvn_globals.get("ENABLED", True)
            plugin_name = uvn_globals.get("PLUGIN_NAME", filename)

            if not enabled:
                print(f"[UVN Script] スキップ (無効化指定): {plugin_name}")
                return None

            hook_func = uvn_globals["process_audio_hook"]
            print(f"[UVN Script Plugin] 読み込み成功: {plugin_name} ({filename})")

            def script_audio_hook(data_float, sample_rate, wave_filename):
                try:
                    return hook_func(data_float, sample_rate, wave_filename)
                except Exception as e:
                    print(f"⚠️ UVN実行エラー [{plugin_name} - {wave_filename}]: {e}")
                    return data_float, sample_rate

            return script_audio_hook
    except Exception:
        pass

    # 2. INI形式の .uvn として解析
    config = configparser.ConfigParser()
    try:
        config.read_string(content)
        if config.has_section("Plugin"):
            enabled = config.getboolean("Plugin", "enabled", fallback=True)
            plugin_name = config.get("Plugin", "name", fallback=filename)

            if not enabled:
                print(f"[UVN INI] スキップ (無効化指定): {plugin_name}")
                return None

            gain_offset_db = config.getfloat("AudioProcess", "gain_offset_db", fallback=0.0)
            low_cut_hz = config.getfloat("AudioProcess", "low_cut_hz", fallback=0.0)
            force_mono = config.getboolean("AudioProcess", "to_mono", fallback=False)

            print(f"[UVN INI Plugin] 読み込み成功: {plugin_name} ({filename})")

            def ini_audio_hook(data_float, sample_rate, wave_filename):
                if force_mono and data_float.ndim > 1:
                    data_float = np.mean(data_float, axis=1)

                if gain_offset_db != 0.0:
                    data_float = uvn_apply_gain_db(data_float, gain_offset_db)

                if low_cut_hz > 0:
                    data_float = uvn_highpass_filter(data_float, low_cut_hz, sample_rate)

                return data_float, sample_rate

            return ini_audio_hook
    except Exception as e:
        print(f"⚠️ .uvn INI解析エラー ({filename}): {e}")

    print(f"⚠️ .uvn 解析警告: 有効な設定または 'process_audio_hook' が見つかりませんでした ({filename})")
    return None
