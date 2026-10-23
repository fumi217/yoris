"""DB のつなぎ方。テーブルの定義は app/models/ に置き、Base を継承する。

API では `Annotated[Session, Depends(get_session)]` で、1 つのリクエストに 1 つのセッションを使う。
書き込んだら、API の関数の最後で 1 回だけ `session.commit()` を呼ぶ
（呼ばずに終わると取り消される）。サービスの関数は commit しない。
API の応答のあとに動く処理は、`with Session(get_engine())` で自分で開く。
"""

from collections.abc import Iterator
from datetime import datetime
from functools import cache

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Engine, MetaData, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import get_settings

# 制約の名前の付け方をそろえる
# （あとのマイグレーションで、消したり変えたりするときに名前で指せるように）
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # data-model.md の決まり（id は bigint、文字は text、日時は timestamptz）を、
    # 型の書き方から決める
    type_annotation_map = {
        int: BigInteger,
        str: Text,
        datetime: DateTime(timezone=True),
    }


def check_in(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    """列の値を決まった選択肢に限る CHECK 制約。

    ENUM の代わりに使う（選択肢を足すときは、制約の付け替えで済む）。

    values はコードに書いた定数だけを渡す（利用者の入力を渡さない）。
    """
    allowed = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)


@cache
def get_engine() -> Engine:
    """最初に使うときに 1 回だけ作る（DB がなくても、import するだけなら動くように）。"""
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL が設定されていません（キー名は env.example）")
    # pool_pre_ping：DB を再起動したあとに、切れた接続を使って失敗しないように
    return create_engine(database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
