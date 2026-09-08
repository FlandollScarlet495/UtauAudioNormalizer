# uvn_audio.py

import os
import glob
import math
import shutil
import datetime
import numpy as np

from scipy.io import wavfile
from scipy.signal import resample_poly
from uvn_utility import *


# -------------------------------------------------------------------
# オーディオ処理関数
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

def create_backup(input_dir, backup_dirname="_backup", log_func=print):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = os.path.join(input_dir, f"{backup_dirname}_{timestamp}")
    wav_files = glob.glob(os.path.join(input_dir, "*.wav"))
    
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)
        
    for f in wav_files:
        shutil.copy2(f, backup_folder)
        
    log_func(f"[バックアップ作成] -> {backup_folder}")
    return backup_folder

def process_audio(input_dir, mode="peak", target_val=-1.0, output_dirname="音源", 
                  to_mono=False, remove_dc=True, backup=True, dry_run=False,
                  target_sr=None, trim=False, force_16bit=False,
                  pitch_shift=0.0, speed_rate=1.0,
                  loaded_plugins=None, log_func=print, progress_func=None):
    
    if loaded_plugins is None:
        loaded_plugins = []

    input_dir = os.path.normpath(input_dir.strip('\'"'))
    if not os.path.exists(input_dir):
        log_func(f"エラー: 指定されたパスが存在しません:\n{input_dir}")
        return

    output_folder = os.path.join(input_dir, output_dirname)
    wav_files = glob.glob(os.path.join(input_dir, "*.wav"))
    
    if not wav_files:
        log_func(f"エラー: '{input_dir}' 直下にWAVファイルが見つかりませんでした。")
        return

    if (pitch_shift != 0.0 or speed_rate != 1.0) and PITCH_ENGINE is None:
        log_func("エラー: ピッチ・速度変更に必要なライブラリ (pyrubberband または librosa) が見つかりません。")
        return

    if backup and not dry_run:
        create_backup(input_dir, log_func=log_func)

    if not dry_run and not os.path.exists(output_folder):
        os.makedirs(output_folder)

    logs = []

    log_func("--- 設定内容 ---")
    log_func(f"入力フォルダ     : {input_dir}")
    log_func(f"出力先フォルダ   : {output_folder}")
    log_func(f"処理モード       : {mode.upper()} ノーマライズ (目標: {target_val} {'dBFS' if mode == 'peak' else 'dB RMS'})")
    log_func(f"ピッチ/速度エンジン: {PITCH_ENGINE if PITCH_ENGINE else '未使用'}")
    log_func(f"自動バックアップ : {'有効' if backup else '無効 (nobackup)'}")
    log_func(f"DCオフセット除去 : {'有効' if remove_dc else '無効'}")
    log_func(f"無音トリミング   : {'有効' if trim else '無効'}")
    if pitch_shift != 0.0:
        log_func(f"ピッチシフト     : {pitch_shift:+} 半音")
    if speed_rate != 1.0:
        log_func(f"再生速度         : {speed_rate} 倍速")
    if force_16bit:
        log_func("フォーマット固定 : 16-bit PCM")
    if target_sr:
        log_func(f"サンプリングレート: {target_sr} Hz")
    if to_mono:
        log_func("チャンネル変換   : モノラル (Mono)")
    if loaded_plugins:
        log_func(f"読み込み済プラグイン: {len(loaded_plugins)} 件")
    if dry_run:
        log_func("※ドライランモード (ファイル出力なし)")
    log_func("----------------\n")

    total_files = len(wav_files)
    for idx, file_path in enumerate(wav_files, start=1):
        filename = os.path.basename(file_path)
        sample_rate, data = wavfile.read(file_path)
        warnings = []

        if trim:
            data = trim_silence(data)

        if remove_dc:
            data = remove_dc_offset(data)

        if to_mono and data.ndim > 1:
            data = np.mean(data, axis=1)

        current_sr = sample_rate
        if target_sr and sample_rate != target_sr:
            g = math.gcd(sample_rate, target_sr)
            data = resample_poly(data, target_sr // g, sample_rate // g)
            current_sr = target_sr

        data_float = data.astype(np.float32)
        if data.dtype == np.int16:
            data_float /= 32768.0
        elif data.dtype == np.int32:
            data_float /= 2147483648.0
        elif data.dtype == np.uint8:
            data_float = (data_float - 127.5) / 127.5
        elif data.dtype == np.float32 or data.dtype == np.float64:
            pass  # そのまま利用

        if pitch_shift != 0.0 or speed_rate != 1.0:
            engine_used = PITCH_ENGINE
            
            if engine_used == "pyrubberband":
                try:
                    if pitch_shift != 0.0:
                        data_float = pyrb.pitch_shift(data_float, current_sr, n_steps=pitch_shift)
                    if speed_rate != 1.0:
                        data_float = pyrb.time_stretch(data_float, current_sr, rate=speed_rate)
                except Exception:
                    engine_used = "librosa" if "librosa" in sys.modules else None

            if engine_used == "librosa":
                try:
                    import librosa
                    if speed_rate != 1.0:
                        data_float = librosa.effects.time_stretch(data_float, rate=speed_rate)
                    if pitch_shift != 0.0:
                        data_float = librosa.effects.pitch_shift(data_float, sr=current_sr, n_steps=pitch_shift)
                except Exception as e:
                    warnings.append(f"⚠️ピッチ/速度変更処理失敗 ({e})")
            elif engine_used is None:
                warnings.append("⚠️Rubberbandの実行バイナリが見つからず、librosaへの切替も失敗しました")

        for hook in loaded_plugins:
            try:
                if callable(hook):
                    data_float, current_sr = hook(data_float, current_sr, filename)
            except Exception as e:
                warnings.append(f"⚠️プラグイン実行エラー: {e}")

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

        if force_16bit or data.dtype in [np.int16, np.int32, np.uint8]:
            out_data = np.clip(normalized_float * 32767.0, -32768, 32767).astype(np.int16)
        else:
            out_data = normalized_float

        save_path = os.path.join(output_folder, filename)
        warn_str = f" [{' / '.join(warnings)}]" if warnings else ""
        log_msg = f"[{idx}/{total_files}] {filename} | Gain: {gain_db:+.2f} dB | SR: {current_sr}Hz{warn_str}"
        logs.append(log_msg)
        log_func(log_msg)

        if not dry_run:
            wavfile.write(save_path, current_sr, out_data)

        if progress_func:
            progress_func(idx, total_files)

    if not dry_run:
        log_path = os.path.join(output_folder, "normalize_log.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(logs))
        log_func(f"\nログファイル出力完了: {log_path}")

    log_func("\n全ファイルの処理が完了しました！")
