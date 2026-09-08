# UTAU Volume Normalizer (UVN) プラグイン開発ドキュメント

`.uvn` プラグインシステムおよび `Plugins/` 拡張機能の仕様、GUI自動生成機能、および各種拡張子（`.py`, `.pyd`, `.dll`, `.zip`）の書き方・読み込み仕様についての解説ドキュメントです。

---

## 1. 概要

本システムでは、以下の 2 種類の方式で音声処理およびGUI機能を拡張できます。

1. **`.uvn` プラグイン**: 個別の音量調整や波形処理ロジックを定義するスクリプト（Pythonスクリプト形式 / INI形式の両対応）。GUI定義（`UI_SCHEMA`）を含めることで、メインGUI上に独自の入力フォームを動的生成できます。
2. **`Plugins/` ユーティリティ拡張**: `.uvn` スクリプト内で繰り返し使用できる便利な標準・自作関数を追加する Python モジュール（`.py`）、C拡張（`.pyd`）、動的ライブラリ（`.dll`）、および ZIP アーカイブ（`.zip`）。

---

## 2. `.uvn` スクリプトの書き方

`.uvn` ファイルは、高度なカスタムコード（Pythonスクリプト形式）と、単純な設定（INI形式）の2通りの書き方が可能です。どちらの形式でもGUI上に設定項目を動的表示できます。

### 方式A: Python(UVN)スクリプト形式 (推奨)

Pythonコードを直接記述し、波形データに対する柔軟な処理を実装できます。`UI_SCHEMA` を定義することで、ユーザーがGUI上で設定したパラメータを `params` 辞書経由で受け取ることができます。

```python
# --- プラグイン情報 ---
PLUGIN_NAME = "LowCut & Custom Gain"
ENABLED = True  # False にするとスキップされます

# --- GUI自動生成スキーマ (オプション) ---
# GUI側に自動生成したい入力フォームを定義します
UI_SCHEMA = [
    {"key": "cutoff", "label": "カットオフ周波数 (Hz)", "type": "entry", "default": "80.0"},
    {"key": "gain_db", "label": "ゲイン調整 (dB)", "type": "entry", "default": "1.5"},
    {"key": "use_gate", "label": "ノイズゲートを有効化", "type": "checkbox", "default": False}
]

def process_audio_hook(data, sample_rate, filename, params=None):
    """
    メイン処理から呼び出されるフック関数です。
    
    引数:
      - data (np.ndarray): 音声波形データ (float32)
      - sample_rate (int): サンプリングレート (Hz)
      - filename (str): 処理対象のファイル名
      - params (dict, optional): GUIの UI_SCHEMA で設定されたユーザー入力値
      
    返り値:
      - (data, sample_rate) のタプル
    """
    if params is None:
        params = {}

    # GUIからのパラメーター取得（未設定時はデフォルト値を使用）
    cutoff = float(params.get("cutoff", 80.0))
    gain_db = float(params.get("gain_db", 1.5))
    use_gate = params.get("use_gate", False)

    # 組み込み関数および Plugins/ からロードされた拡張関数を直接利用可能
    data = highpass_filter(data, cutoff=cutoff, sr=sample_rate)
    data = apply_gain_db(data, gain_db=gain_db)
    
    # 拡張ユーティリティ関数の呼び出し例
    if use_gate and "noise_gate" in globals():
        data = noise_gate(data, threshold_db=-45.0)

    # 音割れガード
    data = clip_protection(data)

    return data, sample_rate

```

#### スキーマ指定可能タイプ (`UI_SCHEMA`)

* `type: "entry"` : テキスト / 数値入力フィールド
* `type: "checkbox"` : チェックボックス (True / False)

#### `.uvn` 内でデフォルトで使用できる標準組み込み関数

* `highpass_filter(data, cutoff, sr, order=5)` : ローカット（ハイパス）フィルター
* `lowpass_filter(data, cutoff, sr, order=5)` : ハイカット（ローパス）フィルター
* `apply_gain_db(data, gain_db)` : dB 単位でのゲイン調整
* `clip_protection(data, threshold=1.0)` : 音割れ（クリッピング）防止

---

### 方式B: INI設定(UVN)ファイル形式

シンプルなパラメータ指定のみで処理を行いたい場合に利用できます。パーサー側で解釈され、GUI上に自動的に対応する入力項目が生成されます。

```ini
[Plugin]
name = Simple LowCut Plugin
enabled = true

[AudioProcess]
to_mono = true
gain_offset_db = +1.5
low_cut_hz = 80.0

```

---

## 3. `Plugins/` ユーティリティ拡張の書き方・対応ファイル形式

`Plugins/` フォルダ内にファイルを追加することで、すべての `.uvn` スクリプトから共有で呼び出せる自作関数やバイナリ処理を自動拡張できます。

### 対応ファイル形式

| 形式 / 拡張子 | 概要 / 処理方法 |
| --- | --- |
| **.py** | Pythonソースコード。`register_uvn_utilities()` で関数を公開します。 |
| **.pyd** | C/C++ 等でビルドされた Python C拡張モジュール。`.py` と同様に直接インポート可能です。 |
| **.dll** | C/C++ 等の動的リンクライブラリ。`ctypes` 経由で C 関数を呼び出し・登録します。 |
| **.zip** | 上記の各種プラグインや依存ファイルをまとめたアーカイブ。起動時に自動展開されます。 |

### 配置パスと自動ロード仕様

* **通常ファイル / サブフォルダ**: `Plugins/my_utility.py`, `Plugins/my_native.pyd`, `Plugins/my_lib.dll` など
* **ZIP アーカイブ**: `Plugins/my_utility_pack.zip`
* `.zip` ファイルは初回実行時に自動的に `Plugins/NormalizerPluginsZipper/<ZIP名>/` に解凍・展開され、内部のスクリプトやバイナリが読み込まれます。
* 検索時には `Plugins/` および `Plugins/NormalizerPluginsZipper/` 以下のすべてのサブフォルダが動的に Python の検索パス（`sys.path`）に追加されます。

---

### スクリプトの書き方例

#### 1. Python スクリプト (`Plugins/custom_dsp.py`)

1. 独自の関数を定義します。
2. **`register_uvn_utilities()`** 関数を定義し、`.uvn` 側に公開したい関数を辞書形式で返します。

```python
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

```

#### 2. C拡張モジュール (`Plugins/fast_dsp.pyd`)

Python C API や Cython、PyBind11 等でビルドされた `.pyd` ファイルも、上記 `.py` と同様に内部で `register_uvn_utilities` を関数返却テーブルとして定義しておくことで、シームレスに組み込み関数化されます。

#### 3. C/C++ DLL (`Plugins/native_process.dll`)

`process_audio_c` などのネイティブ関数をエクスポートした DLL は、`ctypes` を通じて `dll_<モジュール名>` という名称で自動登録され、`.uvn` から直接呼び出せます。

---

## 4. エラー処理と動作仕様

* **安全ガード・サンドボックス**: `.uvn` や `Plugins/` 内のコード実行中にエラー（例外）が発生した場合、処理ログにエラー内容を出力した上で該当処理のみが安全にスキップされ、オリジナルの音声データ（`data`, `sample_rate`）がそのまま保持されます。
* **環境変数・ライブラリ**: `.uvn` 内のグローバル空間には、あらかじめ `sys`, `os`, `np` (NumPy) および全ユーティリティ関数が自動注入されています。さらに必要な外部ライブラリ（`scipy`, `librosa` など）はスクリプト内で自由に追加 `import` して使用可能です。
