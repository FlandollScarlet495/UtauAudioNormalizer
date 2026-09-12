# uvn_gui.py

import os
import tkinter as tk
import threading
import tkinter.ttk as ttk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from uvn_utility import *
from uvn_utility import CURRENT_LANGUAGE, get_available_languages, set_language, tr
from uvn_audio import *

# -------------------------------------------------------------------
# 1. GUI クラス定義 (Tkinter)
# -------------------------------------------------------------------
class NormalizerGUI:
    def __init__(self, root):
        self.root = root
        self.language_code = CURRENT_LANGUAGE
        self.root.title(tr("app.title"))
        self.root.geometry("680x850")
        self.root.minsize(620, 700)
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self.root.bind_all("<Control-w>", self.close_window)

        self.plugin_ui_vars = {}  # プラグインUIの入力値を保持

        # プラグイン初期化
        self.uvn_parsers, self.loaded_plugins = init_plugins_environment(
            PLUGINS_DIR, log_func=self.log_init
        )

        self._create_widgets()

    def log_init(self, msg):
        print(msg)

    def browse_folder(self):
        """入力元フォルダ選択"""
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.input_dir_var.set(dir_path)

    def browse_file(self):
        """入力元ファイル選択"""
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav;*.mp3;*.flac;*.ogg"), ("All files", "*.*")])
        if file_path:
            self.input_dir_var.set(file_path)

    def browse_outdir(self):
        """出力先フォルダ選択"""
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.outdir_var.set(dir_path)

    def _create_widgets(self):
        # 画面全体を管理する Notebook (タブ) の作成
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 【タブ1】メイン操作画面
        main_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(main_tab, text=f" {tr('gui.tabs.main')} ")

        language_frame = ttk.Frame(main_tab)
        language_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(language_frame, text=tr("language.label")).pack(side=tk.LEFT)
        self.language_options = {
            "ja-jp": tr("language.ja"),
            "en-us": tr("language.en"),
        }
        self.language_var = tk.StringVar(value=self.language_options[self.language_code])
        language_cb = ttk.Combobox(
            language_frame,
            textvariable=self.language_var,
            values=list(self.language_options.values()),
            state="readonly",
            width=18,
        )
        language_cb.pack(side=tk.LEFT, padx=5)
        language_cb.bind("<<ComboboxSelected>>", self.on_language_change)

        # --- 1. フォルダ / ファイル選択エリア ---
        folder_frame = ttk.LabelFrame(main_tab, text=f" {tr('gui.frames.input_folder')} ", padding="10")
        folder_frame.pack(fill=tk.X, pady=5)

        self.input_dir_var = tk.StringVar()
        ttk.Entry(folder_frame, textvariable=self.input_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # フォルダ選択とファイル選択のボタンを両方配置
        ttk.Button(folder_frame, text=tr("gui.buttons.browse_file"), command=self.browse_file).pack(side=tk.RIGHT, padx=(2, 0))
        ttk.Button(folder_frame, text=tr("gui.buttons.browse_folder"), command=self.browse_folder).pack(side=tk.RIGHT)

        # --- 2. ノーマライズ設定 ---
        norm_frame = ttk.LabelFrame(main_tab, text=f" {tr('gui.frames.normalize')} ", padding="10")
        norm_frame.pack(fill=tk.X, pady=5)

        ttk.Label(norm_frame, text=tr("gui.labels.mode")).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.mode_var = tk.StringVar(value="peak")
        mode_cb = ttk.Combobox(norm_frame, textvariable=self.mode_var, values=["peak", "rms"], state="readonly", width=8)
        mode_cb.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        mode_cb.bind("<<ComboboxSelected>>", self.on_mode_change)

        ttk.Label(norm_frame, text=tr("gui.labels.target_db")).grid(row=0, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.target_var = tk.StringVar(value="-1.0")
        ttk.Entry(norm_frame, textvariable=self.target_var, width=8).grid(row=0, column=3, sticky=tk.W, padx=5, pady=2)

        # 出力先フォルダ（テキスト入力 + 参照ボタン）
        ttk.Label(norm_frame, text=tr("gui.labels.output_folder")).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.outdir_var = tk.StringVar(value="")
        ttk.Entry(norm_frame, textvariable=self.outdir_var).grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        ttk.Button(norm_frame, text=tr("gui.buttons.browse_folder"), command=self.browse_outdir).grid(row=1, column=3, sticky=tk.W, padx=(2, 0), pady=2)

        # グリッドの幅可変設定
        norm_frame.columnconfigure(1, weight=1)

        # --- 3. 音質・変換オプション ---
        opt_frame = ttk.LabelFrame(main_tab, text=f" {tr('gui.frames.options')} ", padding="10")
        opt_frame.pack(fill=tk.X, pady=5)

        self.utau_preset_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text=tr("gui.options.utau_preset"), 
                        variable=self.utau_preset_var, command=self.on_utau_preset_toggle).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=2)

        self.mono_var = tk.BooleanVar(value=False)
        self.chk_mono = ttk.Checkbutton(opt_frame, text=tr("gui.options.mono"), variable=self.mono_var)
        self.chk_mono.grid(row=1, column=0, sticky=tk.W, pady=2)

        self.remove_dc_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text=tr("gui.options.remove_dc"), variable=self.remove_dc_var).grid(row=1, column=1, sticky=tk.W, pady=2)

        self.trim_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text=tr("gui.options.trim"), variable=self.trim_var).grid(row=1, column=2, sticky=tk.W, pady=2)

        ttk.Label(opt_frame, text=tr("gui.labels.sample_rate")).grid(row=2, column=0, sticky=tk.W, pady=2)
        self.sr_var = tk.StringVar(value="")
        self.ent_sr = ttk.Entry(opt_frame, textvariable=self.sr_var, width=10)
        self.ent_sr.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(opt_frame, text=tr("gui.labels.pitch")).grid(row=3, column=0, sticky=tk.W, pady=2)
        self.pitch_var = tk.StringVar(value="0.0")
        ttk.Entry(opt_frame, textvariable=self.pitch_var, width=8).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(opt_frame, text=tr("gui.labels.speed")).grid(row=3, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.speed_var = tk.StringVar(value="1.0")
        ttk.Entry(opt_frame, textvariable=self.speed_var, width=8).grid(row=3, column=3, sticky=tk.W, padx=5, pady=2)

        # 実行オプション
        exec_opt_frame = ttk.Frame(opt_frame)
        exec_opt_frame.grid(row=4, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))

        self.backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(exec_opt_frame, text=tr("gui.options.backup"), variable=self.backup_var).pack(side=tk.LEFT, padx=(0, 15))

        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(exec_opt_frame, text=tr("gui.options.dry_run"), variable=self.dry_run_var).pack(side=tk.LEFT)

        # --- 4. プラグイン自動生成GUIエリア (UI_SCHEMA対応) ---
        # A. メイン画面内に配置するプラグイン (ui_target == "main")
        main_plugins = [
            p for p in self.loaded_plugins 
            if isinstance(p, dict) and p.get("ui_schema") and p.get("ui_target", "main") == "main"
        ]

        if main_plugins:
            plugin_frame = ttk.LabelFrame(main_tab, text=f" {tr('gui.frames.plugin')} ", padding="10")
            plugin_frame.pack(fill=tk.X, pady=5)

            r = 0
            for plugin in main_plugins:
                p_name = plugin.get("name", "Plugin")
                d_name = plugin.get("display_name", p_name)  # DISPLAY_NAMEが無ければPLUGIN_NAME
                self.plugin_ui_vars[p_name] = {}

                ttk.Label(plugin_frame, text=f"■ {d_name}", font=("", 9, "bold")).grid(row=r, column=0, columnspan=4, sticky=tk.W, pady=(5, 2))
                r += 1

                r = self._build_schema_inputs(plugin_frame, plugin, p_name, start_row=r)

        # B. 独立したタブとして配置するプラグイン (ui_target == "tab")
        tab_plugins = [
            p for p in self.loaded_plugins 
            if isinstance(p, dict) and p.get("ui_schema") and p.get("ui_target") == "tab"
        ]

        for plugin in tab_plugins:
            p_name = plugin.get("name", "Plugin")
            d_name = plugin.get("display_name", p_name)
            self.plugin_ui_vars[p_name] = {}

            # 新規タブを追加（タブ名は [表示名]）
            p_tab = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(p_tab, text=f" {d_name} ")

            p_group = ttk.LabelFrame(p_tab, text=f" {tr('gui.frames.plugin_parameters', name=d_name)} ", padding="10")
            p_group.pack(fill=tk.X, pady=5)

            self._build_schema_inputs(p_group, plugin, p_name, start_row=0)

        # --- 5. 実行ボタン & プログレスバー (メインタブ内) ---
        action_frame = ttk.Frame(main_tab)
        action_frame.pack(fill=tk.X, pady=10)

        self.run_button = ttk.Button(action_frame, text=tr("gui.buttons.start"), command=self.start_processing)
        self.run_button.pack(fill=tk.X, ipady=5)

        self.progress = ttk.Progressbar(action_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, pady=5)

        # --- 6. ログ表示エリア (メインタブ内) ---
        log_frame = ttk.LabelFrame(main_tab, text=f" {tr('gui.frames.log')} ", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def _build_schema_inputs(self, parent_frame, plugin, p_name, start_row=0):
        """UI_SCHEMA からフォーム要素を共通生成するヘルパーメソッド"""
        r = start_row
        for item in plugin["ui_schema"]:
            key = item.get("key")
            label = item.get("label", key)
            default_val = item.get("default", "")
            item_type = item.get("type", "entry")

            ttk.Label(parent_frame, text=f"{label}:").grid(row=r, column=0, sticky=tk.W, padx=(10, 5), pady=2)

            if item_type == "checkbox":
                var = tk.BooleanVar(value=bool(default_val))
                chk = ttk.Checkbutton(parent_frame, variable=var)
                chk.grid(row=r, column=1, sticky=tk.W, pady=2)
            else:
                var = tk.StringVar(value=str(default_val))
                ent = ttk.Entry(parent_frame, textvariable=var, width=12)
                ent.grid(row=r, column=1, sticky=tk.W, pady=2)

            self.plugin_ui_vars[p_name][key] = var
            r += 1
        return r

    def close_window(self, event=None):
        """GUIを通常終了する。Alt+F4、ウィンドウの×、Ctrl+Wから呼び出す。"""
        self.root.destroy()
        return "break"

    def on_language_change(self, event=None):
        selected = next(
            (code for code, label in self.language_options.items()
             if label == self.language_var.get()),
            self.language_code,
        )
        if selected == self.language_code:
            return
        self.language_code = set_language(selected)
        self.notebook.destroy()
        self.plugin_ui_vars = {}
        self.uvn_parsers, self.loaded_plugins = init_plugins_environment(
            PLUGINS_DIR, log_func=self.log_init
        )
        self._create_widgets()

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
        print(msg)
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
            messagebox.showerror(tr("gui.errors.title"), tr("gui.errors.invalid_input_folder"))
            return

        try:
            target_val = float(self.target_var.get())
            pitch_shift = float(self.pitch_var.get())
            speed_rate = float(self.speed_var.get())
            
            sr_str = self.sr_var.get().strip()
            target_sr = int(sr_str) if sr_str else None
        except ValueError:
            messagebox.showerror(tr("gui.errors.title"), tr("gui.errors.invalid_number"))
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
            self.log(tr("gui.unexpected_error", error=e))
        finally:
            self.root.after(0, lambda: self.run_button.config(state="normal"))
