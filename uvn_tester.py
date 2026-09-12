import os
import sys
import shutil
import argparse
import inspect
import importlib.util
import numpy as np
from scipy.io import wavfile

# --- 実行環境・インポートパスのセットアップ ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_PYTHON_DIR = os.path.join(CURRENT_DIR, "core_python_files")
CORE_PYD_DIR = os.path.join(CURRENT_DIR, "core_pyd")

if os.path.exists(CORE_PYTHON_DIR):
    sys.path.insert(0, CORE_PYTHON_DIR)
elif os.path.exists(CORE_PYD_DIR):
    sys.path.insert(0, CORE_PYD_DIR)

sys.path.insert(0, CURRENT_DIR)

# モジュールの読み込み
try:
    from uvn_utility import init_plugins_environment, PLUGINS_DIR
    from uvn_audio import process_audio
    from uvn_plugin_runtime.decoder import parse_uvn_file, load_uvn_utility_plugins
except ImportError:
    try:
        from decoder import parse_uvn_file, load_uvn_utility_plugins
        from uvn_utility import init_plugins_environment, PLUGINS_DIR
        from uvn_audio import process_audio
    except ImportError as e:
        print(f"[ERROR] モジュールの読み込みに失敗しました: {e}")
        sys.exit(1)


def generate_complex_test_wavs(input_dir):
    """テスト用ダミーWAV音源の自動生成"""
    os.makedirs(input_dir, exist_ok=True)
    
    # 1. クリーンサイン波 (44.1kHz, Mono)
    sr, dur = 44100, 1.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    data1 = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    wavfile.write(os.path.join(input_dir, "01_normal_mono.wav"), sr, data1)

    # 2. DC偏り ＋ ノイズ (48kHz, Stereo)
    sr2, dur2 = 48000, 1.2
    t2 = np.linspace(0, dur2, int(sr2 * dur2), endpoint=False)
    noise = np.random.normal(0, 0.05, len(t2))
    dc_signal = 0.3 * np.sin(2 * np.pi * 880 * t2) + 0.15 + noise
    stereo_data = np.vstack((dc_signal, dc_signal)).T
    data2 = (np.clip(stereo_data, -1.0, 1.0) * 32767).astype(np.int16)
    wavfile.write(os.path.join(input_dir, "02_dc_offset_noise_stereo.wav"), sr2, data2)

    # 3. 無音区間付き音源 (44.1kHz)
    sr3, dur3 = 44100, 2.0
    silence = np.zeros(int(sr3 * 0.5))
    tone = 0.6 * np.sin(2 * np.pi * 523.25 * np.linspace(0, 1.0, sr3, endpoint=False))
    data3 = (np.concatenate([silence, tone, silence]) * 32767).astype(np.int16)
    wavfile.write(os.path.join(input_dir, "03_silent_padded.wav"), sr3, data3)


def inspect_py_plugin(file_path):
    """ .py / .pyd ファイルからフック関数および UI_SCHEMA などのメタデータを解析・抽出 """
    try:
        mod_name = os.path.splitext(os.path.basename(file_path))[0]
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        hook = None
        if hasattr(module, "process_audio_hook"):
            hook = getattr(module, "process_audio_hook")
        elif hasattr(module, "process_audio"):
            hook = getattr(module, "process_audio")
        elif hasattr(module, "main"):
            hook = getattr(module, "main")

        ui_schema = getattr(module, "UI_SCHEMA", getattr(module, "PARAMETERS", getattr(module, "UI_CONTROLS", [])))
        display_name = getattr(module, "DISPLAY_NAME", getattr(module, "PLUGIN_NAME", mod_name))

        if hook or ui_schema:
            return {
                "name": mod_name,
                "display_name": display_name,
                "ui_schema": ui_schema,
                "hook": hook,
                "module": module,
                "file_path": file_path
            }
    except Exception as e:
        print(f"[Py Plugin Load Error] {os.path.basename(file_path)}: {e}")
    return None


