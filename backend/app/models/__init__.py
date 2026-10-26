"""テーブルの定義。

Alembic がすべてのテーブルを見つけられるよう、機能のファイルを足したらここで import する。
"""

from app.models import (  # noqa: F401
    billing,
    core,
    disclosure,
    inquiry,
    memos,
    notifications,
    records,
    replies,
    requests,
    visits,
)
