# UTAU Audio Normalizer 開発者向けガイド

開発用ソースの実行、サンドボックス環境による動作テスト、Cythonによる`.pyd`ビルド、PyInstallerによる配布物の作成方法を説明します。

## ディレクトリ構成

```text
UtauAudioNormalizer/
├── core_python_file/                 # 開発用Pythonモジュール
│   ├── uvn_audio.py
│   ├── uvn_gui.py
│   ├── uvn_utility.py
│   └── uvn_plugin_runtime/           # .uvnデコーダーソース
│       ├── __init__.py
│       └── decoder.py
├── core/                             # Cython生成物（.pyd）
│   └── uvn_plugin_runtime/           # ビルド時に同期
├── Plugins/                          # プラグインと関連ライブラリ
│   ├── rubberband/
│   ├── testplugin/
│   ├── testplugindefine/
│   └── utau_volume_normalizer_plugin_decoder/ # プラグイン仕様書
├── Language/                         # UTF-8 .lang翻訳リソース
│   ├── ja-jp.lang
│   └── en-us.lang
├── utau_volume_normalizer.py         # GUI/CLIエントリポイント
├── uvn_tester.py                     # テスト・サンドボックス用ツール
├── setup.py                          # Cython、PyInstaller、配布物整理
├── utau_volume_normalizer_spec/
│   └── utau_volume_normalizer.spec   # PyInstaller設定
├── requirements.txt
├── README.md
└── README_DEV.md

```

`core_python_file/`と`core/`は実行モードで使い分けます。`Plugins/`はソース実行時にも配布用exe実行時にも、実行ファイルまたはスクリプトの横へ配置します。

---

## 開発環境の準備

Python 3.8以上のCPythonと、依存ライブラリを使用します。WindowsでCythonから`.pyd`を生成するには、Visual Studio Build ToolsまたはVisual Studioの「C++によるデスクトップ開発」が必要です。

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt

```

`requirements.txt`には、実行時の`numpy`・`scipy`・音声処理ライブラリに加えて、ビルド用のCythonとPyInstallerが含まれます。

---

## ソース実行

引数なしで起動するとGUIになります。

```bash
python utau_volume_normalizer.py

```

CLIを使用する場合は入力フォルダを指定します。`--runmode`だけを指定したコマンドは入力フォルダがないため、CLIとしては完結しません。

```bash
python utau_volume_normalizer.py "C:\path\to\wav_folder" --runmode dev --dry-run
python utau_volume_normalizer.py "C:\path\to\wav_folder" --runmode prod --dry-run
python utau_volume_normalizer.py "C:\path\to\wav_folder" --language en-us --dry-run

```

* `dev`: `core_python_file/`を優先して読み込みます。
* `prod`: `core/`を優先して読み込みます。
* 未指定時: `core_python_file/`が存在すれば`dev`相当、なければ`core/`を使用します。
* 言語は`--language ja-jp|en-us`、または環境変数`UTAU_LANGUAGE`で指定できます。GUIでは画面上部の選択欄から変更できます。

CLI経路とGUI経路は、`init_plugins_environment(PLUGINS_DIR)`を使用します。標準出力と標準エラーはエントリポイントで`logs/uvn_YYYYMMDD_HHMMSS.log`へ複製され、プラグイン出力や全WAVの処理ログも保存されます。

---

## テスト・サンドボックス環境 (`uvn_tester.py`)

開発中の処理ロジック（`uvn_audio.py`）やプラグイン動作を安全に実験・検証するためのテストツールです。実行時に一時的なテスト用ダミー音源（標準モノラル、DC偏り＋ノイズ含むステレオ、無音区間付き、大音量ピーク）を自動生成し、全パラメータの組み合わせ受入テストを行えます。

### 1. クイック標準テスト (CLI)

標準構成でダミー音源生成から音声処理パイプライン、結果の検証、クリーンアップまでを一撃で検証します。

```bash
python uvn_tester.py

```

### 2. パラメータ指定テスト (CLI)

各種引数を指定して、特定処理（RMSモード、サンプリングレート変換、プロファイル処理、並列数など）のサンドボックステストが可能です。

```bash
# RMSノーマライズ (-12dBFS)、48kHz変換、母音プロファイル指定で実行し、生成ファイルをフォルダに残す
python uvn_tester.py --mode rms --target -12.0 --sr 48000 --profile vowel --keep

# 実際の実ファイル書き出しを行わない Dry-Run テスト
python uvn_tester.py --dry-run

