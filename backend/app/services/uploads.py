"""ファイルを預かる共通の処理（spec 001 の 001-T069。research.md R-10・FR-034）。

お知らせの添付（PDF）とアルバムの写真（JPEG・PNG）は、ここを通す。

- 形式は、ファイルの先頭のバイトで確かめる。拡張子や、送られてきた Content-Type は見ない
- 10MB まで。空のファイルも受け付けない
- 保存名は、推測できない乱数にする。元のファイル名は使わない（保存先の中の名前と、見せる名前は別）
- 関数の中では commit しない（呼んだ API が最後に 1 回だけ commit する）
- 本体を全部メモリに読む形なので、呼ぶ側は、上限 + 1 バイトまでしか読まないこと
  （上限を超えたら、それ以上読まずに断る）
"""

import secrets
from collections.abc import Collection
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, ErrorCode
from app.models.files import FILE_CONTENT_TYPES, MAX_UPLOAD_BYTES, UPLOAD_PURPOSES, UploadedFile

# 先頭のバイトと、その形式（research.md R-10）
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG", "image/png"),
)


def detect_content_type(data: bytes) -> str | None:
    """先頭のバイトから形式を決める。PDF・JPEG・PNG のどれでもなければ None。"""
    for signature, content_type in _SIGNATURES:
        if data.startswith(signature):
            return content_type
    return None


def _upload_dir() -> Path:
    directory = get_settings().upload_dir
    if not directory:
        raise RuntimeError("UPLOAD_DIR が設定されていません")
    return Path(directory)


def _write(storage_key: str, data: bytes) -> None:
    """保存先に書く。本番の保存先（オブジェクトストレージ。001-T076）に替えるときは、ここだけ替える。"""
    directory = _upload_dir()
    directory.mkdir(parents=True, exist_ok=True)
    # "xb"：同じ名前がすでにあれば失敗する（別のファイルを上書きしない）
    with open(directory / storage_key, "xb") as stored:
        stored.write(data)


def read_upload(storage_key: str) -> bytes:
    """保存したバイト列を読む。保存先から消えているときは OSError。"""
    return (_upload_dir() / storage_key).read_bytes()


def delete_stored(storage_key: str) -> None:
    """保存先のファイルを消す。すでにないときは何もしない（消せなければ OSError）。

    本番の保存先に替えるときは、_write・read_upload と一緒に、ここも替える。
    """
    (_upload_dir() / storage_key).unlink(missing_ok=True)


def save_upload(
    session: Session,
    *,
    data: bytes,
    purpose: str,
    uploaded_by: int,
    allowed_types: Collection[str] = FILE_CONTENT_TYPES,
) -> UploadedFile:
    """形式と大きさを確かめて保存し、uploaded_files に 1 行足す。

    断るときは invalid_file（422）。purpose・allowed_types は呼ぶ側が決める固定の値で、
    利用者の入力ではない（purpose が違えばプログラムの間違い）。
    allowed_types は、受け付ける形式（既定は PDF・JPEG・PNG）。アルバムは JPEG・PNG だけを渡す。
    """
    if purpose not in UPLOAD_PURPOSES:
        raise ValueError(f"purpose が正しくありません: {purpose}")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise AppError(ErrorCode.INVALID_FILE)
    content_type = detect_content_type(data)
    if content_type is None or content_type not in allowed_types:
        raise AppError(ErrorCode.INVALID_FILE)

    uploaded = UploadedFile(
        storage_key=secrets.token_urlsafe(32),
        content_type=content_type,
        size_bytes=len(data),
        purpose=purpose,
        uploaded_by=uploaded_by,
    )
    session.add(uploaded)
    # 先に行を確定して（id を得て）から書く。書けなかったら例外で止まり、呼んだ側が取り消す
    session.flush()
    _write(uploaded.storage_key, data)
    return uploaded
