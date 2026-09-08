# UTAU Audio Normalizer (UTAU音源用 高機能オーディオノーマライザー)

UTAU音源の制作・調整・バッチ処理に最適化された高機能オーディオ処理ツールです。  
GUIによる直感的な操作と、コマンドライン（CLI）からの柔軟なバッチ処理の両方に対応しています。独自のプラグイン機構（`.py` / `.pyd` / `.uvn`）を備えており、高い拡張性を実現しています。

---

## 主な機能

- **高度な音量平均化 (ノーマライズ)**:
  - Peak（ピーク / dBFS）モード
  - RMS（実効値 / dB RMS）モード（※音割れを防止する自動リミッター機能付き）
- **UTAU最適化プリセット**: ワンクリックでUTAU標準フォーマット（16-bit PCM / 44.1kHz / モノラル）に統一可能。
- **音声処理オプション**:
  - DCオフセット除去（オン/オフ切替可能）
  - 前後の無音区間トリミング
  - サンプリングレート変換（多項式リサンプル）＆ モノラル化
  - ピッチシフト（半音単位）およびタイムストレッチ（速度変更）
- **プラグイン拡張機構**:
  - `Plugins/` 内の `.zip` 自動解凍および `PluginsZipper/` への展開・環境パス（PATH/DLL）自動登録
  - `.py` / `.pyd` スクリプトからのカスタム処理フック呼び出し（`UI_SCHEMA` によるGUI連携対応）
  - `.uvn` 独自定義ファイルの解析とカスタム波形処理フィルターの適用
- **安全設計**:
  - 処理前の自動タイムスタンプ付きバックアップ機能 (`_backup_YYYYMMDD_HHMMSS`)
  - 出力結果を確認できる試行実行（Dry-Run）モード
  - 処理ログのテキスト出力 (`normalize_log.txt`)

---

## フォルダ構成

```text
UtauAudioNormalizer/
├── Plugins/                                  # ユーザープラグイン格納ディレクトリ
│   ├── rubberband/
│   └── utau_volume_normalizer_plugin/
│       ├── README_PLUGINS.md
│       └── utau_volume_normalizer_plugin.py
├── main.py
├── utau_volume_normalizer.py                 # メインエントリポイント (GUI/CLI兼用)
├── uvn_audio.py                              # オーディオ処理エンジン & バックアップ機能
├── uvn_utility.py                            # フィルター関数 & プラグイン環境構築
└── uvn_gui.py                                # TkinterベースのGUIロジック

```

※実行時に `Plugins/` 内のZIP展開先として `PluginsZipper/` フォルダが自動作成されます。`uvn_utility.py` と `utau_volume_normalizer_plugin_decoder.py` の共通処理により、モジュール間の依存関係を安全に保持し、ライブラリの二重読み込みやパスエラーを防止します。

---

## 動作環境・必要ライブラリ

### 必須環境

- **OS**: Windows (付属のバイナリ使用時)
- **Python**: 3.8 以上
- **依存ライブラリ**:

```bash
pip install numpy scipy

```

### 任意（ピッチ・速度変更機能を利用する場合）

ピッチシフトや速度変更処理を行うには、以下のいずれかのライブラリが必要です。

- `pyrubberband`（推奨：`Plugins/rubberband/` 内のバイナリを使用）
- `librosa`（フォールバック用）

```bash
pip install -r requirements.txt

```

---

## 使い方

### 1. GUI モード (グラフィカル表示)

引数なしで実行するとGUI画面が立ち上がります。

```bash
python utau_volume_normalizer.py

```

1. **対象フォルダ選択**: WAVファイルが入ったフォルダを指定します。
2. **ノーマライズ設定**: 方式（Peak/RMS）と目標値（dB）を入力します。
3. **変換＆編集オプション**: 必要に応じて「UTAU最適化プリセット」、ピッチ・速度変更、無音トリミングや「DCオフセット除去」などの設定を行います。
4. **処理を開始する**: ボタンを押すとバックグラウンドでバッチ処理が実行され、進捗バーとログが表示されます。

