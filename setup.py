# setup.py
# 実行例:
# python setup.py build_ext --inplace
# python setup.py build_ext --inplace -cy

import os
import sys
import shutil
import glob
import argparse
import subprocess
from setuptools import setup
from Cython.Build import cythonize

# ==========================================
# 0. 設定項目 (config)
# ==========================================
src_dir = "core_python_files"
dst_dir = "core"
output_dir = "UtauVolumeNormalizer"
spec_path = "utau_volume_normalizer_spec/utau_volume_normalizer.spec"


# ==========================================
# 1. クリーンアップおよびエラーハンドリング (clean)
# ==========================================
def cleanup_on_error():
    """エラー発生時に指定された成果物・キャッシュ群を削除する"""
    print("\n--- エラーに伴うクリーンアップ処理を開始します ---", file=sys.stderr)

    directories_to_remove = [output_dir, dst_dir, "dist", "build"]
    for dir_name in directories_to_remove:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"[削除] {dir_name}/ フォルダ", file=sys.stderr)
            except Exception as e:
                print(f"[削除失敗] {dir_name}/: {e}", file=sys.stderr)

    # .c ファイルの削除
    if os.path.exists(src_dir):
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith(".c"):
                    c_path = os.path.join(root, file)
                    try:
                        os.remove(c_path)
                        print(f"[削除] {c_path}", file=sys.stderr)
                    except Exception as e:
                        print(f"[削除失敗] {c_path}: {e}", file=sys.stderr)

    # .pyd ファイルの削除
    for root, dirs, files in os.walk("."):
        if any(ex in root for ex in [".venv", "site-packages", ".git"]):
            continue
        for file in files:
            if file.endswith(".pyd"):
                pyd_file = os.path.join(root, file)
                try:
                    os.remove(pyd_file)
                    print(f"[削除] {pyd_file}", file=sys.stderr)
                except Exception as e:
                    print(f"[削除失敗] {pyd_file}: {e}", file=sys.stderr)

    # ルート直下の一時サブフォルダの削除
    if os.path.exists(src_dir):
        for entry in os.listdir(src_dir):
            src_subfolder = os.path.join(src_dir, entry)
            root_subfolder = os.path.join(".", entry)
            if os.path.isdir(src_subfolder) and os.path.isdir(root_subfolder):
                abs_src = os.path.abspath(src_subfolder)
                abs_root = os.path.abspath(root_subfolder)
                if abs_root != abs_src and abs_root != os.path.abspath(dst_dir):
                    try:
                        shutil.rmtree(root_subfolder)
                        print(f"[一時フォルダ削除] {root_subfolder}/", file=sys.stderr)
                    except Exception as e:
                        print(f"[削除失敗] {root_subfolder}/: {e}", file=sys.stderr)

def handle_error(message: str, code: int = 1):
    """エラーメッセージを出力し、クリーンアップを行って処理を安全に中断する"""
    print(f"\n[ERROR] {message}", file=sys.stderr)
    cleanup_on_error()
    print("ビルド処理を中断しました。", file=sys.stderr)
    sys.exit(code)


# ==========================================
# 2. CLI パース処理 (cli)
# ==========================================
def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    """対話形式で Yes/No を受け取る"""
    suffix = " [Y/n]: " if default_yes else " [y/N]: "
    try:
        choice = input(prompt + suffix).strip().lower()
        if not choice:
            return default_yes
        return choice in ["y", "yes"]
    except (KeyboardInterrupt, EOFError):
        print("\n中断されました。")
        sys.exit(1)

def parse_build_options():
    # 0. コマンドライン引数と対話（Y/n）の解析

    parser = argparse.ArgumentParser(description="UTAU Volume Normalizer Build Script")
    parser.add_argument("--core-yes", "-cy", action="store_true", help="core_python_files を .pyd 化する")
    parser.add_argument("--core-no", "-cn", action="store_true", help="core_python_files を .py のまま扱う")

    # Cython(setuptools)の引数とバッティングしないよう未知の引数を許容
    args, unknown = parser.parse_known_args()

    # core の .pyd 化フラグ決定
    if args.core_yes:
        build_core_pyd = True
    elif args.core_no:
        build_core_pyd = False
    else:
        build_core_pyd = ask_yes_no("core_python_files を .pyd 化しますか？", default_yes=True)

    return build_core_pyd, unknown