def collect_all_tester_plugins():
    """Plugins/ ディレクトリから .py, .pyd, .uvn プラグインを一括収集"""
    uvn_parsers, loaded_plugins = init_plugins_environment(PLUGINS_DIR)
    all_plugins = []

    # 1. init_plugins_environment の結果を取り込み
    for p in loaded_plugins:
        if isinstance(p, dict):
            all_plugins.append(p)
        elif callable(p):
            func_name = getattr(p, "__name__", str(p))
            all_plugins.append({
                "name": func_name,
                "display_name": func_name,
                "ui_schema": getattr(p, "UI_SCHEMA", []),
                "hook": p
            })

    # 2. Plugins ディレクトリを直接探索して .uvn および .py / .pyd を登録
    if os.path.exists(PLUGINS_DIR):
        for root, _, files in os.walk(PLUGINS_DIR):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                full_path = os.path.join(root, file)

                if ext == ".uvn":
                    parsed = parse_uvn_file(full_path)
                    if parsed:
                        already_exists = any(
                            isinstance(p, dict) and p.get("name") == parsed.get("name")
                            for p in all_plugins
                        )
                        if not already_exists:
                            all_plugins.append(parsed)

                elif ext in (".py", ".pyd") and not file.startswith("__"):
                    py_plugin = inspect_py_plugin(full_path)
                    if py_plugin:
                        already_exists = any(
                            isinstance(p, dict) and p.get("name") == py_plugin.get("name")
                            for p in all_plugins
                        )
                        if not already_exists:
                            all_plugins.append(py_plugin)

    return all_plugins


def filter_plugins_by_target(plugins_list, target_name):
    """名前またはファイルパスで対象プラグインを絞り込み"""
    if not target_name or target_name.lower() == "all":
        return plugins_list

    filtered = []
    target_lower = target_name.lower()

    for plugin in plugins_list:
        if isinstance(plugin, dict):
            p_name = str(plugin.get("name", "")).lower()
            p_disp = str(plugin.get("display_name", "")).lower()
            if target_lower in p_name or target_lower in p_disp:
                filtered.append(plugin)
        elif callable(plugin):
            func_name = getattr(plugin, "__name__", str(plugin)).lower()
            if target_lower in func_name:
                filtered.append(plugin)

    return filtered


def execute_sandbox_test(params, target_plugin_name=None, keep_files=False, runtime_custom_params=None):
    """サンドボックステストの実行"""
    print("\n==================================================")
    print("          UVN Sandbox Plugin Tester               ")
    print("==================================================")

    test_input_dir = os.path.join(CURRENT_DIR, "_test_sandbox_wavs")
    test_output_dirname = "_test_output"
    
    if os.path.exists(test_input_dir):
        shutil.rmtree(test_input_dir)

    print("\n[Step 1] テスト用音源の生成...")
    generate_complex_test_wavs(test_input_dir)

    print("\n[Step 2] プラグイン走査・フィルタリング...")
    raw_plugins = collect_all_tester_plugins()
    
    executable_hooks = []

    if params['use_plugins']:
        filtered_plugins = filter_plugins_by_target(raw_plugins, target_plugin_name)
        print(f" - 検出総数: {len(raw_plugins)} 件 / 適用対象: {len(filtered_plugins)} 件")
        
        for idx, p in enumerate(filtered_plugins, 1):
            if isinstance(p, dict):
                disp = p.get("display_name", p.get("name", "Unnamed"))
                hook = p.get("hook")
                p_type = ".py/.pyd" if p.get("file_path", "").endswith((".py", ".pyd")) else ".uvn"
                
                if callable(hook):
                    if runtime_custom_params:
                        def custom_hook_wrapper(data, sr, wave_name, orig_h=hook, c_params=runtime_custom_params):
                            sig = inspect.signature(orig_h)
                            if "params" in sig.parameters:
                                return orig_h(data, sr, wave_name, params=c_params)
                            return orig_h(data, sr, wave_name)
                        executable_hooks.append(custom_hook_wrapper)
                    else:
                        executable_hooks.append(hook)
                    print(f"   {idx}. [{p_type}] {disp} (Hook抽出完了)")
                else:
                    print(f"   {idx}. [{p_type}] {disp} (実行可能フックなし)")

            elif callable(p):
                executable_hooks.append(p)
                print(f"   {idx}. [.py/.pyd] {getattr(p, '__name__', str(p))}")
    else:
        print(" - プラグイン適用: OFF")

    print("\n[Step 3] process_audio 実行中...")
    log_func = None if params['no_log'] else print

    exit_code = process_audio(
        input_dir=test_input_dir,
        mode=params['mode'],
        target_val=params['target_val'],
        profile_mode=params['profile_mode'],
        output_dirname=test_output_dirname,
        to_mono=params['to_mono'],
        remove_dc=params['remove_dc'],
        backup=params['backup'],
        dry_run=params['dry_run'],
        target_sr=params['target_sr'],
        trim=params['trim'],
        force_16bit=params['force_16bit'],
        pitch_shift=params['pitch_shift'],
        speed_rate=params['speed_rate'],
        max_workers=params['max_workers'],
        show_progress=params['show_progress'],
        loaded_plugins=executable_hooks,
        log_func=log_func
    )

    print("\n[Step 4] 処理結果の検証...")
    output_dir = os.path.join(test_input_dir, test_output_dirname)
    if exit_code == 0 and os.path.exists(output_dir):
        out_files = [f for f in os.listdir(output_dir) if f.endswith(".wav")]
        print(f" - 成功: {len(out_files)} 個のファイルを出力")
        for f in out_files:
            out_path = os.path.join(output_dir, f)
            sr, data = wavfile.read(out_path)
            print(f"   * {f:30s} | SR: {sr}Hz | Shape: {data.shape} | dtype: {data.dtype}")
    else:
        print(" - エラー: パイプライン実行に失敗しました。")

    if keep_files:
        print(f"\n[情報] 出力結果ディレクトリを保持しました: {test_input_dir}")
    else:
        try:
            shutil.rmtree(test_input_dir)
            print("\n[クリーンアップ] テスト用一時データを削除しました。")
        except Exception as e:
            print(f"\n[クリーンアップ失敗]: {e}")

    print("\n==================================================")
    print("                 テスト完了                       ")
    print("==================================================")


