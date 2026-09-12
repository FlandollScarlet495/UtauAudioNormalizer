# decoder.py

import configparser
import ctypes
import importlib
import importlib.util
import os
import sys
import tempfile
import zipfile

import numpy as np
from scipy.signal import butter, lfilter


PLUGIN_LANGUAGE_ROOT = "PluginsLanguages"


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_plugin_language(uvn_path):
    plugin_dir = os.path.dirname(os.path.abspath(uvn_path))
    plugin_name = os.path.basename(plugin_dir)
    language_code = os.environ.get("UTAU_LANGUAGE", "en-us").lower().replace("_", "-")
    language_code = {"ja": "ja-jp", "en": "en-us"}.get(language_code, language_code)
    if language_code not in ("ja-jp", "en-us"):
        language_code = "en-us"
    path = os.path.join(_base_dir(), PLUGIN_LANGUAGE_ROOT, plugin_name, f"{language_code}.lang")
    translations = {}
    try:
        with open(path, "r", encoding="utf-8") as language_file:
            for raw_line in language_file:
                line = raw_line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    translations[key.strip()] = value.strip().replace("\\n", "\n")
    except (OSError, UnicodeError):
        pass
    return translations


def _plugin_tr(translations, key, **values):
    text = translations.get(key, key)
    return text.format(**values) if values else text


def _translate_schema(schema, translations):
    translated = []
    for item in schema if isinstance(schema, list) else []:
        item = dict(item) if isinstance(item, dict) else {}
        for field in ("label", "default"):
            value = item.get(field)
            if isinstance(value, str) and value.startswith("@"):
                item[field] = _plugin_tr(translations, value[1:])
        translated.append(item)
    return translated


def uvn_highpass_filter(data, cutoff, sr, order=5):
    if cutoff <= 0 or cutoff >= sr / 2:
        return data
    b, a = butter(order, cutoff / (0.5 * sr), btype="high", analog=False)
    if data.ndim > 1:
        return np.vstack([lfilter(b, a, data[:, c]) for c in range(data.shape[1])]).T
    return lfilter(b, a, data)


def uvn_lowpass_filter(data, cutoff, sr, order=5):
    if cutoff <= 0 or cutoff >= sr / 2:
        return data
    b, a = butter(order, cutoff / (0.5 * sr), btype="low", analog=False)
    if data.ndim > 1:
        return np.vstack([lfilter(b, a, data[:, c]) for c in range(data.shape[1])]).T
    return lfilter(b, a, data)


def uvn_apply_gain_db(data, gain_db):
    return data if gain_db == 0.0 else data * (10 ** (gain_db / 20.0))


def uvn_clip_protection(data, threshold=1.0):
    return np.clip(data, -threshold, threshold)


BASE_UVN_UTILITIES = {
    "highpass_filter": uvn_highpass_filter,
    "lowpass_filter": uvn_lowpass_filter,
    "apply_gain_db": uvn_apply_gain_db,
    "clip_protection": uvn_clip_protection,
}


def load_uvn_utility_plugins():
    plugins_dir = os.path.join(_base_dir(), "Plugins")
    utilities = BASE_UVN_UTILITIES.copy()
    if not os.path.isdir(plugins_dir):
        return utilities
    for root, _, files in os.walk(plugins_dir):
        if root not in sys.path:
            sys.path.insert(0, root)
        for filename in files:
            extension = os.path.splitext(filename)[1].lower()
            path = os.path.join(root, filename)
            if filename.startswith("__") or extension not in (".py", ".pyd"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(os.path.splitext(filename)[0], path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "register_uvn_utilities"):
                    registered = module.register_uvn_utilities()
                    if isinstance(registered, dict):
                        utilities.update(registered)
            except Exception as error:
                print(f"[Plugin utility load error] {filename}: {error}")
    return utilities


def parse_uvn_content(content, uvn_path="memory.uvn"):
    filename = os.path.basename(uvn_path)
    translations = _read_plugin_language(uvn_path)
    utilities = load_uvn_utility_plugins()
    namespace = {"__file__": uvn_path, "__name__": f"uvn_module_{os.path.splitext(filename)[0]}", "sys": sys, "os": os, "np": np}
    namespace.update(utilities)
    namespace["plugin_translations"] = translations
    namespace["plugin_tr"] = lambda key, **values: _plugin_tr(translations, key, **values)
    try:
        exec(content, namespace)
        hook = namespace.get("process_audio_hook")
        if callable(hook):
            plugin_name = namespace.get("PLUGIN_NAME", filename)
            display_name = namespace.get("DISPLAY_NAME", plugin_name)
            if isinstance(display_name, str) and display_name.startswith("@"):
                display_name = _plugin_tr(translations, display_name[1:])
            if not namespace.get("ENABLED", True):
                return None
            return {"name": plugin_name, "display_name": display_name, "ui_target": namespace.get("UI_TARGET", "main").lower(), "ui_schema": _translate_schema(namespace.get("UI_SCHEMA", []), translations), "hook": _wrap_hook(hook, plugin_name)}
    except Exception:
        pass
    config = configparser.ConfigParser()
    try:
        config.read_string(content)
        if config.has_section("Plugin"):
            if not config.getboolean("Plugin", "enabled", fallback=True):
                return None
            gain = config.getfloat("AudioProcess", "gain_offset_db", fallback=0.0)
            low_cut = config.getfloat("AudioProcess", "low_cut_hz", fallback=0.0)
            force_mono = config.getboolean("AudioProcess", "to_mono", fallback=False)
            def ini_hook(data, sample_rate, wave_filename):
                if force_mono and data.ndim > 1:
                    data = np.mean(data, axis=1)
                if gain:
                    data = uvn_apply_gain_db(data, gain)
                if low_cut:
                    data = uvn_highpass_filter(data, low_cut, sample_rate)
                return data, sample_rate
            return ini_hook
    except Exception as error:
        print(f"[UVN parse error] {filename}: {error}")
    return None


def _wrap_hook(hook, plugin_name):
    def script_hook(data, sample_rate, wave_filename, params=None):
        try:
            import inspect
            if "params" in inspect.signature(hook).parameters:
                return hook(data, sample_rate, wave_filename, params=params)
            return hook(data, sample_rate, wave_filename)
        except Exception as error:
            print(f"[UVN execution error] {plugin_name} - {wave_filename}: {error}")
            return data, sample_rate
    return script_hook


def parse_uvn_file(uvn_path):
    try:
        with open(uvn_path, "r", encoding="utf-8") as source:
            return parse_uvn_content(source.read(), uvn_path)
    except (OSError, UnicodeError) as error:
        print(f"[UVN read error] {os.path.basename(uvn_path)}: {error}")
        return None