# ==========================================
# 3. Cython ヘルパー関数 (cython_helper)
# ==========================================
def prepare_and_collect_modules(build_core_pyd: bool):
    # 2-2. ビルド対象の .py ファイルを再帰的に取得
    modules = []

    # core の収集
    if build_core_pyd:
        if os.path.exists(src_dir):
            for root, _, files in os.walk(src_dir):
                for file in files:
                    if file.endswith(".py") and not file.startswith("__"):
                        modules.append(os.path.join(root, file))

    # 2-3. Cython が --inplace で出力するための下準備（ルート直下に一時フォルダ作成）
    for mod_path in modules:
        if mod_path.startswith(src_dir + os.sep):
            rel_path = os.path.relpath(mod_path, start=src_dir)
        else:
            rel_path = os.path.normpath(mod_path)

        rel_dir = os.path.dirname(rel_path)
        if rel_dir and not os.path.exists(rel_dir):
            os.makedirs(rel_dir, exist_ok=True)
            print(f"[事前作成] サブフォルダ: {rel_dir}/")

    return modules

def post_cython_cleanup():
    print("\n--- Cythonビルド後処理（移動・クリーンアップ）を開始します ---")

    # 3-1. 生成された .pyd ファイルの移動配置
    pyd_files = []
    for target_search_dir in [".", src_dir]:
        if os.path.exists(target_search_dir):
            for root, _, files in os.walk(target_search_dir):
                if any(ex in root for ex in ["build", output_dir, "dist", ".venv", "site-packages", dst_dir]):
                    continue
                for file in files:
                    if file.endswith(".pyd"):
                        full_pyd_path = os.path.normpath(os.path.join(root, file))
                        if full_pyd_path not in pyd_files:
                            pyd_files.append(full_pyd_path)

    for pyd_path in pyd_files:
        clean_pyd_path = os.path.normpath(pyd_path)

        # 移動先決定 (core 用の振分け)
        if clean_pyd_path.startswith(src_dir + os.sep):
            sub_rel = os.path.relpath(clean_pyd_path, start=src_dir)
            dst_path = os.path.normpath(os.path.join(dst_dir, sub_rel))
        else:
            sub_rel = clean_pyd_path.lstrip("." + os.sep)
            dst_path = os.path.normpath(os.path.join(dst_dir, sub_rel))

        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            abs_src = os.path.abspath(pyd_path)
            abs_dst = os.path.abspath(dst_path)

            if abs_src != abs_dst:
                if os.path.exists(dst_path):
                    os.remove(dst_path)
                shutil.move(pyd_path, dst_path)
                print(f"[移動完了] {pyd_path} -> {dst_path}")
        except Exception as e:
            handle_error(f".pyd ファイルの移動中にエラーが発生しました ({pyd_path} -> {dst_path}): {e}")

    # 3-2. C キャッシュファイルの削除
    if os.path.exists(src_dir):
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith(".c"):
                    c_file = os.path.join(root, file)
                    try:
                        os.remove(c_file)
                        print(f"[キャッシュ削除] {os.path.basename(c_file)}")
                    except Exception as e:
                        handle_error(f"[削除失敗] {c_file}: {e}", file=sys.stderr)

    # 3-3. ルート直下に作られた作業用一時サブフォルダの削除
    if os.path.exists(src_dir):
        for entry in os.listdir(src_dir):
            src_subfolder = os.path.join(src_dir, entry)
            root_subfolder = os.path.join(".", entry)
            if os.path.isdir(src_subfolder) and os.path.isdir(root_subfolder):
                abs_src = os.path.abspath(src_subfolder)
                abs_root = os.path.abspath(root_subfolder)
                if abs_root != abs_src and abs_root != os.path.abspath(dst_dir):
                    try:
                        shutil.rmtree(root_subfolder)
                        print(f"[一時フォルダ削除] {root_subfolder}/")
                    except Exception as e:
                        print(f"[削除失敗] {root_subfolder}/: {e}", file=sys.stderr)

    # 3-4. build/ の削除
    if os.path.exists("build"):
        try:
            shutil.rmtree("build")
            print("[キャッシュ削除] build/ フォルダ")
        except Exception as e:
            handle_error(f"[削除失敗] build/: {e}", file=sys.stderr)


