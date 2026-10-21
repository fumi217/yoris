"""Alembic の実行の設定。DB の場所は DATABASE_URL、テーブルの定義は app/models/ から読む。"""

from logging.config import fileConfig

from alembic import context

import app.models  # noqa: F401  すべてのテーブルを Base.metadata に登録する
from app.db import Base, get_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB につながずに SQL だけを出す（`alembic upgrade head --sql`）。"""
    context.configure(
        url=get_engine().url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        # compare_type：列の型の変更も、自動で作るマイグレーションに出す
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
