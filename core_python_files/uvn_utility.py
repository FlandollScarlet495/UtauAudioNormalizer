# uvn_utility.py

import os
import sys
import locale
import zipfile
import shutil
import importlib.util
import numpy as np

from scipy.signal import butter, filtfilt
try:
    from uvn_plugin_runtime.decoder import parse_uvn_file
except Exception:
    parse_uvn_file = None

# -------------------------------------------------------------------
# 1. .uvn スクリプトで共有利用できる標準ヘルパー関数群
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
# 2. Plugins フォルダのスキャン & パス・ライブラリ設定
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS_DIR = os.path.join(BASE_DIR, "Plugins")

# --- パス解決および Languages フォルダの探索 ---
if getattr(sys, 'frozen', False):
    # exe 化されている場合：utau_volume_normalizer.exe が置いてあるフォルダ（外部参照用）
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 通常の Python 実行時：スクリプトが存在するフォルダ
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTERNAL_LANGUAGE_DIR = os.path.join(BASE_DIR, "Languages")

INTERNAL_LANGUAGE_DIR = None
if hasattr(sys, "_MEIPASS"):
    candidate_root = sys._MEIPASS
    candidate_lib = os.path.join(sys._MEIPASS, "libraries", "Languages")

    # 1. 指定したい場合（candidate_lib が明示的に存在する場合）をチェック
    if os.path.isdir(candidate_lib):
        INTERNAL_LANGUAGE_DIR = candidate_lib

def _get_language_file_path(language_code):
    """開発用（外部フォルダ）を優先し、無ければ内部埋め込み（PyInstaller）を探す"""
    filename = f"{language_code}.lang"
    
    # 1. 外部 Languages フォルダ（開発中・外部調整用）
    ext_path = os.path.join(EXTERNAL_LANGUAGE_DIR, filename)
    if os.path.isfile(ext_path):
        print(f"[Language] 外部言語ファイルを使用: {ext_path}")
        return ext_path
        
    # 2. 明示指定された candidate_lib から検索
    if INTERNAL_LANGUAGE_DIR:
        int_path = os.path.join(INTERNAL_LANGUAGE_DIR, filename)
        if os.path.isfile(int_path):
            print(f"[Language] 指定ライブラリ内の言語ファイルを使用: {int_path}")
            return int_path

    # 3. candidate_root (sys._MEIPASS) 配下をすべて再帰検索 (--onefile / --onedir 救済)
    if hasattr(sys, "_MEIPASS"):
        for root, _, files in os.walk(sys._MEIPASS):
            if filename in files:
                found_path = os.path.join(root, filename)
                print(f"[Language] 内部全検索で見つかった言語ファイルを使用: {found_path}")
                return found_path

    print(f"[Language] 言語ファイルが見つかりません: {filename}")
    return None

def _read_language_file(language_code, base_translations=None):
    translations = dict(base_translations or {})
    path = _get_language_file_path(language_code)
    
    if path:
        try:
            with open(path, "r", encoding="utf-8") as language_file:
                for raw_line in language_file:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    translations[key.strip()] = value.strip().replace("\\n", "\n")
        except (OSError, UnicodeError) as e:
            print(f"[Language] 言語ファイルの読み込みエラー: {e}")
            
    return translations

_DEFAULT_TRANSLATIONS = _read_language_file("en-us")

def _load_language_file(language_code):
    return _read_language_file(language_code, _DEFAULT_TRANSLATIONS)

_translations = dict(_DEFAULT_TRANSLATIONS)
CURRENT_LANGUAGE = "en-us"

def _detect_system_language():
    """OSのロケールを対応する地域付き言語IDへ変換する"""
    try:
        system_locale = locale.getlocale()[0] or ""
    except (ValueError, TypeError):
        system_locale = ""
    system_locale = system_locale.lower().replace("_", "-")
    if system_locale.startswith("ja"):
        return "ja-jp"
    if system_locale.startswith("en"):
        return "en-us"
    return "en-us"

def set_language(language_code):
    """指定された言語を読み込み、現在の翻訳を切り替える"""
    global _translations, CURRENT_LANGUAGE
    language_code = str(language_code).lower().replace("_", "-")
    language_aliases = {"ja": "ja-jp", "en": "en-us"}
    language_code = language_aliases.get(language_code, language_code)
    if language_code not in ("ja-jp", "en-us"):
        language_code = _detect_system_language()
    _translations = _load_language_file(language_code)
    CURRENT_LANGUAGE = language_code
    os.environ["UTAU_LANGUAGE"] = language_code
    return CURRENT_LANGUAGE

def get_available_languages():
    return ("ja-jp", "en-us")

def tr(key, **values):
    """翻訳キーを取得し、指定されたプレースホルダーを展開する"""
    text = _translations.get(key, _DEFAULT_TRANSLATIONS.get(key, key))
    return text.format(**values) if values else text

set_language(os.environ.get("UTAU_LANGUAGE") or _detect_system_language())

def init_plugins_environment(plugins_root, log_func=print):
    """Plugins 内を走査してパス登録とプラグイン初期化を行う"""
    uvn_parsers = []
    custom_hooks = []

    if not os.path.exists(plugins_root):
        os.makedirs(plugins_root, exist_ok=True)

    for root, dirs, files in os.walk(plugins_root):
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

    # デフォルトパーサー（事前インポートに成功している場合）を追加
    if parse_uvn_file is not None:
        uvn_parsers.append(parse_uvn_file)
    else:
        log_func("⚠️ 標準UVNデコーダープラグインが検出されませんでした。")

    # .uvn ファイルのスキャンと解析処理
    for root, dirs, files in os.walk(plugins_root):
        for file in files:
            if file.endswith(".uvn"):
                uvn_path = os.path.join(root, file)
                for parser in uvn_parsers:
                    try:
                        hook = parser(uvn_path)
                        if hook:
                            custom_hooks.append(hook)
                            log_func(f"[UVN Plugin] 読み込み成功: {file}")
                            break
                    except Exception as e:
                        log_func(f"⚠️ UVN解析エラー ({file}): {e}")

    return uvn_parsers, custom_hooks

# -------------------------------------------------------------------
# 3. 音声処理エンジン (pyrubberband -> librosa フォールバック)
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
