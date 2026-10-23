"""テーブルの定義。

Alembic がすべてのテーブルを見つけられるよう、機能のファイルを足したらここで import する。
"""

from app.models import (  # noqa: F401
    core,
    disclosure,
    notifications,
    records,
    requests,
    visits,
)
