# utau_volume_normalizer.py

import os
import sys
import argparse
import datetime
import gzip
import shutil
import threading

import tkinter as tk

from scipy.io import wavfile
from scipy.signal import resample_poly

# -------------------------------------------------------------------
# 1. 実行環境の設定とモジュールの動的ロード (dev/prod モード切り替え)
# -------------------------------------------------------------------

# 実行環境（exe化されているか通常実行か）に応じて基準ディレクトリを取得
if getattr(sys, 'frozen', False):
    # PyInstallerでexe化されている場合：exeファイルが置かれている実際のフォルダ
    current_dir = os.path.dirname(sys.executable)
else:
    # 通常のPythonスクリプト実行の場合：スクリプトがあるフォルダ
    current_dir = os.path.dirname(os.path.abspath(__file__))


class _LogTee:
    def __init__(self, terminal_stream, log_file):
        self.terminal_stream = terminal_stream
        self.log_file = log_file
        self.lock = threading.Lock()

    def write(self, message):
        with self.lock:
            self.terminal_stream.write(message)
            self.terminal_stream.flush()
            self.log_file.write(message)
            self.log_file.flush()

    def flush(self):
        with self.lock:
            self.terminal_stream.flush()
            self.log_file.flush()

    def isatty(self):
        return self.terminal_stream.isatty()


