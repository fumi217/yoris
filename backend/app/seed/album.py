"""アルバムのデモ用の写真（spec 005 の 005-T032）。

初期データの仕組み（001-T015 の `python -m app.seed`）から呼ぶ。入居者と職員を入れたあとに呼ぶこと。
写真は、コードの中で作った架空の風景（空・丘・太陽だけ。人の顔は写らない）で、画像ファイルは
リポジトリに置かない。Pillow は使わない（Session 2026-10-28）ので、標準ライブラリだけで PNG を作る。
同じ入居者に、すでに写真があれば足さない（何度流しても同じになるように）。
"""

import math
import struct
import zlib
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now
from app.models.album import AlbumPhoto
from app.services.album import ALBUM_FILE_TYPES
from app.services.uploads import save_upload

WIDTH = 320
HEIGHT = 240
HORIZON = 150  # 丘の高さの目安（上から）

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Scene:
    sky: Color
    hill: Color
    sun: Color
    comment: str | None
    minutes_ago: int  # 載せた日時（いまから何分前か。日ごとに並ぶように、1 日以上前も入れる）


# 季節の違う、架空の風景。コメントは架空で、1 枚はコメントなし
SAMPLE_SCENES = [
    Scene((150, 210, 240), (110, 180, 100), (255, 220, 80), "お庭の花がきれいでした", 10),
    Scene((90, 160, 225), (50, 130, 70), (255, 245, 150), None, 90),
    Scene(
        (245, 190, 130), (190, 140, 70), (255, 230, 170), "みんなで、お散歩に出かけました", 26 * 60
    ),
    Scene((190, 205, 225), (235, 240, 245), (250, 250, 250), "季節の飾りを作りました", 28 * 60),
]


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def landscape_png(scene: Scene) -> bytes:
    """空・なだらかな丘・太陽だけの、小さな風景の PNG（ブラウザで表示できる）。"""
    rows = bytearray()
    for y in range(HEIGHT):
        rows.append(0)  # 行のフィルター（なし）
        for x in range(WIDTH):
            hill_top = HORIZON - int(30 * math.sin(math.pi * x / WIDTH))
            if (x - 250) ** 2 + (y - 55) ** 2 <= 24**2:
                color = scene.sun
            elif y >= hill_top:
                color = scene.hill
            else:
                color = scene.sky
            rows.extend(color)
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)  # 8 ビット、RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )


def add_sample_photos(session: Session, *, resident_id: int, staff_id: int) -> int:
    """入居者に、デモの写真を足し、足した枚数を返す。commit は呼んだ側が行う。

    staff_id は、載せた職員（介護職員）。すでにその入居者に写真があれば、何も足さない。
    """
    if session.scalars(select(AlbumPhoto.id).where(AlbumPhoto.resident_id == resident_id)).first():
        return 0
    current = now()
    for scene in SAMPLE_SCENES:
        saved = save_upload(
            session,
            data=landscape_png(scene),
            purpose="album",
            uploaded_by=staff_id,
            allowed_types=ALBUM_FILE_TYPES,
        )
        session.add(
            AlbumPhoto(
                resident_id=resident_id,
                file_id=saved.id,
                comment=scene.comment,
                posted_by=staff_id,
                posted_at=current - timedelta(minutes=scene.minutes_ago),
            )
        )
    session.flush()
    return len(SAMPLE_SCENES)
