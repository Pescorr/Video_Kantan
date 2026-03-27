"""ライセンス検証モジュール

署名付きBase64形式の license.key ファイルを検証する。

ファイル形式:
    -----BEGIN VIDEOKANTAN LICENSE-----
    <Base64エンコードされたJSON>
    -----END VIDEOKANTAN LICENSE-----

JSON構造:
    {"k": "VK-XXXX-XXXX-XXXX", "t": "timestamp", "s": "hmac_hex"}
"""

import base64
import hashlib
import hmac
import json
import os
import random
import sys
import time
from typing import Optional

# I, O, L を除外した33文字セット
_CHARSET = "0123456789ABCDEFGHJKMNPQRSTUVWXYZ"

# HMAC署名用シークレット（善意ベース: カジュアルコピー防止）
_HMAC_SECRET = b"vk-2025-kantan-sign-e9f3a7b1c4d6"

_BEGIN_MARKER = "-----BEGIN VIDEOKANTAN LICENSE-----"
_END_MARKER = "-----END VIDEOKANTAN LICENSE-----"


def _get_base_dir() -> str:
    """exe（またはスクリプト）と同じディレクトリを返す"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_license_paths() -> list[str]:
    """ライセンスファイルの検索パスを優先順に返す"""
    base = _get_base_dir()
    paths = [
        # 1. <exe_dir>/license/license.key
        os.path.join(base, "license", "license.key"),
        # 2. <exe_dir>/license.key (旧互換)
        os.path.join(base, "license.key"),
    ]
    # 3. %LOCALAPPDATA%/VideoKantan/license.key
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        local_app_data = os.path.expanduser("~\\AppData\\Local")
    paths.append(os.path.join(local_app_data, "VideoKantan", "license.key"))
    return paths


# ===== キー検証（内部） =====

def _validate_key_format(key: str) -> bool:
    """キーフォーマット VK-XXXX-XXXX-XXXX を検証"""
    key = key.strip().upper()
    if not key.startswith("VK-"):
        return False
    parts = key[3:].split("-")
    if len(parts) != 3:
        return False
    if not all(len(p) == 4 for p in parts):
        return False
    all_chars = "".join(parts)
    return all(c in _CHARSET for c in all_chars)


def _validate_checksum(key: str) -> bool:
    """チェックサム検証（最後の1文字）"""
    key = key.strip().upper()
    all_chars = key.replace("VK-", "").replace("-", "")
    payload = all_chars[:-1]
    check_char = all_chars[-1]
    total = sum(_CHARSET.index(c) * (i + 1) for i, c in enumerate(payload))
    expected = _CHARSET[total % len(_CHARSET)]
    return check_char == expected


def _validate_key(key: str) -> bool:
    """ライセンスキーの完全検証"""
    if not _validate_key_format(key):
        return False
    return _validate_checksum(key)


def _compute_signature(key: str, timestamp: str) -> str:
    """HMAC-SHA256 署名を計算"""
    message = f"{key}:{timestamp}".encode("utf-8")
    return hmac.new(_HMAC_SECRET, message, hashlib.sha256).hexdigest()


# ===== ファイル読み取り・検証 =====

def _parse_license_file(content: str) -> Optional[dict]:
    """ライセンスファイルの内容をパースして検証済みJSONを返す"""
    # BEGIN/END マーカー間を抽出
    try:
        start = content.index(_BEGIN_MARKER) + len(_BEGIN_MARKER)
        end = content.index(_END_MARKER)
    except ValueError:
        return None

    b64_data = content[start:end].strip()
    if not b64_data:
        return None

    # Base64 デコード → JSON
    try:
        decoded = base64.b64decode(b64_data)
        data = json.loads(decoded)
    except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        return None

    # 必須フィールド確認
    key = data.get("k", "")
    timestamp = data.get("t", "")
    signature = data.get("s", "")
    if not key or not timestamp or not signature:
        return None

    # HMAC 署名検証
    expected_sig = _compute_signature(key, timestamp)
    if not hmac.compare_digest(signature, expected_sig):
        return None

    # キーフォーマット + チェックサム検証
    if not _validate_key(key):
        return None

    return data


def find_valid_license() -> Optional[str]:
    """有効なライセンスファイルを探してキーを返す。見つからなければ None"""
    for path in _get_license_paths():
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                data = _parse_license_file(content)
                if data:
                    return data["k"]
            except (OSError, UnicodeDecodeError):
                continue
    return None


# ===== キャッシュ付き公開API =====

_cached_status: Optional[bool] = None


def check_license_cached() -> bool:
    """起動時にライセンス状態をキャッシュして返す"""
    global _cached_status
    if _cached_status is None:
        _cached_status = find_valid_license() is not None
    return _cached_status


def refresh_license() -> bool:
    """ライセンス状態を再チェック（キャッシュを更新）"""
    global _cached_status
    _cached_status = find_valid_license() is not None
    return _cached_status


# ===== 生成（販売用） =====

def generate_key() -> str:
    """有効なライセンスキーを生成"""
    payload = "".join(random.choice(_CHARSET) for _ in range(11))
    total = sum(_CHARSET.index(c) * (i + 1) for i, c in enumerate(payload))
    check_char = _CHARSET[total % len(_CHARSET)]
    all_chars = payload + check_char
    return f"VK-{all_chars[0:4]}-{all_chars[4:8]}-{all_chars[8:12]}"


def generate_license_file(output_path: str) -> str:
    """署名付きライセンスファイルを生成して保存する。キーを返す。"""
    key = generate_key()
    timestamp = str(int(time.time()))
    signature = _compute_signature(key, timestamp)

    data = json.dumps({"k": key, "t": timestamp, "s": signature})
    b64 = base64.b64encode(data.encode("utf-8")).decode("ascii")

    # 76文字ごとに改行（PEM風）
    lines = [b64[i:i + 76] for i in range(0, len(b64), 76)]
    b64_formatted = "\n".join(lines)

    content = f"{_BEGIN_MARKER}\n{b64_formatted}\n{_END_MARKER}\n"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return key
