# utau_volume_normalizer.py

import sys
import argparse

import tkinter as tk

from uvn_utility import *
from uvn_audio import *
from uvn_gui import *

# -------------------------------------------------------------------
# 5. エントリポイント (CLI と GUI の自動切り替え)
# -------------------------------------------------------------------
def main():
    has_cli_flag = "--command-line-mode" in sys.argv
    has_optional_args = any(arg.startswith("-") for arg in sys.argv[1:])

    if has_cli_flag or has_optional_args:
        cli_args = [arg for arg in sys.argv[1:] if arg != "--command-line-mode"]

        parser = argparse.ArgumentParser(description="UTAU音源用 高機能オーディオノーマライザー")
        parser.add_argument("--command-line-mode", action="store_true", help="CLIモードで実行")
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

        target_val = args.target
        if target_val is None:
            target_val = -1.0 if args.mode == "peak" else -20.0

        uvn_parsers, loaded_plugins = init_plugins_environment(PLUGINS_DIR, PLUGINS_ZIPPER_DIR)

        process_audio(
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
    else:
        root = tk.Tk()
        app = NormalizerGUI(root)
        root.mainloop()

if __name__ == "__main__":
    main()
