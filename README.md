# Video Kantan v1.0.0

軽量な動画/GIF編集ツールです。ドラッグ&ドロップで動画を読み込み、トリミング・逆再生・クロップ・GIF変換などの基本操作を直感的に行えます。

*A lightweight video/GIF editor. Load videos via drag & drop and perform basic operations like trimming, reverse playback, cropping, and GIF conversion.*

## 機能 / Features

- **動画プレビュー / Video Preview**: フレーム単位のシークバー付きプレイヤー
- **トリミング / Trim**: A-B区間を指定してカット
- **逆再生 / Reverse**: 動画全体またはトリミング区間を逆再生
- **ブーメラン / Boomerang**: 順再生＋逆再生のループ動画を生成
- **クロップ / Crop**: ドラッグで範囲選択して切り抜き
- **GIF変換 / GIF Export**: 動画をGIFアニメーションに変換
- **MP4出力 / MP4 Export**: 編集結果をMP4で保存
- **ダークテーマ / Dark Theme**: 目に優しいダークUI
- **日英対応 / Bilingual**: OSロケールで自動切替

## Free版 vs Licensed版

| | Free | Licensed |
|---|---|---|
| 全機能 | ✅ | ✅ |
| ウォーターマーク | あり | **なし** |

ライセンスキーは `license/` フォルダに `license.key` を配置して再起動するだけで有効化されます。

## 動作環境

- Windows 10 以降
- FFmpeg（初回起動時に自動ダウンロード）

## インストール（開発者向け）

```bash
pip install -r requirements.txt
python main.py
```

## ビルド（exe化）

```bash
pyinstaller VideoKantan.spec
```

`dist/VideoKantan/` フォルダが生成されます。

## FFmpegについて

本ソフトウェアは動画処理に FFmpeg を使用しますが、FFmpeg バイナリは同梱していません。初回起動時にダウンロード確認ダイアログが表示され、承諾すると [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) から FFmpeg essentials ビルドを `%LOCALAPPDATA%/VideoKantan/ffmpeg/` に自動ダウンロードします。

FFmpeg は GPL v2 ライセンスですが、本ソフトウェアは FFmpeg をコマンドライン経由で別プロセスとして呼び出しており、FFmpeg のコードをリンク・同梱していないため、GPL の影響を受けません。

## 依存ライブラリ

| ライブラリ | ライセンス | 用途 |
|---|---|---|
| [PySide6](https://doc.qt.io/qtforpython/) | LGPL v3 | GUI フレームワーク |
| [Pillow](https://python-pillow.org/) | HPND License | GIF フレーム処理 |

## LGPL準拠について

本ソフトウェアは PySide6（LGPL v3）を使用しています。ソースコードは MIT ライセンスで公開されているため、ユーザーは PySide6 を別バージョンに差し替えて再ビルドすることが可能です。PyInstaller の onedir モードでビルドしており、PySide6 の DLL は `_internal/` 内に個別ファイルとして配置されるため、直接差し替えも可能です。

## ライセンス

MIT License - 詳細は [LICENSE.txt](LICENSE.txt) を参照してください。

利用規約は [TERMS.md](TERMS.md) を参照してください。
