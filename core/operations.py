"""FFmpegコマンド構築（逆再生/ループ/トリミング/クロップ/ウォーターマーク）"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExportOptions:
    """エクスポートオプション"""
    reverse: bool = False
    boomerang: bool = False  # 順再生+逆再生
    crop: Optional[tuple[int, int, int, int]] = None  # (x, y, w, h)
    trim_start: float = 0.0
    trim_end: float = 0.0  # 0 = 末尾まで
    quality: int = 18  # CRF値（低いほど高品質）
    watermark: bool = False  # Free版ウォーターマーク


def _get_font_path() -> str:
    """利用可能なWindowsシステムフォントパスを返す（FFmpegエスケープ済み）"""
    candidates = [
        ("C:/Windows/Fonts/arial.ttf", "C\\:/Windows/Fonts/arial.ttf"),
        ("C:/Windows/Fonts/segoeui.ttf", "C\\:/Windows/Fonts/segoeui.ttf"),
        ("C:/Windows/Fonts/msgothic.ttc", "C\\:/Windows/Fonts/msgothic.ttc"),
    ]
    for real_path, escaped_path in candidates:
        if os.path.isfile(real_path):
            return escaped_path
    return ""


def _build_watermark_filter(video_width: int = 0) -> str:
    """ウォーターマーク用のFFmpeg drawtextフィルタ文字列を返す"""
    font_size = max(14, min(48, video_width // 30)) if video_width > 0 else 24
    font_path = _get_font_path()
    font_clause = f"fontfile='{font_path}':" if font_path else ""
    return (
        f"drawtext="
        f"{font_clause}"
        f"text='Video Kantan':"
        f"fontsize={font_size}:"
        f"fontcolor=white@0.5:"
        f"borderw=1:"
        f"bordercolor=black@0.3:"
        f"box=1:"
        f"boxcolor=black@0.3:"
        f"boxborderw=6:"
        f"x=w-tw-16:"
        f"y=h-th-16"
    )


def build_export_args(
    input_path: str,
    output_path: str,
    options: ExportOptions,
    is_gif: bool,
    duration: float,
    video_width: int = 0,
) -> list[str]:
    """エクスポート用のFFmpegコマンド引数を構築

    複数操作を1回のFFmpeg実行で適用する。
    """
    trim_start = options.trim_start
    trim_end = options.trim_end if options.trim_end > 0 else duration

    # フォーマット変換の検出（MP4→GIF, GIF→MP4）
    input_ext = os.path.splitext(input_path)[1].lower()
    output_ext = os.path.splitext(output_path)[1].lower()
    is_format_convert = (input_ext != output_ext)

    # トリミングのみ、他操作なし、同フォーマットの場合はロスレスコピー
    # ウォーターマーク付きの場合は再エンコード必須
    is_trim_only = (
        not options.reverse
        and not options.boomerang
        and options.crop is None
        and not is_format_convert
        and not options.watermark
        and (trim_start > 0 or trim_end < duration)
    )

    if is_trim_only:
        return _build_trim_lossless(input_path, output_path, trim_start, trim_end)

    # filter_complexで複合操作を構築
    if is_gif:
        return _build_gif_export(input_path, output_path, options, trim_start, trim_end, video_width)
    else:
        return _build_mp4_export(input_path, output_path, options, trim_start, trim_end, video_width)


def _build_trim_lossless(
    input_path: str, output_path: str,
    start: float, end: float,
) -> list[str]:
    """ロスレストリミング"""
    return [
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-i", input_path,
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]


def _build_mp4_export(
    input_path: str, output_path: str,
    options: ExportOptions,
    start: float, end: float,
    video_width: int = 0,
) -> list[str]:
    """MP4エクスポート（filter_complex使用）"""
    args = []

    # 入力（トリミング付き）
    if start > 0 or end > 0:
        args.extend(["-ss", f"{start:.3f}", "-to", f"{end:.3f}"])
    args.extend(["-i", input_path])

    # フィルタチェーン構築
    vfilters = []
    afilters = []

    # クロップ
    if options.crop:
        x, y, w, h = options.crop
        # 2の倍数に丸める
        w = w - (w % 2)
        h = h - (h % 2)
        vfilters.append(f"crop={w}:{h}:{x}:{y}")

    # ウォーターマーク（クロップ後、boomerang/reverse前）
    if options.watermark:
        wm_width = options.crop[2] if options.crop else video_width
        vfilters.append(_build_watermark_filter(wm_width))

    if options.boomerang:
        # 順再生+逆再生（ブーメラン）
        filter_parts = []
        pre_filters = ",".join(vfilters) + "," if vfilters else ""

        filter_complex = (
            f"[0:v]{pre_filters}split[a][b];"
            f"[b]reverse[r];"
            f"[a][r]concat=n=2:v=1[outv]"
        )
        args.extend(["-filter_complex", filter_complex])
        args.extend(["-map", "[outv]"])
        # 音声は除外（ブーメラン動画は通常音声なし）
        args.extend(["-an"])

    elif options.reverse:
        # 逆再生
        vfilters.append("reverse")
        afilters.append("areverse")

        if vfilters:
            args.extend(["-vf", ",".join(vfilters)])
        if afilters:
            args.extend(["-af", ",".join(afilters)])

    else:
        # 通常（トリミング+クロップのみ）
        if vfilters:
            args.extend(["-vf", ",".join(vfilters)])

    # 出力設定
    args.extend([
        "-c:v", "libx264",
        "-crf", str(options.quality),
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
    ])

    # 音声（ブーメラン以外）
    if not options.boomerang:
        if not options.reverse:
            args.extend(["-c:a", "aac", "-b:a", "128k"])

    args.append(output_path)
    return args


def _build_gif_export(
    input_path: str, output_path: str,
    options: ExportOptions,
    start: float, end: float,
    video_width: int = 0,
) -> list[str]:
    """GIFエクスポート（palettegen/paletteuse使用で高品質）"""
    args = []

    # 入力（トリミング付き）
    if start > 0 or end > 0:
        args.extend(["-ss", f"{start:.3f}", "-to", f"{end:.3f}"])
    args.extend(["-i", input_path])

    # フィルタ構築
    vfilters = []

    # クロップ
    if options.crop:
        x, y, w, h = options.crop
        w = w - (w % 2)
        h = h - (h % 2)
        vfilters.append(f"crop={w}:{h}:{x}:{y}")

    # ウォーターマーク（クロップ後、split前）
    if options.watermark:
        wm_width = options.crop[2] if options.crop else video_width
        vfilters.append(_build_watermark_filter(wm_width))

    pre_filters = ",".join(vfilters) + "," if vfilters else ""

    if options.boomerang:
        filter_complex = (
            f"[0:v]{pre_filters}split[a][b];"
            f"[b]reverse[r];"
            f"[a][r]concat=n=2:v=1[c];"
            f"[c]split[s1][s2];"
            f"[s1]palettegen=max_colors=256[pal];"
            f"[s2][pal]paletteuse=dither=sierra2_4a[outv]"
        )
    elif options.reverse:
        filter_complex = (
            f"[0:v]{pre_filters}reverse,split[s1][s2];"
            f"[s1]palettegen=max_colors=256[pal];"
            f"[s2][pal]paletteuse=dither=sierra2_4a[outv]"
        )
    else:
        filter_complex = (
            f"[0:v]{pre_filters}split[s1][s2];"
            f"[s1]palettegen=max_colors=256[pal];"
            f"[s2][pal]paletteuse=dither=sierra2_4a[outv]"
        )

    args.extend(["-filter_complex", filter_complex])
    args.extend(["-map", "[outv]"])
    args.append(output_path)

    return args


def generate_output_path(input_path: str, options: ExportOptions) -> str:
    """出力ファイルパスを自動生成"""
    base, ext = os.path.splitext(input_path)

    # サフィックス決定
    if options.boomerang:
        suffix = "_loop"
    elif options.reverse:
        suffix = "_reversed"
    elif options.crop:
        suffix = "_cropped"
    elif options.trim_start > 0 or options.trim_end > 0:
        suffix = "_trimmed"
    else:
        suffix = "_edited"

    # 複合操作の場合
    parts = []
    if options.trim_start > 0 or options.trim_end > 0:
        parts.append("trim")
    if options.reverse:
        parts.append("rev")
    if options.boomerang:
        parts.append("loop")
    if options.crop:
        parts.append("crop")

    if len(parts) > 1:
        suffix = "_" + "_".join(parts)

    # 同名ファイルが存在する場合は連番付与
    output_path = f"{base}{suffix}{ext}"
    counter = 2
    while os.path.exists(output_path):
        output_path = f"{base}{suffix}_{counter}{ext}"
        counter += 1

    return output_path