```

#### 主なCLIオプション一覧

* `--mode {peak,rms}` : 処理モード（デフォルト: `peak`）
* `--target FLOAT` : 目標dBFS値（デフォルト: `-1.0`）
* `--profile {none,vowel,consonant}` : プロファイル処理設定（デフォルト: `none`）
* `--sr INT` : 出力サンプリングレート（`0`で変更なし、デフォルト: `44100`）
* `--pitch FLOAT` / `--speed FLOAT` : ピッチ変更（半音）/ 速度変更倍率
* `--workers INT` : 最大並列スレッド数（`0`で自動調整）
* `--dry-run` : ファイル生成なしのシミュレーション実行
* `--no-mono` / `--no-dc` / `--no-trim` : モノラル化 / DCオフセット除去 / 無音トリミングの無効化
* `--keep` : テスト終了後も生成音源および出力結果のフォルダ（`_test_sandbox_wavs/`）を維持

### 3. ポチポチ試せる GUI コントロールパネル

`--gui` オプションを付けて実行すると、画面上で全パラメータを視覚的にいじりながらテストできる操作パネルが立ち上がります。

```bash
python uvn_tester.py --gui

```

---

## ビルド

ビルドはリポジトリのルートで実行します。

```bash
python setup.py build_ext --inplace

```

このコマンドは単なるCythonコンパイルではなく、次の処理を一括して実行します。

1. 既存の`UtauVolumeNormalizer/`を削除して配布フォルダを作成
2. `core_python_file/uvn_audio.py`、`uvn_gui.py`、`uvn_utility.py`をCythonでコンパイル
3. 生成された`.pyd`をルートから`core/`へ移動
4. 生成された`.c`と`build/`を削除
5. `utau_volume_normalizer.spec`でPyInstallerを実行
6. `dist/utau_volume_normalizer.exe`、`core/`、`Plugins/`、`LICENSE`、`README.md`を`UtauVolumeNormalizer/`へ集約
7. 配布フォルダ内のrubberband実行ファイル、DLL、`COPYING.txt`を削除

そのため、実行前に`UtauVolumeNormalizer/`の必要な変更を退避してください。`setup.py`のエラー処理でも`UtauVolumeNormalizer/`、`dist/`、`build/`などを削除します。

### 成果物

Windowsでは、主な成果物は次の場所に作成されます。

```text
UtauVolumeNormalizer/
├── utau_volume_normalizer.exe
├── core/
├── Plugins/
├── LICENSE
└── README.md

```

`utau_volume_normalizer.spec`はWindowsでは`.exe`を生成し、macOSでは`.app`定義も持ちます。ただし、現在の`setup.py`の成果物集約処理は`dist/utau_volume_normalizer.exe`を前提としているため、標準のビルド手順はWindows向けです。

`setup.py`は`Language/`を配布フォルダへコピーし、specファイルでもPyInstallerデータとして登録します。配布後に翻訳だけを変更する場合は、exeと同じ場所の`Language/*.lang`を編集できます。

---

## `.pyd`の互換性

`.pyd`はビルドした環境と互換性のある実行環境で使用してください。少なくとも次の条件を揃える必要があります。

* 同じOS
* 同じCPUアーキテクチャ
* 互換性のあるCPythonのメジャー・マイナーバージョン
* 互換性のあるCランタイムと依存ライブラリ

ファイル名の例に含まれる`cp310`などはPython ABI、`win_amd64`などはOSとアーキテクチャを表します。別のPythonバージョンやアーキテクチャ向けにビルドした`.pyd`は使用できません。

---

## PyInstaller設定

`utau_volume_normalizer_spec/utau_volume_normalizer.spec`は、ルートの`utau_volume_normalizer.py`をエントリポイントとして解析します。`tkinter`、`scipy`などの隠しインポートを指定しています。

単独でPyInstallerだけを実行する場合は、次のコマンドです。

```bash
python -m PyInstaller utau_volume_normalizer_spec/utau_volume_normalizer.spec --noconfirm

```

ただし、単独実行では`core/`や`Plugins/`のコピー、配布フォルダの整理は行われません。配布物を作る場合は`setup.py`の一括処理を使用します。

---

## プラグイン開発

プラグインの詳細は [Plugins/utau_volume_normalizer_plugin_decoder/README_PLUGINS.md](https://www.google.com/search?q=Plugins/utau_volume_normalizer_plugin_decoder/README_PLUGINS.md) を参照してください。デコーダー本体は開発時は`core_python_file/uvn_plugin_runtime/decoder.py`、ビルド後は`core/uvn_plugin_runtime/decoder.py`にあります。

要点は次のとおりです。

* `Plugins/`以下は再帰的に走査されます。
* `.py`と`.pyd`は`register_uvn_utilities()`または`register_plugin()`に対応します。
* `.uvn`は登録済みパーサーで読み込まれます。
* `.dll`は`process_audio_c`をエクスポートしている場合に登録されます。
* `.zip`は自動展開されず、ZIP自体を検索パスへ追加して読み込まれます。

---

## モジュールのパス解決

`utau_volume_normalizer.py`は起動時にプロジェクトルート、`core_python_file/`または`core/`を`sys.path`へ追加します。そのため、モジュール間のインポートは次のように記述します。

```python
from uvn_utility import *
from uvn_audio import *

```

`core.uvn_utility`のようなパッケージ接頭辞は付けません。`uvn_utility.py`では次の`BASE_DIR`により、`core_python_file/`または`core/`からプロジェクトルートへ戻って`Plugins/`を参照します。

```python
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

```
