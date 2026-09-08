# 依存ライブラリおよびサードパーティ製ソフトウェアのライセンス表記

本ツール（UTAU Audio Normalizer）では、音声処理・ピッチシフト・タイムストレッチ機能を実現するために以下のサードパーティ製ライブラリおよびソフトウェアを利用しています。

---

## 1. Rubberband Command-Line Utility

- **用途**: 高音質なピッチシフトおよびタイムストレッチ処理（優先処理）
- **ライセンス**: GNU General Public License v2.0 (GPL v2)
- **権利表記**: Copyright © Particular Programs Ltd / Breakfast Quay
- **入手元**: <https://breakfastquay.com/rubberband/>
- **設置方法**:
  本リポジトリには `rubberband.exe` などのバイナリファイルは同梱されていません。  
  Rubberband による高音質な処理を利用したい場合は、上記の公式入手元から Windows 版のバイナリパッケージをダウンロードし、展開した `rubberband.exe` を以下のフォルダに配置してください。

```text
  Plugins/rubberband/rubberband.exe

```

- **補足**:
本ツールは `rubberband.exe` を外部プロセス（CLIコマンド）として呼び出して利用しています。
`rubberband.exe` が配置されていない場合は、自動的に `librosa` による処理へフォールバックされます。

---

## 2. pyrubberband

- **用途**: Pythonから Rubberband CLI を安全かつ簡易に呼び出すためのラッパーライブラリ
- **ライセンス**: MIT License
- **権利表記**: Copyright (c) 2015 Brian McFee
- **入手元**: [https://github.com/bmcfee/pyrubberband](https://github.com/bmcfee/pyrubberband)

### MIT License 原文

```text
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

```

---

## 3. librosa

- **用途**: Rubberband 非搭載環境でのピッチ・速度変更フォールバック処理、および音声解析処理
- **ライセンス**: ISC License
- **権利表記**: Copyright (c) 2013--2024, librosa development team.
- **入手元**: [https://librosa.org/](https://librosa.org/)

### ISC License 原文

```text
Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

```