log_dir = os.path.join(current_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_name = datetime.datetime.now().strftime("uvn_%Y%m%d_%H%M%S.log")
log_path = os.path.join(log_dir, log_name)
log_file = open(log_path, "a", encoding="utf-8", buffering=1)
sys.stdout = _LogTee(sys.__stdout__, log_file)
sys.stderr = _LogTee(sys.__stderr__, log_file)
print(f"ログファイル: {log_path}")


def _finalize_session_log():
    log_file.flush()
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    log_file.close()

    if os.path.getsize(log_path) <= 10 * 1024:
        return log_path

    compressed_path = f"{log_path}.gz"
    with open(log_path, "rb") as source, gzip.open(compressed_path, "wb") as compressed:
        shutil.copyfileobj(source, compressed)
    os.remove(log_path)
    return compressed_path

# 開発中フォルダとコンパイル後フォルダのパス設定
dev_dir = os.path.join(current_dir, "core_python_files")
prod_dir = os.path.join(current_dir, "core")

# --- exe直下のルート (current_dir) を sys.path に追加して Plugins/ を認識させる ---
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# --- 1. コマンドライン引数 `--runmode` の判定 (インポート前処理) ---
runmode = None
if "--runmode" in sys.argv:
    try:
        mode_idx = sys.argv.index("--runmode") + 1
        if mode_idx < len(sys.argv):
            runmode = sys.argv[mode_idx].lower()
    except ValueError:
        pass

language = os.environ.get("UTAU_LANGUAGE")
if "--language" in sys.argv:
    language_idx = sys.argv.index("--language") + 1
    if language_idx < len(sys.argv):
        language = sys.argv[language_idx]
if language:
    os.environ["UTAU_LANGUAGE"] = language

# モードの指定状態に応じた sys.path の切り替え
if runmode == "dev":
    if os.path.exists(dev_dir):
        sys.path.insert(0, dev_dir)
        print("[runmode: dev] 開発中のコード（core_python_files）を優先読み込みします。")
    else:
        print("[Warning] --runmode dev が指定されましたが、core_python_files が見つかりません。")
        sys.path.insert(0, prod_dir)
elif runmode == "prod":
    if os.path.exists(prod_dir):
        sys.path.insert(0, prod_dir)
        print("[runmode: prod] コンパイル済みのコード（core_pyd）を優先読み込みします。")
    else:
        print("[Warning] --runmode prod が指定されましたが、core_pyd が見つかりません。")
        sys.path.insert(0, dev_dir)
else:
    # 引数未指定時はフォルダの存在確認で自動判定（フォールバック）
    if os.path.exists(dev_dir):
        sys.path.insert(0, dev_dir)
        print("開発中のコード（core_python_files）を読み込みルートに設定しました。")
    else:
        sys.path.insert(0, prod_dir)
        print("コンパイル済みのコード（core_pyd）を読み込みルートに設定しました。")

# --- ここから下のインポートは、頭の「core_pyd.」などを付けずに書く ---
# これにより、上の設定（インポートルート）に合わせて自動で中身が切り替わります
from uvn_utility import * # type: ignore
from uvn_utility import tr # type: ignore
from uvn_gui import * # type: ignore

# -------------------------------------------------------------------
# 2. エントリポイント (CLI と GUI の自動切り替え)
# -------------------------------------------------------------------
def main():
    # `--runmode` や `--command-line-mode` 以外のオプション引数があるか確認
    has_cli_flag = "--command-line-mode" in sys.argv
    has_optional_args = any(
        arg.startswith("-")
        and not arg.startswith("--runmode")
        and arg != "--language"
        for arg in sys.argv[1:]
    )
    has_input_arg = any(
        not arg.startswith("-")
        and arg not in ("dev", "prod", "ja-jp", "en-us")
        for arg in sys.argv[1:]
    )

    if has_cli_flag or has_optional_args or has_input_arg:
        cli_args = [arg for arg in sys.argv[1:] if arg != "--command-line-mode"]

        parser = argparse.ArgumentParser(description="UTAU音源用 高機能オーディオノーマライザー")
        parser.add_argument("--command-line-mode", action="store_true", help="CLIモードで実行")
        parser.add_argument("--runmode", choices=["dev", "prod"], help="実行モード指定 (dev: ソースコード / prod: .pyd)")
        parser.add_argument("--language", choices=["ja-jp", "en-us"], default=language or CURRENT_LANGUAGE, help="表示言語") # type: ignore
        parser.add_argument("input", type=str, help="対象入力フォルダのフルパス")
        parser.add_argument("-m", "--mode", choices=["peak", "rms"], default="peak")
        parser.add_argument("-t", "--target", type=float, default=None)
        parser.add_argument("-o", "--outdir", type=str, default="音源")
        parser.add_argument("-s", "--sample-rate", type=int, default=None)
        parser.add_argument("--mono", action="store_true")
        parser.add_argument("--trim", action="store_true")
        parser.add_argument("--utau-preset", action="store_true")
        parser.add_argument("--no-dc", action="store_true")
        parser.add_argument("-p", "--pitch", type=float, default=0.0)
        parser.add_argument("--speed", type=float, default=1.0)
        parser.add_argument("--backup", action="store_true", default=True)
        parser.add_argument("--nobackup", action="store_false", dest="backup")
        parser.add_argument("--dry-run", action="store_true")

        args = parser.parse_args(cli_args)
        set_language(args.language) # type: ignore

        target_val = args.target
        if target_val is None:
            target_val = -1.0 if args.mode == "peak" else -20.0

        uvn_parsers, loaded_plugins = init_plugins_environment(PLUGINS_DIR) # type: ignore

        process_exit_code = process_audio( # type: ignore
            input_dir=args.input,
            mode=args.mode,
            target_val=target_val,
            output_dirname=args.outdir,
            to_mono=args.mono or args.utau_preset,
            remove_dc=not args.no_dc,
            backup=args.backup,
            dry_run=args.dry_run,
            target_sr=44100 if args.utau_preset else args.sample_rate,
            trim=args.trim,
            force_16bit=args.utau_preset,
            pitch_shift=args.pitch,
            speed_rate=args.speed,
            loaded_plugins=loaded_plugins
        )
        return process_exit_code if isinstance(process_exit_code, int) else 0
    else:
        root = tk.Tk()
        app = NormalizerGUI(root) # type: ignore
        root.mainloop()
        return 0

if __name__ == "__main__":
    # main()

    exit_code = 0
    try:
        main_exit_code = main()
        if isinstance(main_exit_code, int):
            exit_code = main_exit_code
    except KeyboardInterrupt:
        print(tr("cli.interrupted"), file=sys.stderr)
        exit_code = 130
    except Exception as error:
        print(tr("cli.unexpected_error", error=error), file=sys.stderr)
        exit_code = 1
    finally:
        print(tr("cli.exit_code", code=exit_code))
        _finalize_session_log()
    sys.exit(exit_code)