# ==========================================
# 4. PyInstaller ヘルパー (pyinstaller_helper)
# ==========================================
def run_pyinstaller():
    # 4. PyInstaller ビルド実行
    print(f"\n--- [Step 2] PyInstaller ビルドを開始します ({spec_path}) ---")

    if not os.path.exists(spec_path):
        handle_error(f"Specファイルが見つかりません: {spec_path}")

    cmd = [sys.executable, "-m", "PyInstaller", spec_path, "--noconfirm"]
    result = subprocess.run(cmd)

    if result.returncode != 0:
        handle_error(f"PyInstaller によるビルドに失敗しました。(終了コード: {result.returncode})")

    if os.path.exists("build"):
        try:
            shutil.rmtree("build")
            print("[キャッシュ削除] PyInstaller実行後の build/ フォルダを削除しました")
        except Exception as e:
            handle_error(f"[削除失敗] build/: {e}", file=sys.stderr)

    print("--- PyInstaller ビルド完了 ---\n")


# ==========================================
# 5. 成果物集約・整理処理 (artifact)
# ==========================================
def initialize_output_dir():
    # 2-1. 配布用フォルダ (UtauVolumeNormalizer/) の初期化
    if os.path.exists(output_dir):
        try:
            shutil.rmtree(output_dir)
            print(f"[初期化] 既存の {output_dir}/ フォルダを削除しました。")
        except Exception as e:
            handle_error(f"{output_dir}/ フォルダの削除に失敗しました: {e}")

    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"[初期化] {output_dir}/ フォルダを新規作成しました。")
    except Exception as e:
        handle_error(f"{output_dir}/ フォルダの作成に失敗しました: {e}")

