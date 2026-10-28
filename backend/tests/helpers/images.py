"""テスト用の架空の画像を、テストの中で作る（spec 005 の 005-T005。research.md R-08）。

実在の人物の写真は使わない。どれも、中身のない小さなバイト列で、個人情報・位置情報は入っていない。
Pillow は使わない（Exif の除去・向きの直し・サムネイルはやらない。Session 2026-10-28）ので、
画像としてちゃんと開けるのは fake_png だけ。ほかは、先頭のバイトで形式が決まる最小のバイト列
（API の形式の確認・大きさの確認のテスト用）。

縦向きの写真の表示は、ブラウザが向きの情報で直す。テストでは確かめず、実機で確かめる
（specs/005-album/quickstart.md の手順 6）。
"""

import struct
import zlib

from app.models.files import MAX_UPLOAD_BYTES

_PDF = b"%PDF-1.4\n%fake\n"
_JPEG_HEAD = b"\xff\xd8\xff\xe0"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def fake_jpeg() -> bytes:
    """先頭が JPEG の、小さなバイト列（画像としては開けない）。"""
    return _JPEG_HEAD + b"\x00" * 16 + b"\xff\xd9"


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def fake_png() -> bytes:
    """本物の 1×1 の PNG（ブラウザで表示できる）。"""
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1×1、8 ビット、RGB
    pixel = zlib.compress(b"\x00\xcc\xcc\xcc")  # フィルターなし + 灰色の 1 画素
    return (
        _PNG_SIGNATURE
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", pixel)
        + _png_chunk(b"IEND", b"")
    )


def pdf_named_jpg() -> tuple[str, bytes]:
    """名前だけ `.jpg` の PDF（拡張子ではなく、中身で断ることを確かめる）。"""
    return "photo.jpg", _PDF


def oversize_image(kind: str = "jpeg") -> bytes:
    """10MB（MAX_UPLOAD_BYTES）を 1 バイト超えた画像。kind は jpeg か png。"""
    head = {"jpeg": fake_jpeg(), "png": _PNG_SIGNATURE}[kind]
    return head + b"\x00" * (MAX_UPLOAD_BYTES + 1 - len(head))
