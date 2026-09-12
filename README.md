# UTAU Audio Normalizer（UTAU音源用オーディオノーマライザー）

UTAU音源の制作・調整・バッチ処理向けの音声処理ツールです。Tkinter GUIとCLIに対応し、WAVファイルのノーマライズ、形式変換、ピッチ・速度変更、プラグイン処理を実行できます。

## 主な機能

- Peak（ピーク / dBFS）またはRMS（実効値 / dB RMS）によるノーマライズ
- RMSモードの音割れ回避リミッター
- UTAU最適化プリセット（16-bit PCM / 44.1 kHz / モノラル）
- DCオフセット除去、前後の無音トリミング、モノラル化
- 多項式リサンプルによるサンプリングレート変換
- ピッチシフトとタイムストレッチ
- `Plugins/` 以下の`.py`、`.pyd`、`.dll`、`.zip`、`.uvn`拡張
- タイムスタンプ付きバックアップ、Dry-Run、`normalize_log.txt`出力

プラグインの詳細仕様は [Plugins/utau_volume_normalizer_plugin_decoder/README_PLUGINS.md](Plugins/utau_volume_normalizer_plugin_decoder/README_PLUGINS.md) を参照してください。

## フォルダ構成

```text
UtauAudioNormalizer/
├── Plugins/                                  # ユーザープラグイン
│   ├── rubberband/                           # rubberband実行ファイルの配置先
│   ├── testplugin/                           # .uvnサンプル
│   ├── testplugindefine/                     # Pythonユーティリティサンプル
│   ├── Language/                             # プラグイン個別翻訳
│   │   └── [PluginName]/ja-jp.lang / en-us.lang
│   └── utau_volume_normalizer_plugin_decoder/ # プラグイン仕様書
├── core_python_file/                         # 開発用Pythonモジュール
│   ├── uvn_audio.py
│   ├── uvn_gui.py
│   ├── uvn_utility.py
│   └── uvn_plugin_runtime/                   # .uvnデコーダーソース
│       ├── __init__.py
│       └── decoder.py
├── core/                                     # ビルド済み.pydの配置先
│   └── uvn_plugin_runtime/                   # ビルド時に同期
├── Language/                                 # 言語リソース（.lang）
│   ├── ja-jp.lang
│   └── en-us.lang
├── utau_volume_normalizer.py                 # GUI/CLIエントリポイント
├── setup.py                                  # CythonとPyInstallerによるビルド
├── utau_volume_normalizer_spec/              # PyInstaller spec
├── requirements.txt
└── README_DEV.md
```

`Plugins/` 以下は再帰的に走査されます。ZIPは展開されず、ZIP自体をPythonの検索パスへ追加して内部ファイルを読み込みます。通常、プラグインの配置先として`Plugins/`直下またはそのサブフォルダを使用してください。

`Language/`には画面とログの翻訳リソースを置きます。ファイル形式はUTF-8の`.lang`（1行1キーの`key=value`形式）です。GUI上の言語選択、CLIの`--language ja-jp|en-us`、または環境変数`UTAU_LANGUAGE`で切り替えられます。

実行ごとの標準出力・エラー出力は、ルートの`logs/uvn_YYYYMMDD_HHMMSS.log`へ保存されます。プラグインの読み込み結果、全WAVファイルの処理結果、エラー、終了コードも同じファイルに記録されます。

## 動作環境と依存ライブラリ

- Python 3.8以上のCPython
- `numpy`、`scipy`
- GUI使用時: Tkinter
- ピッチ・速度変更時: `librosa` または `pyrubberband`とrubberband実行ファイル

開発環境では仮想環境を作成して依存ライブラリをインストールします。

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

`requirements.txt`には実行時依存に加えて、CythonとPyInstallerも含まれます。

## 使い方

### GUI

引数なしで起動するとGUIが表示されます。

```bash
python utau_volume_normalizer.py
```

対象フォルダを選択し、ノーマライズ方式、目標値、出力先、変換オプションを指定して実行します。入力フォルダ直下の`*.wav`が処理対象です。既定では入力フォルダ内に`音源`フォルダを作成し、処理前にバックアップを作成します。

### CLI

CLIでは入力フォルダを必ず指定します。オプション引数を指定するとCLIとして判定されるため、`--command-line-mode`を明示する場合も入力フォルダを付けてください。

```bash
python utau_volume_normalizer.py "C:\path\to\wav_folder" [オプション]
```

| オプション | 短縮形 | 説明 | 既定値 |
| --- | --- | --- | --- |
| `input` | - | WAVファイルを含む入力フォルダ（必須） | - |
| `--mode` | `-m` | `peak`または`rms` | `peak` |
| `--target` | `-t` | 目標値（dB） | Peak: `-1.0` / RMS: `-20.0` |
| `--outdir` | `-o` | 出力フォルダ名 | `音源` |
| `--sample-rate` | `-s` | 出力サンプリングレート（Hz） | 変更なし |
| `--mono` | - | モノラル化 | 無効 |
| `--trim` | - | 前後の無音区間をトリミング | 無効 |
| `--utau-preset` | - | 16-bit / 44.1 kHz / モノラルへ変換 | 無効 |
| `--no-dc` | - | DCオフセット除去を無効化 | 除去する |
| `--pitch` | `-p` | ピッチ変更（半音） | `0.0` |
| `--speed` | - | 速度倍率 | `1.0` |
| `--nobackup` | - | 自動バックアップを無効化 | 作成する |
| `--dry-run` | - | ファイルを書き込まずに処理 | 無効 |
| `--runmode` | - | `dev`または`prod`を選択 | 自動判定 |
| `--command-line-mode` | - | CLIモードを明示 | 自動判定 |
| `--language` | - | 表示言語（`ja-jp`または`en-us`） | OSのシステム言語 |

使用例:

```bash
python utau_volume_normalizer.py "C:\path\to\wav_folder" -m peak -t -1.0
python utau_volume_normalizer.py "D:\UTAU\VoiceBank" --utau-preset -o "音源_normalized"
python utau_volume_normalizer.py "C:\path\to\wav_folder" -m rms -t -20.0 --dry-run
python utau_volume_normalizer.py "C:\path\to\wav_folder" -p 2.0 --speed 1.1
```

## プラグイン

起動時に`Plugins/`以下が走査されます。

- `.uvn`: Pythonスクリプト形式または限定的なINI形式の音声処理フック
- `.py`: `register_uvn_utilities()`が返す辞書による共有ユーティリティ登録。`register_plugin()`にも対応
- `.pyd`: Python拡張モジュール。`register_uvn_utilities()`または`register_plugin()`に対応
- `.dll`: `process_audio_c`をエクスポートしている場合、`dll_<ファイル名>`として登録
- `.zip`: 展開せず、内部の対応ファイルを読み込み

Python形式の`.uvn`では`UI_SCHEMA`によるGUI入力を定義できます。INI形式は`to_mono`、`gain_offset_db`、`low_cut_hz`に対応します。プラグインはサンドボックスではなく通常のPythonコードとして実行されるため、信頼できるファイルだけを使用してください。

## ライセンス

本プロジェクトはMIT Licenseです。`Plugins/`に含まれるサードパーティ製ソフトウェアについては、各フォルダのライセンスファイルを確認してください。