def organize_artifacts(build_core_pyd: bool):
    # 5. 成果物の集約と配置処理
    print("--- [Step 3] 成果物（onedir成果物, core, Plugins, Languages, LICENSE, README.md）の整理と配置 ---")

    onedir_folder = os.path.join("dist", "utau_volume_normalizer")
    dist_exe = os.path.join(onedir_folder, "utau_volume_normalizer.exe")
    dist_libraries = os.path.join(onedir_folder, "libraries")

    target_exe = os.path.join(output_dir, "utau_volume_normalizer.exe")
    target_libraries = os.path.join(output_dir, "libraries")

    # 5-1. exe コピー
    if os.path.exists(dist_exe):
        try:
            shutil.copy2(dist_exe, target_exe)
            print(f"[コピー完了] {dist_exe} -> {target_exe}")
        except Exception as e:
            handle_error(f"exe ファイルのコピーに失敗しました: {e}")
    else:
        handle_error(f"onedir フォルダ内に exe ファイルが見つかりません: {dist_exe}")

    # 5-2. libraries コピー
    if os.path.exists(dist_libraries):
        try:
            shutil.copytree(dist_libraries, target_libraries, dirs_exist_ok=True)
            print(f"[コピー完了] {dist_libraries}/ -> {target_libraries}/")
        except Exception as e:
            handle_error(f"libraries フォルダのコピーに失敗しました: {e}")
    else:
        handle_error(f"onedir フォルダ内に libraries フォルダが見つかりません: {dist_libraries}")

    # 5-3. dist/ フォルダ削除
    if os.path.exists("dist"):
        try:
            shutil.rmtree("dist")
            print("[クリーンアップ] dist/ フォルダを削除しました")
        except Exception as e:
            handle_error(f"[削除失敗] dist/: {e}", file=sys.stderr)

    # 5-4. ドキュメント類のコピー
    for doc in ["LICENSE", "README.md", "README.txt"]:
        if os.path.exists(doc):
            try:
                shutil.copy2(doc, os.path.join(output_dir, doc))
                print(f"[コピー完了] {doc} -> {output_dir}/")
            except Exception as e:
                print(f"[警告] {doc} のコピーに失敗しました: {e}", file=sys.stderr)

    # 5-5. core/ の配置 (pyd化の有無に応じた処理)
    dst_core_in_output = os.path.join(output_dir, "core")
    if build_core_pyd:
        if os.path.exists(dst_dir):
            try:
                shutil.copytree(dst_dir, dst_core_in_output, dirs_exist_ok=True)
                print(f"[コピー完了] {dst_dir}/ -> {dst_core_in_output}/ (.pyd 版)")
            except Exception as e:
                handle_error(f"{dst_dir}/ フォルダのコピーに失敗しました: {e}")
    else:
        # .py のままコピー (core_python_files/ -> UtauVolumeNormalizer/core/)
        if os.path.exists(src_dir):
            try:
                shutil.copytree(src_dir, dst_core_in_output, dirs_exist_ok=True)
                print(f"[コピー完了] {src_dir}/ -> {dst_core_in_output}/ (.py 版)")
            except Exception as e:
                handle_error(f"{src_dir}/ フォルダのコピーに失敗しました: {e}")

    # 5-6. Plugins / Languages などのコピー
    for src_folder in ["Plugins", "PluginsLanguages"]:
        dst_folder = os.path.join(output_dir, src_folder)
        if os.path.exists(src_folder):
            try:
                shutil.copytree(src_folder, dst_folder, dirs_exist_ok=True)
                print(f"[コピー完了] {src_folder}/ -> {dst_folder}/")
            except Exception as e:
                print(f"[警告] {src_folder}/ のコピーに失敗しました: {e}", file=sys.stderr)

    # 5-7. Plugins/rubberband/ 内の不要ファイルの削除
    rubberband_dir = os.path.join(output_dir, "Plugins", "rubberband")
    if os.path.exists(rubberband_dir):
        for pattern in ["*.exe", "*.dll", "COPYING.txt"]:
            for target_file in glob.glob(os.path.join(rubberband_dir, pattern)):
                try:
                    os.remove(target_file)
                    print(f"[削除] {target_file}")
                except Exception as e:
                    handle_error(f"[削除失敗] {target_file}: {e}", file=sys.stderr)

    print("\n=== すべてのビルド・配置処理が正常に完了しました！ ===")


# ==========================================
# メインエントリーポイント
# ==========================================
def main():
    # 0. コマンドライン引数と対話（Y/n）の解析
    build_core_pyd, unknown = parse_build_options()

    # 2-1. 配布用フォルダ (UtauVolumeNormalizer/) の初期化
    initialize_output_dir()

    # 2-2 ~ 2-3. ビルド対象収集・下準備
    modules = prepare_and_collect_modules(build_core_pyd)

    # 3. Cython ビルド実行
    if modules:
        print(f"\n--- [Step 1] Cython ビルドを実行します ({len(modules)} ファイル) ---")
        try:
            # sys.argv から独自フラグを除外して setuptools に渡す
            sys.argv = [sys.argv[0]] + unknown
            setup(
                ext_modules=cythonize(modules, compiler_directives={'language_level': "3"})
            )
        except Exception as e:
            handle_error(f"Cython ビルド中にエラーが発生しました: {e}")

        post_cython_cleanup()
    else:
        print("\n--- Cython ビルド対象がないため、スキップします ---")

    # 4. PyInstaller ビルド実行
    run_pyinstaller()

    # 5. 成果物の集約と配置処理
    organize_artifacts(build_core_pyd)

if __name__ == "__main__":
    main()
