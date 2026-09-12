# uvn_audio.py

import os
import sys
import glob
import math
import shutil
import datetime
import numpy as np
import soundfile as sf

from uvn_utility import *
from uvn_utility import tr
from scipy.signal import resample_poly

# -------------------------------------------------------------------
# 1. オーディオ処理関数
# -------------------------------------------------------------------
def remove_dc_offset(data):
    if data.ndim > 1:
        return data - np.mean(data, axis=0)
    return data - np.mean(data)

def trim_silence(data, threshold_db=-40.0):
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data

    abs_mono = np.abs(mono)
    max_val = np.max(abs_mono)
    if max_val == 0:
        return data

    threshold = max_val * (10 ** (threshold_db / 20.0))
    non_silent = np.where(abs_mono > threshold)[0]

    if len(non_silent) == 0:
        return data

    start_idx = non_silent[0]
    end_idx = non_silent[-1] + 1

    return data[start_idx:end_idx]

def create_backup(target_path, backup_dirname="_backup", log_func=print):
    """単一ファイルまたはフォルダに対応したバックアップ作成"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if os.path.isfile(target_path):
        base_dir = os.path.dirname(target_path)
        backup_folder = os.path.join(base_dir, f"{backup_dirname}_{timestamp}")
        wav_files = [target_path]
    else:
        base_dir = target_path
        backup_folder = os.path.join(base_dir, f"{backup_dirname}_{timestamp}")
        # WAVとMP3の両方を対象に検索
        wav_files = glob.glob(os.path.join(base_dir, "*.wav")) + glob.glob(os.path.join(base_dir, "*.mp3"))
    
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)
        
    for f in wav_files:
        shutil.copy2(f, backup_folder)
        
    log_func(tr("logs.backup_created", backup_folder=backup_folder))
    return backup_folder

def process_audio(input_dir, mode="peak", target_val=-1.0, output_dirname="", 
                  to_mono=False, remove_dc=True, backup=True, dry_run=False,
                  target_sr=None, trim=False, force_16bit=False,
                  pitch_shift=0.0, speed_rate=1.0,
                  loaded_plugins=None, plugin_params=None, log_func=print, progress_func=None):
    
    if loaded_plugins is None:
        loaded_plugins = []
    if plugin_params is None:
        plugin_params = {}

    target_path = os.path.normpath(input_dir.strip('\'"'))
    if not os.path.exists(target_path):
        log_func(tr("logs.invalid_path", input_dir=target_path))
        return 1

    # --- ファイルかフォルダかの判定および対象ファイルの収集（.wav / .mp3 対応） ---
    valid_extensions = ('.wav', '.mp3', '.flac', '.ogg')
    if os.path.isfile(target_path):
        root_dir = os.path.dirname(target_path)
        wav_files = [target_path] if target_path.lower().endswith(valid_extensions) else []
    else:
        root_dir = target_path
        wav_files = [
            os.path.join(root_dir, f) for f in os.listdir(root_dir)
            if f.lower().endswith(valid_extensions)
        ]

    if not wav_files:
        log_func(tr("logs.no_wav_files", input_dir=target_path))
        return 1

    # --- 出力フォルダの設定（空文字列なら root_dir にそのまま出力） ---
    output_dirname = output_dirname.strip()
    if output_dirname:
        output_folder = os.path.join(root_dir, output_dirname)
    else:
        output_folder = root_dir

    if (pitch_shift != 0.0 or speed_rate != 1.0) and PITCH_ENGINE is None:
        log_func(tr("logs.pitch_library_missing"))
        return 1

    if backup and not dry_run:
        create_backup(target_path, log_func=log_func)

    if not dry_run and not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)

    logs = []

    log_func(tr("logs.settings"))
    log_func(tr("logs.input_folder", input_dir=target_path))
    log_func(tr("logs.output_folder", output_folder=output_folder))
    log_func(tr("logs.normalize", mode=mode.upper(), target=target_val, unit="dBFS" if mode == "peak" else "dB RMS"))
    log_func(tr("logs.pitch_engine", engine=PITCH_ENGINE if PITCH_ENGINE else tr("status.unused")))
    log_func(tr("logs.backup", status=tr("status.enabled") if backup else tr("status.no_backup")))
    log_func(tr("logs.remove_dc", status=tr("status.enabled") if remove_dc else tr("status.disabled")))
    log_func(tr("logs.trim", status=tr("status.enabled") if trim else tr("status.disabled")))
    if pitch_shift != 0.0:
        log_func(tr("logs.pitch_shift", value=pitch_shift))
    if speed_rate != 1.0:
        log_func(tr("logs.speed", value=speed_rate))
    if force_16bit:
        log_func(tr("logs.format"))
    if target_sr:
        log_func(tr("logs.sample_rate", value=target_sr))
    if to_mono:
        log_func(tr("logs.mono"))
    if loaded_plugins:
        log_func(tr("logs.loaded_plugins", count=len(loaded_plugins)))
    if dry_run:
        log_func(tr("logs.dry_run"))
    log_func(tr("logs.separator") + "\n")

    total_files = len(wav_files)
    for idx, file_path in enumerate(wav_files, start=1):
        filename = os.path.basename(file_path)
        warnings = []

        # --- soundfile による読み込み（MP3やID3タグ付き偽WAVにも対応） ---
        try:
            data_float, sample_rate = sf.read(file_path, dtype='float32')
        except Exception as e:
            log_msg = f"[{idx}/{total_files}] ❌ ファイル読み込み失敗: {filename} ({e})"
            logs.append(log_msg)
            log_func(log_msg)
            continue

        if trim:
            data_float = trim_silence(data_float)

        if remove_dc:
            data_float = remove_dc_offset(data_float)

        if to_mono and data_float.ndim > 1:
            data_float = np.mean(data_float, axis=1)

        current_sr = sample_rate
        if target_sr and sample_rate != target_sr:
            g = math.gcd(sample_rate, target_sr)
            data_float = resample_poly(data_float, target_sr // g, sample_rate // g)
            current_sr = target_sr

        # --- ピッチ・速度変更（pyrubberband / librosa 両対応） ---
        if pitch_shift != 0.0 or speed_rate != 1.0:
            engine_used = PITCH_ENGINE
            
            if engine_used == "pyrubberband":
                try:
                    import pyrubberband as pyrb
                    if pitch_shift != 0.0:
                        data_float = pyrb.pitch_shift(data_float, current_sr, n_steps=pitch_shift)
                    if speed_rate != 1.0:
                        data_float = pyrb.time_stretch(data_float, current_sr, rate=speed_rate)
                except Exception:
                    engine_used = "librosa" if "librosa" in sys.modules else None

            if engine_used == "librosa":
                try:
                    import librosa
                    # librosa 処理用に C-contiguous な 1次元(モノラル) or (channels, n_samples) に変換
                    y = data_float.T if data_float.ndim > 1 else data_float
                    y = np.ascontiguousarray(y)

                    if speed_rate != 1.0:
                        if y.ndim > 1:
                            y = np.array([librosa.effects.time_stretch(ch, rate=speed_rate) for ch in y])
                        else:
                            y = librosa.effects.time_stretch(y, rate=speed_rate)

                    if pitch_shift != 0.0:
                        if y.ndim > 1:
                            y = np.array([librosa.effects.pitch_shift(ch, sr=current_sr, n_steps=pitch_shift) for ch in y])
                        else:
                            y = librosa.effects.pitch_shift(y, sr=current_sr, n_steps=pitch_shift)

                    data_float = y.T if y.ndim > 1 else y
                except Exception as e:
                    warnings.append(f"⚠️ピッチ/速度変更処理失敗 ({e})")
            elif engine_used is None:
                warnings.append("⚠️Rubberbandの実行バイナリが見つからず、librosaへの切替も失敗しました")

        # --- プラグイン処理 ---
        for plugin in loaded_plugins:
            try:
                if isinstance(plugin, dict):
                    hook = plugin.get("hook")
                    p_name = plugin.get("name")
                    params = plugin_params.get(p_name, {}) if plugin_params else {}
                else:
                    hook = plugin
                    params = {}

                if callable(hook):
                    import inspect
                    sig = inspect.signature(hook)
                    if "params" in sig.parameters:
                        res = hook(data_float, current_sr, filename, params=params)
                    else:
                        res = hook(data_float, current_sr, filename)

                    if isinstance(res, tuple):
                        data_float = res[0]
                        if len(res) >= 2:
                            current_sr = res[1]
            except Exception as e:
                warnings.append(f"⚠️プラグイン実行エラー: {e}")

        # --- ノーマライズ処理 ---
        peak = np.max(np.abs(data_float))
        if peak == 0:
            warnings.append("❌無音ファイル")

        if peak > 0:
            if mode == "peak":
                target_amp = 10 ** (target_val / 20.0)
                gain = target_amp / peak
            elif mode == "rms":
                current_rms = np.sqrt(np.mean(data_float ** 2))
                target_rms = 10 ** (target_val / 20.0)
                gain = target_rms / (current_rms + 1e-8)
                
                if np.max(np.abs(data_float * gain)) > 0.99:
                    gain = 0.99 / peak
                    warnings.append("⚠️音割れ回避リミッター作動")

            normalized_float = data_float * gain
            gain_db = 20 * np.log10(gain)
        else:
            normalized_float = data_float
            gain_db = 0.0

        # 出力フォーマット設定（デフォルトは 16-bit PCM WAV）
        subtype = 'PCM_16' if (force_16bit or True) else None

        # 出力ファイル名は拡張子を .wav に統一して保存
        base_name = os.path.splitext(filename)[0]
        save_path = os.path.join(output_folder, f"{base_name}.wav")

        warn_str = f" [{' / '.join(warnings)}]" if warnings else ""
        log_msg = tr("logs.file_result", current=idx, total=total_files, filename=filename,
                     gain=gain_db, sample_rate=current_sr, warnings=warn_str)
        logs.append(log_msg)
        log_func(log_msg)

        if not dry_run:
            # soundfile を使って真の WAV ファイルとして保存
            sf.write(save_path, normalized_float, current_sr, subtype=subtype)

        if progress_func:
            progress_func(idx, total_files)

    if not dry_run:
        log_path = os.path.join(output_folder, "normalize_log.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(logs))
        log_func("\n" + tr("logs.log_written", log_path=log_path))

    log_func("\n" + tr("logs.completed"))
    return 0
