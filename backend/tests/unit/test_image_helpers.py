"""テスト用の架空の画像の補助（005-T005）が、ちゃんとした形かを確かめる。"""

import struct
import zlib

from app.models.files import MAX_UPLOAD_BYTES
from app.services.uploads import detect_content_type
from tests.helpers.images import fake_jpeg, fake_png, oversize_image, pdf_named_jpg


def test_fake_jpeg_and_png_are_recognised_by_the_first_bytes():
    assert detect_content_type(fake_jpeg()) == "image/jpeg"
    assert detect_content_type(fake_png()) == "image/png"


def test_pdf_named_jpg_is_a_pdf_by_content():
    name, data = pdf_named_jpg()

    assert name.endswith(".jpg")
    assert detect_content_type(data) == "application/pdf"


def test_oversize_images_are_one_byte_over_the_limit():
    for kind, expected in (("jpeg", "image/jpeg"), ("png", "image/png")):
        data = oversize_image(kind)

        assert len(data) == MAX_UPLOAD_BYTES + 1
        assert detect_content_type(data) == expected


def test_fake_png_is_a_well_formed_one_by_one_png():
    data = fake_png()

    # チャンクを順にたどり、長さと CRC が合うこと・IHDR が 1×1 であることを確かめる
    position = 8
    kinds = []
    while position < len(data):
        (length,) = struct.unpack(">I", data[position : position + 4])
        kind = data[position + 4 : position + 8]
        body = data[position + 8 : position + 8 + length]
        (crc,) = struct.unpack(">I", data[position + 8 + length : position + 12 + length])
        assert crc == zlib.crc32(kind + body)
        if kind == b"IHDR":
            assert struct.unpack(">II", body[:8]) == (1, 1)
        kinds.append(kind)
        position += 12 + length
    assert kinds == [b"IHDR", b"IDAT", b"IEND"]
