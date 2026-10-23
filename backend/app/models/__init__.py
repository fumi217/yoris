"""テーブルの定義。

Alembic がすべてのテーブルを見つけられるよう、機能のファイルを足したらここで import する。
"""

from app.models import core, records, visits  # noqa: F401