def launch_gui():
    """.py と .uvn の両方の UI_SCHEMA ダイナミック再現GUI"""
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("UVN Sandbox - プラグイン＆機能テスター")
    root.geometry("560x760")
    root.resizable(True, True)

    all_plugins = collect_all_tester_plugins()

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=5, pady=5)

    tab_basic = ttk.Frame(notebook)
    tab_plugin = ttk.Frame(notebook)

    notebook.add(tab_basic, text=" 基本・パイプライン設定 ")
    notebook.add(tab_plugin, text=" プラグイン選択 & UI_SCHEMA再現 ")

    padding_opts = {'padx': 8, 'pady': 3, 'sticky': 'w'}

    # --- タブ1: 基本設定 ---
    mode_var = tk.StringVar(value="peak")
    target_val_var = tk.DoubleVar(value=-1.0)
    profile_var = tk.StringVar(value="none")
    target_sr_var = tk.IntVar(value=44100)
    pitch_var = tk.DoubleVar(value=0.0)
    speed_var = tk.DoubleVar(value=1.0)
    
    mono_var = tk.BooleanVar(value=True)
    dc_var = tk.BooleanVar(value=True)
    trim_var = tk.BooleanVar(value=True)
    keep_var = tk.BooleanVar(value=False)

    frame_basic = ttk.LabelFrame(tab_basic, text=" ノーマライズ & 音声設定 ", padding=10)
    frame_basic.pack(fill="both", expand=True, padx=10, pady=10)

    ttk.Label(frame_basic, text="処理モード:").grid(row=0, column=0, **padding_opts)
    ttk.Combobox(frame_basic, textvariable=mode_var, values=["peak", "rms"], state="readonly", width=12).grid(row=0, column=1, **padding_opts)

    ttk.Label(frame_basic, text="目標値 (dBFS):").grid(row=1, column=0, **padding_opts)
    ttk.Entry(frame_basic, textvariable=target_val_var, width=15).grid(row=1, column=1, **padding_opts)

    ttk.Label(frame_basic, text="プロファイル処理:").grid(row=2, column=0, **padding_opts)
    ttk.Combobox(frame_basic, textvariable=profile_var, values=["none", "vowel", "consonant"], state="readonly", width=12).grid(row=2, column=1, **padding_opts)

    ttk.Label(frame_basic, text="サンプリングレート:").grid(row=3, column=0, **padding_opts)
    ttk.Combobox(frame_basic, textvariable=target_sr_var, values=[0, 44100, 48000, 96000], state="readonly", width=12).grid(row=3, column=1, **padding_opts)

    ttk.Label(frame_basic, text="ピッチ変更 (半音):").grid(row=4, column=0, **padding_opts)
    ttk.Entry(frame_basic, textvariable=pitch_var, width=15).grid(row=4, column=1, **padding_opts)

    ttk.Label(frame_basic, text="速度倍率:").grid(row=5, column=0, **padding_opts)
    ttk.Entry(frame_basic, textvariable=speed_var, width=15).grid(row=5, column=1, **padding_opts)

    ttk.Checkbutton(frame_basic, text="モノラル化", variable=mono_var).grid(row=6, column=0, **padding_opts)
    ttk.Checkbutton(frame_basic, text="DCオフセット除去", variable=dc_var).grid(row=6, column=1, **padding_opts)
    ttk.Checkbutton(frame_basic, text="無音トリミング", variable=trim_var).grid(row=7, column=0, **padding_opts)
    ttk.Checkbutton(frame_basic, text="生成ファイルを残す", variable=keep_var).grid(row=7, column=1, **padding_opts)

    # --- タブ2: プラグイン選択 & UI_SCHEMA 自動生成 ---
    plugin_select_var = tk.StringVar(value="すべてのプラグイン (All)")
    
    plugin_options = ["すべてのプラグイン (All)", "プラグインなし (None)"]
    plugin_map = {}

    for p in all_plugins:
        if isinstance(p, dict):
            disp = p.get("display_name", p.get("name", "Unknown Plugin"))
            p_type = ".py" if p.get("file_path", "").endswith((".py", ".pyd")) else ".uvn"
            label_text = f"[{p_type}] {disp}"
            plugin_options.append(label_text)
            plugin_map[label_text] = p

    frame_plugin_sel = ttk.LabelFrame(tab_plugin, text=" テスト対象プラグインの選択 ", padding=10)
    frame_plugin_sel.pack(fill="x", padx=10, pady=5)

    plugin_cb = ttk.Combobox(frame_plugin_sel, textvariable=plugin_select_var, values=plugin_options, state="readonly", width=42)
    plugin_cb.pack(fill="x", padx=5, pady=5)

    # UI_SCHEMA 再現コンテナ
    schema_ui_frame = ttk.LabelFrame(tab_plugin, text=" プラグイン UI_SCHEMA ダイナミック再現 ", padding=10)
    schema_ui_frame.pack(fill="both", expand=True, padx=10, pady=5)

    dynamic_widgets = {}

    def render_schema_ui(selected_label):
        for widget in schema_ui_frame.winfo_children():
            widget.destroy()
        dynamic_widgets.clear()

        plugin_obj = plugin_map.get(selected_label)
        if not plugin_obj or not isinstance(plugin_obj, dict):
            ttk.Label(schema_ui_frame, text="選択された要素には UI_SCHEMA 定義がありません。").pack(padx=10, pady=10)
            return

        schema = plugin_obj.get("ui_schema", [])
        if not schema:
            ttk.Label(schema_ui_frame, text="このプラグインに設定可能な UI_SCHEMA パラメータはありません。").pack(padx=10, pady=10)
            return

        for row_idx, item in enumerate(schema):
            if not isinstance(item, dict):
                continue
            
            p_name = item.get("name", item.get("key", f"param_{row_idx}"))
            p_label = item.get("label", p_name)
            p_default = item.get("default", "")
            p_type = item.get("type", "entry").lower()

            ttk.Label(schema_ui_frame, text=f"{p_label}:").grid(row=row_idx, column=0, **padding_opts)

            if p_type in ["checkbox", "bool", "boolean"] or isinstance(p_default, bool):
                var = tk.BooleanVar(value=bool(p_default))
                chk = ttk.Checkbutton(schema_ui_frame, variable=var)
                chk.grid(row=row_idx, column=1, **padding_opts)
                dynamic_widgets[p_name] = var

            elif p_type in ["combobox", "choice", "select"] or "options" in item:
                var = tk.StringVar(value=str(p_default))
                opts = item.get("options", item.get("choices", []))
                cb = ttk.Combobox(schema_ui_frame, textvariable=var, values=opts, state="readonly", width=15)
                cb.grid(row=row_idx, column=1, **padding_opts)
                dynamic_widgets[p_name] = var

            else:
                var = tk.StringVar(value=str(p_default))
                entry = ttk.Entry(schema_ui_frame, textvariable=var, width=20)
                entry.grid(row=row_idx, column=1, **padding_opts)
                dynamic_widgets[p_name] = var

    def on_plugin_select_change(event):
        render_schema_ui(plugin_select_var.get())

    plugin_cb.bind("<<ComboboxSelected>>", on_plugin_select_change)

    # テスト実行
    def on_run_test():
        selected_key = plugin_select_var.get()
        use_plugins = True
        target_name = "all"
        custom_params = {}

        if selected_key == "プラグインなし (None)":
            use_plugins = False
        elif selected_key != "すべてのプラグイン (All)":
            plugin_obj = plugin_map.get(selected_key)
            if isinstance(plugin_obj, dict):
                target_name = plugin_obj.get("name", plugin_obj.get("display_name", ""))
                custom_params = {k: v.get() for k, v in dynamic_widgets.items()}

        params = {
            'mode': mode_var.get(),
            'target_val': target_val_var.get(),
            'profile_mode': None if profile_var.get() == "none" else profile_var.get(),
            'target_sr': None if target_sr_var.get() == 0 else target_sr_var.get(),
            'pitch_shift': pitch_var.get(),
            'speed_rate': speed_var.get(),
            'max_workers': None,
            'to_mono': mono_var.get(),
            'remove_dc': dc_var.get(),
            'trim': trim_var.get(),
            'force_16bit': True,
            'backup': False,
            'dry_run': False,
            'use_plugins': use_plugins,
            'show_progress': True,
            'no_log': False
        }

        try:
            execute_sandbox_test(
                params, 
                target_plugin_name=target_name, 
                keep_files=keep_var.get(),
                runtime_custom_params=custom_params
            )
            messagebox.showinfo("完了", "プラグインテスト処理が正常に終了しました。\n詳細はコンソール出力をご確認ください。")
        except Exception as e:
            messagebox.showerror("エラー", f"実行中にエラーが発生しました:\n{e}")

    btn_run = ttk.Button(root, text="🚀 サンドボックステストを実行", command=on_run_test)
    btn_run.pack(fill="x", padx=15, pady=10)

    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="UVN プラグイン＆機能サンドボックステスター")
    parser.add_argument("--gui", action="store_true", help="UI_SCHEMA 再現GUIモードを起動します")
    
    parser.add_argument("--plugin", type=str, default="all", help="対象プラグイン名（例: lowcut, .py, .uvn）")
    parser.add_argument("--mode", choices=["peak", "rms"], default="peak")
    parser.add_argument("--target", type=float, default=-1.0)
    parser.add_argument("--profile", choices=["none", "vowel", "consonant"], default="none")
    parser.add_argument("--sr", type=int, default=44100)
    parser.add_argument("--keep", action="store_true", help="テスト用WAV生成フォルダを削除せず維持")

    args = parser.parse_args()

    if args.gui:
        launch_gui()
    else:
        params = {
            'mode': args.mode,
            'target_val': args.target,
            'profile_mode': None if args.profile == "none" else args.profile,
            'target_sr': None if args.sr == 0 else args.sr,
            'pitch_shift': 0.0,
            'speed_rate': 1.0,
            'max_workers': None,
            'to_mono': True,
            'remove_dc': True,
            'trim': True,
            'force_16bit': True,
            'backup': False,
            'dry_run': False,
            'use_plugins': True,
            'show_progress': True,
            'no_log': False
        }
        execute_sandbox_test(params, target_plugin_name=args.plugin, keep_files=args.keep)


if __name__ == "__main__":
    main()
