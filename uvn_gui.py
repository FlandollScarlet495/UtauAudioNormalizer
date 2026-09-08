# uvn_gui.py

import os
import tkinter as tk
import threading
from tkinter import ttk, filedialog, messagebox

from uvn_utility import *
from uvn_audio import *

# -------------------------------------------------------------------
# GUI クラス定義 (Tkinter)
# -------------------------------------------------------------------
class NormalizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("UTAU 音源用 オーディオノーマライザー GUI")
        self.root.geometry("680x850")
        self.root.minsize(620, 700)

        self.plugin_ui_vars = {}  # プラグインUIの入力値を保持

        # プラグイン初期化
        self.uvn_parsers, self.loaded_plugins = init_plugins_environment(
            PLUGINS_DIR, PLUGINS_ZIPPER_DIR, log_func=self.log_init
        )

        self._create_widgets()

    def log_init(self, msg):
        print(msg)

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. フォルダ選択エリア
        folder_frame = ttk.LabelFrame(main_frame, text=" 対象フォルダ選択 ", padding="10")
        folder_frame.pack(fill=tk.X, pady=5)

        self.input_dir_var = tk.StringVar()
        ttk.Entry(folder_frame, textvariable=self.input_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(folder_frame, text="参照...", command=self.browse_folder).pack(side=tk.RIGHT)

        # 2. ノーマライズ設定
        norm_frame = ttk.LabelFrame(main_frame, text=" ノーマライズ設定 ", padding="10")
        norm_frame.pack(fill=tk.X, pady=5)

        ttk.Label(norm_frame, text="方式:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.mode_var = tk.StringVar(value="peak")
        mode_cb = ttk.Combobox(norm_frame, textvariable=self.mode_var, values=["peak", "rms"], state="readonly", width=8)
        mode_cb.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        mode_cb.bind("<<ComboboxSelected>>", self.on_mode_change)

        ttk.Label(norm_frame, text="目標値 (dB):").grid(row=0, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.target_var = tk.StringVar(value="-1.0")
        ttk.Entry(norm_frame, textvariable=self.target_var, width=8).grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)

        ttk.Label(norm_frame, text="出力先フォルダ名:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.outdir_var = tk.StringVar(value="音源")
        ttk.Entry(norm_frame, textvariable=self.outdir_var, width=15).grid(row=1, column=1, columnspan=3, sticky=tk.W, padx=5, pady=2)

        # 3. 音質・変換オプション
        opt_frame = ttk.LabelFrame(main_frame, text=" 変換＆編集オプション ", padding="10")
        opt_frame.pack(fill=tk.X, pady=5)

        self.utau_preset_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="UTAU最適化プリセット (16bit / 44.1kHz / Mono 固定)", 
                        variable=self.utau_preset_var, command=self.on_utau_preset_toggle).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=2)

        self.mono_var = tk.BooleanVar(value=False)
        self.chk_mono = ttk.Checkbutton(opt_frame, text="モノラル化", variable=self.mono_var)
        self.chk_mono.grid(row=1, column=0, sticky=tk.W, pady=2)

        self.remove_dc_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="DCオフセット除去", variable=self.remove_dc_var).grid(row=1, column=1, sticky=tk.W, pady=2)

        self.trim_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="無音トリミング", variable=self.trim_var).grid(row=1, column=2, sticky=tk.W, pady=2)

        ttk.Label(opt_frame, text="サンプリングレート(Hz):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.sr_var = tk.StringVar(value="")
        self.ent_sr = ttk.Entry(opt_frame, textvariable=self.sr_var, width=10)
        self.ent_sr.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(opt_frame, text="ピッチ変更(半音):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.pitch_var = tk.StringVar(value="0.0")
        ttk.Entry(opt_frame, textvariable=self.pitch_var, width=8).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(opt_frame, text="速度(倍率):").grid(row=3, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.speed_var = tk.StringVar(value="1.0")
        ttk.Entry(opt_frame, textvariable=self.speed_var, width=8).grid(row=3, column=3, sticky=tk.W, padx=5, pady=2)

        # 実行オプション (バックアップ・Dry-Run)
        exec_opt_frame = ttk.Frame(opt_frame)
        exec_opt_frame.grid(row=4, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))

        self.backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(exec_opt_frame, text="自動バックアップ作成", variable=self.backup_var).pack(side=tk.LEFT, padx=(0, 15))

        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(exec_opt_frame, text="試行実行 (Dry-Run)", variable=self.dry_run_var).pack(side=tk.LEFT)

        # 4. プラグイン自動生成GUIエリア (UI_SCHEMA対応)
        has_plugin_ui = any(isinstance(p, dict) and p.get("ui_schema") for p in self.loaded_plugins)
        if has_plugin_ui:
            plugin_frame = ttk.LabelFrame(main_frame, text=" プラグイン拡張設定 ", padding="10")
            plugin_frame.pack(fill=tk.X, pady=5)

            r = 0
            for plugin in self.loaded_plugins:
                if not isinstance(plugin, dict) or not plugin.get("ui_schema"):
                    continue

                p_name = plugin.get("name", "Plugin")
                self.plugin_ui_vars[p_name] = {}

                ttk.Label(plugin_frame, text=f"■ {p_name}", font=("", 9, "bold")).grid(row=r, column=0, columnspan=4, sticky=tk.W, pady=(5, 2))
                r += 1

                for item in plugin["ui_schema"]:
                    key = item.get("key")
                    label = item.get("label", key)
                    default_val = item.get("default", "")
                    item_type = item.get("type", "entry")

                    ttk.Label(plugin_frame, text=f"{label}:").grid(row=r, column=0, sticky=tk.W, padx=(10, 5), pady=2)

                    if item_type == "checkbox":
                        var = tk.BooleanVar(value=bool(default_val))
                        chk = ttk.Checkbutton(plugin_frame, variable=var)
                        chk.grid(row=r, column=1, sticky=tk.W, pady=2)
                    else:
                        var = tk.StringVar(value=str(default_val))
                        ent = ttk.Entry(plugin_frame, textvariable=var, width=12)
                        ent.grid(row=r, column=1, sticky=tk.W, pady=2)

                    self.plugin_ui_vars[p_name][key] = var
                    r += 1

        # 5. 実行ボタン & プログレスバー
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)

        self.run_button = ttk.Button(action_frame, text="処理を開始する", command=self.start_processing)
        self.run_button.pack(fill=tk.X, ipady=5)

        self.progress = ttk.Progressbar(action_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, pady=5)

        # 6. ログ表示エリア
        log_frame = ttk.LabelFrame(main_frame, text=" 処理ログ ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_dir_var.set(folder)

    def on_mode_change(self, event=None):
        if self.mode_var.get() == "peak":
            self.target_var.set("-1.0")
        else:
            self.target_var.set("-20.0")

    def on_utau_preset_toggle(self):
        if self.utau_preset_var.get():
            self.mono_var.set(True)
            self.chk_mono.config(state="disabled")
            self.sr_var.set("44100")
            self.ent_sr.config(state="disabled")
        else:
            self.chk_mono.config(state="normal")
            self.ent_sr.config(state="normal")

    def log(self, msg):
        def _append():
            self.log_text.insert(tk.END, str(msg) + "\n")
            self.log_text.see(tk.END)
        self.root.after(0, _append)

    def update_progress(self, current, total):
        def _update():
            self.progress["maximum"] = total
            self.progress["value"] = current
        self.root.after(0, _update)

    def collect_plugin_params(self):
        collected = {}
        for p_name, keys in self.plugin_ui_vars.items():
            collected[p_name] = {}
            for k, var in keys.items():
                collected[p_name][k] = var.get()
        return collected

    def start_processing(self):
        input_dir = self.input_dir_var.get().strip().strip('\'"')
        if not input_dir or not os.path.exists(input_dir):
            messagebox.showerror("エラー", "有効な対象フォルダを選択してください。")
            return

        try:
            target_val = float(self.target_var.get())
            pitch_shift = float(self.pitch_var.get())
            speed_rate = float(self.speed_var.get())
            
            sr_str = self.sr_var.get().strip()
            target_sr = int(sr_str) if sr_str else None
        except ValueError:
            messagebox.showerror("エラー", "数値の入力形式が不正です。確認してください。")
            return

        plugin_params = self.collect_plugin_params()

        self.run_button.config(state="disabled")
        self.log_text.delete("1.0", tk.END)
        self.progress["value"] = 0

        # UIフリーズ回避のためにスレッド処理
        threading.Thread(
            target=self._worker,
            args=(input_dir, target_val, target_sr, pitch_shift, speed_rate, plugin_params),
            daemon=True
        ).start()

    def _worker(self, input_dir, target_val, target_sr, pitch_shift, speed_rate, plugin_params):
        try:
            is_utau = self.utau_preset_var.get()
            process_audio(
                input_dir=input_dir,
                mode=self.mode_var.get(),
                target_val=target_val,
                output_dirname=self.outdir_var.get().strip() or "音源",
                to_mono=self.mono_var.get() or is_utau,
                remove_dc=self.remove_dc_var.get(),
                backup=self.backup_var.get(),
                dry_run=self.dry_run_var.get(),
                target_sr=44100 if is_utau else target_sr,
                trim=self.trim_var.get(),
                force_16bit=is_utau,
                pitch_shift=pitch_shift,
                speed_rate=speed_rate,
                loaded_plugins=self.loaded_plugins,
                plugin_params=plugin_params,
                log_func=self.log,
                progress_func=self.update_progress
            )
        except Exception as e:
            self.log(f"\n❌ 予期せぬエラーが発生しました: {e}")
        finally:
            self.root.after(0, lambda: self.run_button.config(state="normal"))