---

### 2. CLI モード (コマンドライン)

引数やオプションを指定して実行すると、自動的にCLIモードとして動作します。

```bash
python utau_volume_normalizer.py <対象フォルダパス> [オプション]

```

#### 主なコマンドラインオプション

| オプション | 短縮形 | 説明 | デフォルト |
| --- | --- | --- | --- |
| `input` | - | **[必須]** 対象となるWAVファイルが含まれるフォルダのパス | - |
| `--mode` | `-m` | ノーマライズ方式 (`peak` または `rms`) | `peak` |
| `--target` | `-t` | 目標値 (dB) | Peak: -1.0 / RMS: -20.0 |
| `--outdir` | `-o` | 出力先フォルダ名 | `音源` |
| `--utau-preset` | - | UTAU最適化 (16bit / 44.1kHz / モノラル 固定) | Off |
| `--sample-rate` | `-s` | サンプリングレートの変換 (例: `44100`) | 自動設定 |
| `--mono` | - | モノラル化 | Off |
| `--trim` | - | 前後の無音区間をトリミング | Off |
| `--no-dc` | - | DCオフセット除去を無効化 | Off |
| `--pitch` | `-p` | ピッチ変更 (半音単位, 例: `1.5`, `-2.0`) | `0.0` |
| `--speed` | - | 再生速度変更 (倍率, 例: `1.2`) | `1.0` |
| `--nobackup` | - | 自動バックアップ作成をスキップ | Off |
| `--dry-run` | - | ファイル出力を行わずに処理内容のみテスト実行 | Off |
| `--command-line-mode` | - | 明示的にCLIモードで起動 | Off |

#### 使用例

- **基本処理（Peak -1.0dB）**

```bash
python utau_volume_normalizer.py "C:\path\to\wav_folder" -m peak -t -1.0

```

- **UTAU最適化 ＋ バックアップあり出力**

```bash
python utau_volume_normalizer.py "D:\UTAU\VoiceBank" --utau-preset -o "音源_normalized"

```

- **RMS -20dB 変換 ＋ UTAU最適化**

```bash
python utau_volume_normalizer.py "C:\path\to\wav_folder" -m rms -t -20.0 --utau-preset

```

- **ピッチを2半音上げ、速度を1.1倍にしてテスト実行（Dry-Run）**

```bash
python utau_volume_normalizer.py "C:\path\to\wav_folder" -p 2.0 --speed 1.1 --dry-run

```

---

## プラグイン拡張仕様

`Plugins/` フォルダ配下に置かれた拡張ファイルは、起動時に自動検出・読み込みされます。

- **ZIPプラグイン (`.zip`)**: `Plugins/` 内の `.zip` ファイルは `PluginsZipper/` に自動解凍・展開され、環境パス（PATH/DLL）へ登録のうえロードされます。
- **Pythonプラグイン (`.py` / `.pyd`)**:
- `register_plugin()` や `parse_uvn_file()` 関数を定義することで、オーディオデータ処理フックを追加できます。
- `register_uvn_utilities()` による組み込みユーティリティ関数の拡張が可能です。
- スクリプト側で `UI_SCHEMA` を定義することで、GUI（`uvn_gui.py`）上に設定項目を自動反映し、`plugin_params` 経由で設定値を保持できます。

- **.uvn スクリプト**: 独自形式のプラグイン定義ファイルを登録済みパーサーを介して読み込み、波形処理フィルターを自由に適用できます。

---

## ライセンス

本スクリプトおよびプロジェクト内のプラグイン（`Plugins/` 配下）に含まれるサードパーティ製ライブラリのライセンスについては、各フォルダ内のライセンスファイル（`COPYING.txt`, `LICENSE`, `README_LICENSES.md` 等）をご確認ください。
