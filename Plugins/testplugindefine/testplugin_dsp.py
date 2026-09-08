# root/Plugins/testplugindefine/testplugin_dsp.py

import numpy as np

def noise_gate(data, threshold_db=-40.0):
    """指定した閾値以下の振幅をゼロにする簡易ノイズゲート"""
    threshold = 10 ** (threshold_db / 20.0)
    data[np.abs(data) < threshold] = 0.0
    return data

def soft_clipper(data, drive=1.2):
    """波形を滑らかに歪ませて音圧を稼ぐソフトクリッパー"""
    return np.tanh(data * drive)

# --- エントリーポイント ---
def register_uvn_utilities():
    """
    パーサーが自動ロードする際に呼び出される関数です。
    {".uvn側での関数名": 関数オブジェクト} の形式で返却します。
    """
    return {
        "noise_gate": noise_gate,
        "soft_clipper": soft_clipper,
    }
