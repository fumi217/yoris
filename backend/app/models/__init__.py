"""テーブルの定義。

Alembic がすべてのテーブルを見つけられるよう、機能のファイルを足したらここで import する。
"""

from app.models import (  # noqa: F401
    album,
    billing,
    change_flags,
    core,
    disclosure,
    files,
    inquiry,
    memos,
    notifications,
    records,
    replies,
    requests,
    visits,
)
