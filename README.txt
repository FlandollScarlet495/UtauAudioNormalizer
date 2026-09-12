UTAU Audio Normalizer
UTAU音源用オーディオノーマライザー

一般ユーザー向け説明書
======================

1. このソフトについて
----------------------
UTAU Audio Normalizerは、UTAU音源用のWAVファイルをまとめて処理するソフトウェアです。
音量の統一、サンプリングレート変換、モノラル化、無音トリミングなどをGUIまたはコマンドラインから実行できます。

2. 主な機能
------------
・Peak（ピーク）またはRMS（実効値）による音量ノーマライズ
・RMS処理時の音割れ回避
・UTAU向け形式への一括変換（16-bit PCM、44.1 kHz、モノラル）
・DCオフセット除去
・前後の無音区間トリミング
・サンプリングレート変換
・モノラル化
・ピッチ変更（半音単位）
・再生速度変更
・処理前の自動バックアップ
・Dry-Run（ファイルを書き込まない試行実行）
・処理結果ログの出力
・プラグインによる機能拡張

3. 動作環境
------------
・Windows
・Python 3.8以上（Python版を実行する場合）
・numpy、scipy
・Tkinter（GUIを使用する場合）

ピッチ変更または速度変更を使用する場合は、librosaまたはpyrubberbandが必要です。
必要なライブラリは、配布物に含まれるrequirements.txtからインストールできます。

  python -m pip install -r requirements.txt

すでにexe版が用意されている場合は、通常Pythonのインストールは必要ありません。

4. GUIで使用する
-----------------
引数を付けずに起動するとGUIが表示されます。

  python utau_volume_normalizer.py

exe版では、utau_volume_normalizer.exeを起動してください。

基本的な手順:

  1. 「参照」ボタンでWAVファイルが入ったフォルダを選択します。
  2. ノーマライズ方式を選択します。
  3. 目標値を入力します。
  4. 必要に応じて変換オプションを設定します。
  5. 「処理を開始する」を押します。

入力フォルダ直下にあるWAVファイルが処理対象です。
処理結果は、既定では入力フォルダ内の「音源」フォルダへ保存されます。

5. ノーマライズ方式
--------------------
Peak:
  音声の最大ピークを目標値へ合わせます。
  既定値は-1.0 dBFSです。

RMS:
  音声の平均的な音量を目標値へ合わせます。
  既定値は-20.0 dB RMSです。
  音割れの可能性がある場合は自動的にゲインを制限します。

目標値は、通常は負のdB値を指定します。

6. UTAU最適化プリセット
------------------------
「UTAU最適化プリセット」を有効にすると、次の形式で出力されます。

  ・16-bit PCM
  ・44.1 kHz
  ・モノラル

UTAUで使用する音源をまとめて整える場合に便利です。

7. CLIで使用する
-----------------
入力フォルダを指定して起動するとCLIモードになります。

  python utau_volume_normalizer.py "C:\path\to\wav_folder" [オプション]

主なオプション:

  -m, --mode peak|rms       ノーマライズ方式
  -t, --target 数値         目標値（dB）
  -o, --outdir フォルダ名   出力フォルダ名
  -s, --sample-rate 数値    出力サンプリングレート
      --mono                モノラル化
      --trim                前後の無音区間をトリミング
      --utau-preset         UTAU向け形式へ変換
      --no-dc               DCオフセット除去を無効化
  -p, --pitch 数値          ピッチ変更（半音）
      --speed 数値          再生速度の倍率
      --nobackup             自動バックアップを作成しない
      --dry-run              ファイルを書き込まず試行する
      --command-line-mode    CLIモードを明示する
      --runmode dev|prod     使用する実行モジュールを指定する

使用例:

  python utau_volume_normalizer.py "C:\VoiceBank" -m peak -t -1.0
  python utau_volume_normalizer.py "C:\VoiceBank" --utau-preset -o "音源_normalized"
  python utau_volume_normalizer.py "C:\VoiceBank" -m rms -t -20.0 --dry-run
  python utau_volume_normalizer.py "C:\VoiceBank" -p 2.0 --speed 1.1

8. バックアップと出力
----------------------
バックアップを有効にすると、処理開始前に入力フォルダ内へ次の形式のフォルダを作成します。

  _backup_YYYYMMDD_HHMMSS

出力先には処理済みWAVとnormalize_log.txtが保存されます。
Dry-Runを有効にした場合、出力フォルダやバックアップを作成せず、処理内容だけを確認します。

9. プラグイン
-------------
Pluginsフォルダにプラグインを配置すると、起動時に自動的に読み込まれます。

  ・.uvn  : 音声処理プラグイン（Python形式または簡易INI形式）
  ・.py   : 共有ユーティリティや処理プラグイン
  ・.pyd  : Python拡張モジュール
  ・.dll  : process_audio_cを公開するネイティブ拡張
  ・.zip  : 対応プラグインをまとめたアーカイブ

ZIPは自動展開されず、内部のファイルが直接読み込まれます。
Python形式の.uvnでは、設定項目をGUIへ追加することもできます。
詳しい仕様はPlugins\utau_volume_normalizer_plugin_decoder\README_PLUGINS.mdを参照してください。デコーダー本体はuvn_plugin_runtime\decoder.pyにあります。

プラグインは通常のPythonコードとして実行されます。内容を確認した信頼できるプラグインだけを使用してください。

10. 注意事項
-------------
・処理対象は入力フォルダ直下のWAVファイルです。サブフォルダ内は自動処理されません。
・出力先フォルダを入力フォルダ内に指定した場合、既存の同名ファイルが上書きされる可能性があります。
・大切な音源を処理する前に、自動バックアップが有効になっていることを確認してください。
・ピッチ変更や速度変更には追加ライブラリと、設定によってはrubberband実行ファイルが必要です。
・異なるPythonバージョンやCPUアーキテクチャ向けに作成された.pydは使用できません。

11. ライセンス
--------------
本ソフトウェアはMIT Licenseで公開されています。
Pluginsフォルダ内のサードパーティ製ソフトウェアについては、各フォルダにあるライセンスファイルを確認してください。
