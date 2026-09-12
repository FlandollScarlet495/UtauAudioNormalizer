# UTAU Volume Normalizer (UVN) プラグイン開発ドキュメント

`.uvn` プラグインと `Plugins/` 拡張機能の仕様、GUIの自動生成、読み込み時の注意点を説明します。記載内容は現在のPython実装に基づきます。

---

## 1. 概要

本システムには、次の2種類の拡張があります。

1. **`.uvn` プラグイン**: Pythonスクリプト形式またはINI形式で、音声処理フックを定義します。Python形式では `UI_SCHEMA` によるGUI入力を定義できます。
2. **`Plugins/` ユーティリティ拡張**: `.uvn` から共有利用する関数を、`.py`、`.pyd`、`.dll`、`.zip` で追加できます。

プラグインは、入力WAVを浮動小数点の波形データへ変換した後、ノーマライズ処理の前に実行されます。プラグインが失敗しても、音声処理全体は可能な限り継続します。

---

## 2. `.uvn` ファイル

### 方式A: Pythonスクリプト形式（推奨）

`.uvn` にPythonコードを記述し、`process_audio_hook` を定義します。`PLUGIN_NAME`、`ENABLED`、`UI_SCHEMA` は任意です。

```python
PLUGIN_NAME = "LowCut & Custom Gain"
ENABLED = True

UI_SCHEMA = [
    {"key": "cutoff", "label": "カットオフ周波数 (Hz)", "type": "entry", "default": "80.0"},
    {"key": "gain_db", "label": "ゲイン調整 (dB)", "type": "entry", "default": "1.5"},
    {"key": "use_gate", "label": "ノイズゲートを有効化", "type": "checkbox", "default": False},
]

def process_audio_hook(data, sample_rate, filename, params=None):
    if params is None:
        params = {}

    cutoff = float(params.get("cutoff", 80.0))
    gain_db = float(params.get("gain_db", 1.5))
    use_gate = bool(params.get("use_gate", False))

    data = highpass_filter(data, cutoff=cutoff, sr=sample_rate)
    data = apply_gain_db(data, gain_db=gain_db)

    if use_gate and "noise_gate" in globals():
        data = noise_gate(data, threshold_db=-45.0)

    return clip_protection(data), sample_rate
```

#### 予約された変数

| 変数 | 説明 |
| --- | --- |
| `PLUGIN_NAME` | プラグイン名。未指定時は `.uvn` のファイル名です。 |
| `DISPLAY_NAME` | GUI表示名。未指定時は `PLUGIN_NAME` です。 |
| `ENABLED` | `False` の場合は処理対象から除外されます。既定値は `True` です。 |
| `UI_TARGET` | `main` または `tab`。GUIの配置先を指定します。既定値は `main` です。 |
| `UI_SCHEMA` | GUI入力の配列。未指定時は空配列です。 |

#### `process_audio_hook` の引数と戻り値

フックは次の形で呼び出されます。

```text
process_audio_hook(data, sample_rate, filename, params=params)
```

`params` 引数を定義していないフックは、`params`なしで呼び出されます。

- `data`: NumPy配列の音声データ（通常は `float32`、振幅はおおむね -1.0～1.0）
- `sample_rate`: 現在のサンプリングレート（整数）
- `filename`: 処理対象WAVのファイル名
- `params`: GUIで入力された値の辞書。`entry` は文字列、`checkbox` は真偽値です。
- 戻り値: `(data, sample_rate)` または `(data, sample_rate, filename)` のタプル。処理エンジンは先頭2要素を使用します。

### `UI_SCHEMA`

`UI_SCHEMA` は次の形式の辞書の配列です。

```python
UI_SCHEMA = [
    {"key": "cutoff", "label": "カットオフ (Hz)", "type": "entry", "default": "80.0"},
    {"key": "enabled", "label": "有効化", "type": "checkbox", "default": True},
]
```

- `key`: `params` 辞書で使用するキー
- `label`: GUIに表示するラベル。未指定時は `key`
- `type`: `entry` または `checkbox`。未指定時は `entry`
- `default`: 初期値。`entry` は文字列として、`checkbox` は真偽値としてGUIへ渡されます。

`UI_TARGET = "main"` ならメイン設定画面、`UI_TARGET = "tab"` なら専用タブに表示されます。INI形式には `UI_SCHEMA` はなく、GUI入力も生成されません。

### 標準ユーティリティ

Python形式の `.uvn` のグローバルスコープには、次の関数と `sys`、`os`、`np` が注入されます。

| 関数 | 説明 |
| --- | --- |
| `highpass_filter(data, cutoff, sr, order=5)` | ハイパスフィルター。無効なカットオフの場合は入力を返します。 |
| `lowpass_filter(data, cutoff, sr, order=5)` | ローパスフィルター。無効なカットオフの場合は入力を返します。 |
| `apply_gain_db(data, gain_db)` | dB単位のゲインを適用します。 |
| `clip_protection(data, threshold=1.0)` | 振幅を `-threshold`～`threshold` に制限します。 |

