# setup_cache_delete.py
# 実行方法: python setup_cache_delete.py

import os
import sys
import shutil

src_dir = "core_python_file"
dst_dir = "core_pyd"
output_dir = "UtauVolumeNormalizer"

def cleanup_on_error():
    """指定された成果物・キャッシュ群を削除する"""
    print("\n--- クリーンアップ処理を開始します ---", file=sys.stderr)

    # 1-1. 削除対象ディレクトリ（core/ 含む成果物・ビルド・一時フォルダを丸ごと削除）
    directories_to_remove = [dst_dir, "dist", "build"]
    for dir_name in directories_to_remove:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"[削除] {dir_name}/ フォルダ", file=sys.stderr)
            except Exception as e:
                print(f"[削除失敗] {dir_name}/: {e}", file=sys.stderr)

    # 1-2. core_python_file/ 配下の全 .c ファイル削除
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

    # 1-3. ルート直下および作業用サブフォルダに残った .pyd ファイルの再帰削除
    for root, dirs, files in os.walk("."):
        # 検索除外対象（.venv等）
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

    # 1-4. src_dir 内の構造に基づいてルート直下に作成された一時サブフォルダ（uvn_plugin_runtime等）のみ安全に削除
    if os.path.exists(src_dir):
        for entry in os.listdir(src_dir):
            src_subfolder = os.path.join(src_dir, entry)
            root_subfolder = os.path.join(".", entry)  # ルート直下のパスを明示

            # core_python_file 内がフォルダであり、かつルート直下にも同名フォルダが存在する場合
            if os.path.isdir(src_subfolder) and os.path.isdir(root_subfolder):
                # 絶対パスに変換して、削除対象が絶対に core_python_file 内ではないことを保証する
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
    print("クリーンアップ処理を中断しました。", file=sys.stderr)
    sys.exit(code)

# クリーンアップ実行
cleanup_on_error()

print("\n=== キャッシュ・一時ファイルのクリーンアップが完了しました！ ===")
