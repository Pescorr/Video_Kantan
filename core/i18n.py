"""国際化モジュール - シンプル辞書ベース

OSロケールで言語を自動検出し、tr() 関数で翻訳文字列を取得する。
"""

import json
import locale
import os
from typing import Optional

_current_lang: str = "ja"

_CONFIG_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")),
    "VideoKantan", "config.json",
)

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # === gui/app.py - ウィンドウタイトル ===
    "title_free_suffix": {
        "ja": " (Free版)",
        "en": " (Free)",
    },

    # === gui/app.py - ヘッダーバー ===
    "placeholder_path": {
        "ja": "ファイルパスを入力...",
        "en": "Enter file path...",
    },
    "btn_open": {
        "ja": "開く",
        "en": "Open",
    },

    # === gui/app.py - ファイル選択 ===
    "dialog_select_file": {
        "ja": "動画/GIFファイルを選択",
        "en": "Select Video/GIF File",
    },
    "filter_video": {
        "ja": "動画ファイル (*.mp4 *.gif);;MP4 (*.mp4);;GIF (*.gif);;すべてのファイル (*.*)",
        "en": "Video Files (*.mp4 *.gif);;MP4 (*.mp4);;GIF (*.gif);;All Files (*.*)",
    },

    # === gui/app.py - エラーダイアログ ===
    "err_load_title": {
        "ja": "読み込みエラー",
        "en": "Load Error",
    },
    "err_load_msg": {
        "ja": "ファイルを読み込めません:\n{error}",
        "en": "Cannot load file:\n{error}",
    },
    "err_ffmpeg_needed_title": {
        "ja": "FFmpegが必要です",
        "en": "FFmpeg Required",
    },
    "err_ffmpeg_needed_msg": {
        "ja": "FFmpegがないため、動画の再生・編集ができません。\n"
              "手動でインストールするか、次回起動時にダウンロードしてください。",
        "en": "FFmpeg is required for video playback and editing.\n"
              "Please install manually or download on next launch.",
    },
    "err_command_title": {
        "ja": "エラー",
        "en": "Error",
    },
    "err_command_msg": {
        "ja": "コマンド構築に失敗:\n{error}",
        "en": "Failed to build command:\n{error}",
    },
    "err_export_title": {
        "ja": "エクスポートエラー",
        "en": "Export Error",
    },

    # === gui/app.py - FFmpegダウンロード ===
    "ffmpeg_not_found_title": {
        "ja": "FFmpegが見つかりません",
        "en": "FFmpeg Not Found",
    },
    "ffmpeg_not_found_msg": {
        "ja": "動画の再生・編集に必要な FFmpeg が見つかりません。\n\n"
              "インターネットから FFmpeg を自動ダウンロードしますか？\n"
              "（約40MB、gyan.dev の公式ビルドを使用します）",
        "en": "FFmpeg is required for video playback and editing.\n\n"
              "Download FFmpeg automatically?\n"
              "(~40MB, from official gyan.dev builds)",
    },
    "ffmpeg_download_title": {
        "ja": "FFmpeg ダウンロード",
        "en": "FFmpeg Download",
    },
    "ffmpeg_downloading": {
        "ja": "FFmpeg をダウンロード中... {pct}%",
        "en": "Downloading FFmpeg... {pct}%",
    },
    "ffmpeg_extracting": {
        "ja": "FFmpeg を展開中...",
        "en": "Extracting FFmpeg...",
    },
    "ffmpeg_download_cancel": {
        "ja": "キャンセル",
        "en": "Cancel",
    },
    "ffmpeg_download_error_title": {
        "ja": "ダウンロードエラー",
        "en": "Download Error",
    },
    "ffmpeg_download_error_msg": {
        "ja": "FFmpeg のダウンロードに失敗しました:\n{error}",
        "en": "Failed to download FFmpeg:\n{error}",
    },
    "ffmpeg_extract_error_msg": {
        "ja": "ダウンロードは完了しましたが、FFmpeg が正しく展開されませんでした。",
        "en": "Download completed but FFmpeg was not extracted correctly.",
    },

    # === gui/app.py - 情報ダイアログ ===
    "info_no_operation_title": {
        "ja": "Video Kantan",
        "en": "Video Kantan",
    },
    "info_no_operation_msg": {
        "ja": "操作を選択してください。\n"
              "（逆再生、ループ、クロップ、A-B区間の変更、\n"
              "\u3000または別フォーマットで出力）",
        "en": "Please select an operation.\n"
              "(Reverse, loop, crop, change A-B range,\n"
              "or export in a different format)",
    },
    "warn_memory_title": {
        "ja": "メモリ警告",
        "en": "Memory Warning",
    },
    "warn_memory_msg": {
        "ja": "逆再生/ループは動画全体をメモリに読み込みます。\n"
              "選択区間: {duration:.1f}秒\n\n"
              "5分を超える動画ではメモリ不足になる可能性があります。\n"
              "続行しますか？",
        "en": "Reverse/loop requires loading the entire video into memory.\n"
              "Selected range: {duration:.1f}s\n\n"
              "Videos over 5 minutes may cause memory issues.\n"
              "Continue?",
    },

    # === gui/app.py - エクスポート完了 ===
    "export_done_title": {
        "ja": "完了",
        "en": "Done",
    },
    "export_done_msg": {
        "ja": "保存しました:\n{filename}",
        "en": "Saved:\n{filename}",
    },
    "export_done_free_suffix": {
        "ja": "\n\n(Free版: ウォーターマーク付き)",
        "en": "\n\n(Free: watermark applied)",
    },

    # === gui/options_panel.py ===
    "cb_reverse": {
        "ja": "逆再生",
        "en": "Reverse",
    },
    "cb_boomerang": {
        "ja": "順再生+逆再生 (ループ動画)",
        "en": "Forward+Reverse (Boomerang)",
    },
    "cb_crop": {
        "ja": "クロップ",
        "en": "Crop",
    },
    "label_quality": {
        "ja": "品質:",
        "en": "Quality:",
    },
    "label_low": {
        "ja": "低",
        "en": "Low",
    },
    "label_high": {
        "ja": "高",
        "en": "High",
    },
    "btn_save_gif": {
        "ja": "GIF出力",
        "en": "Export GIF",
    },
    "btn_save_mp4": {
        "ja": "MP4出力",
        "en": "Export MP4",
    },
    "btn_open_folder": {
        "ja": "\U0001f4c2 フォルダを開く",
        "en": "\U0001f4c2 Open Folder",
    },
    "btn_cancel": {
        "ja": "キャンセル",
        "en": "Cancel",
    },
    "license_active": {
        "ja": "Licensed",
        "en": "Licensed",
    },
    "license_free": {
        "ja": "Free版 - 出力にウォーターマークが付きます",
        "en": "Free - Exports include watermark",
    },
    "label_output": {
        "ja": "出力: {path}",
        "en": "Output: {path}",
    },

    # === gui/player_widget.py ===
    "tooltip_audio_on": {
        "ja": "音声ON (クリックでOFF)",
        "en": "Audio ON (click to mute)",
    },
    "tooltip_audio_off": {
        "ja": "音声OFF (クリックでON)",
        "en": "Audio OFF (click to unmute)",
    },
    "tooltip_audiostretch_on": {
        "ja": "AUDIOSTRETCH ON (シークバードラッグで音声スクラブ)",
        "en": "AUDIOSTRETCH ON (drag seekbar to scrub audio)",
    },
    "tooltip_audiostretch_off": {
        "ja": "AUDIOSTRETCH OFF (クリックでON)",
        "en": "AUDIOSTRETCH OFF (click to enable)",
    },
    "placeholder_drag": {
        "ja": "ここにファイルをドラッグ&ドロップ\nまたは「ファイルを開く」をクリック",
        "en": "Drag & drop a file here\nor click Open",
    },

    # === gui/player_widget.py - 速度・再生モード ===
    "tooltip_speed": {
        "ja": "再生速度 (ダブルクリックでリセット)",
        "en": "Playback speed (double-click to reset)",
    },
    "tooltip_speed_input": {
        "ja": "再生速度を手入力（0.10〜3.00）",
        "en": "Enter playback speed (0.10-3.00)",
    },
    "tooltip_reverse": {
        "ja": "逆再生プレビュー (B→A)",
        "en": "Reverse preview (B→A)",
    },
    "tooltip_boomerang": {
        "ja": "ピンポン再生 (A→B→A→...)",
        "en": "Ping-pong playback (A→B→A→...)",
    },
}


def _load_saved_language() -> Optional[str]:
    """保存された言語設定を読み込む"""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("language")
    except Exception:
        return None


def _save_language(lang: str):
    """言語設定を保存"""
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    data = {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass
    data["language"] = lang
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def detect_language() -> str:
    """OSロケールから言語を自動検出"""
    try:
        loc = locale.getdefaultlocale()[0] or ""
        if loc.startswith("ja"):
            return "ja"
    except Exception:
        pass
    return "en"


def init_language(lang: Optional[str] = None):
    """言語を初期化。優先順位: 引数 → 保存済み設定 → OS自動検出"""
    global _current_lang
    if lang:
        _current_lang = lang
    else:
        saved = _load_saved_language()
        _current_lang = saved if saved else detect_language()


def set_language(lang: str):
    """言語を変更して設定ファイルに保存"""
    global _current_lang
    _current_lang = lang
    _save_language(lang)


def tr(key: str, **kwargs) -> str:
    """翻訳キーから現在の言語の文字列を返す"""
    entry = _TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(_current_lang, entry.get("en", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def get_language() -> str:
    """現在の言語コードを返す"""
    return _current_lang