これらはデコーダーが提供する実装です。フィルターは `scipy.signal.lfilter` を使用し、ステレオ以上の多チャンネルデータにも対応します。

### 方式B: INI形式

単純な音声処理だけが必要な場合は、次のINI形式を使用できます。

```ini
[Plugin]
name = Simple LowCut Plugin
enabled = true

[AudioProcess]
to_mono = true
gain_offset_db = +1.5
low_cut_hz = 80.0
```

対応する設定は次のとおりです。

- `[Plugin] name`: プラグイン名。未指定時はファイル名
- `[Plugin] enabled`: `false` で無効化
- `[AudioProcess] to_mono`: `true` でモノラル化
- `[AudioProcess] gain_offset_db`: ゲイン補正値（dB）
- `[AudioProcess] low_cut_hz`: ハイパスのカットオフ周波数（Hz）

未指定の音声設定は、モノラル化なし、ゲイン0 dB、ローカットなしになります。INIプラグインは `(data, sample_rate)` を返す処理フックとして登録され、`UI_SCHEMA` による自動GUIはありません。

---

## 3. `Plugins/` ユーティリティ拡張

### プラグイン個別の言語リソース

プラグイン名と同じフォルダ名を使って、次の場所に言語ファイルを配置できます。

```text
Plugins/
├── my_plugin/
│   └── my_plugin.uvn
└── Language/
    └── my_plugin/
        ├── ja-jp.lang
        └── en-us.lang
```

`.uvn`の`UI_SCHEMA`または`DISPLAY_NAME`で`@キー`を指定すると、現在の本体言語に対応するプラグイン言語ファイルから翻訳されます。プラグインコード内では、注入された`plugin_tr("キー")`を使用できます。ファイルがない場合やキーがない場合は、指定したキーがそのまま表示されます。

本体の言語はGUIの言語選択、`--language`、または`UTAU_LANGUAGE`で変更できます。プラグイン言語も同じ選択に追従します。

### 対応形式

| 形式 | 読み込みと登録 |
| --- | --- |
| `.py` | `register_uvn_utilities()` が返す辞書をユーティリティとして登録します。 |
| `.pyd` | Python拡張モジュールです。`register_uvn_utilities()` による登録をサポートします。通常の初期化処理では `register_plugin()` も利用できます。 |
| `.dll` | `ctypes.CDLL` で読み込み、`process_audio_c` がエクスポートされていれば `dll_<ファイル名>` として登録します。呼び出し規約と引数定義はDLL側で一致させてください。 |
| `.zip` | ZIP自体を `sys.path` に追加し、内部の `.py`、`.pyd`、`.dll`、`.uvn` を読み込もうとします。自動展開は行いません。 |

### 配置と走査

通常は次の場所へ配置します。

```text
Plugins/custom_dsp.py
Plugins/fast_dsp.pyd
Plugins/native_process.dll
Plugins/my_plugins.zip
Plugins/my_plugin/test.uvn
```

`Plugins/` 以下のサブフォルダも再帰的に走査され、各フォルダはPythonの検索パス（`sys.path`）へ追加されます。WindowsではDLL探索のため、各フォルダがプロセスの `PATH` とDLL検索パスにも追加されます。

ZIP内のPythonモジュールはZIPから直接インポートされます。ZIP内のDLLは一時ファイルへ書き出して読み込まれます。ZIP内の `.uvn` は現在の実装上、通常の `.uvn` スキャンと同じ登録形態になることを保証していないため、安定して利用する場合は `Plugins/` 配下へ直接配置してください。

### Pythonユーティリティの例

```python
import numpy as np

def noise_gate(data, threshold_db=-40.0):
    threshold = 10 ** (threshold_db / 20.0)
    data[np.abs(data) < threshold] = 0.0
    return data

def register_uvn_utilities():
    return {"noise_gate": noise_gate}
```

登録された辞書のキーが、そのまま `.uvn` のグローバルスコープで使用する関数名になります。標準ユーティリティと同じキーを登録した場合は、後から読み込まれた拡張が上書きします。

---

## 4. エラー処理と注意事項

- プラグインの読み込みエラーはログへ出力され、そのプラグインの読み込みをスキップします。
- `.uvn` の実行エラーはログへ出力され、そのフックについては処理前の `data` と `sample_rate` が返されます。
- 音声処理中のプラグインエラーは警告として記録され、次のプラグインまたはノーマライズ処理へ進みます。
- これはサンドボックスではありません。`.uvn` とPythonユーティリティは通常のPythonコードとして実行され、ファイル、環境変数、外部ライブラリなどへアクセスできます。信頼できるプラグインだけを使用してください。
- `scipy`、`librosa` などの外部ライブラリは自動注入されません。必要な場合は `.uvn` 内で `import` し、実行環境へ別途インストールしてください。
- `ctypes` DLLの関数シグネチャやメモリ安全性は検証されません。`process_audio_c` を通常のPython音声配列処理関数として利用するには、DLL側のABI設計とPython側の呼び出し形式を一致させる必要があります。

---
