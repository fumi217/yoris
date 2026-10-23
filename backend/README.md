# Backend

FastAPI のバックエンド（Python 3.13）。技術の前提は [CLAUDE.md](../CLAUDE.md) と [docs/技術選定.md](../docs/技術選定.md)、
置き場所の決まりは [spec 001 の plan.md](../specs/001-family-priority-report/plan.md) の「Project Structure」を見る。

## 動かし方

リポジトリの一番上で `docker compose up -d` を実行すると、http://localhost:8000 で動く（API の一覧は http://localhost:8000/docs）。
ファイルを保存すると自動で読み直す。

- **worker**（メールの送信・20 時のまとめ。T057 ができるまでは `docker compose --profile worker up -d worker` で起動）は自動では読み直さない。`app/jobs/` などを変えたら `docker compose restart worker` で再起動する。
- アップロードしたファイルは、名前つきのボリューム `uploads`（コンテナの中の `/data/uploads`）に置く。手元の `backend/` には残らない。

## DB とマイグレーション

- テーブルの定義は `app/models/<機能>.py` に、`app.db.Base` を継承して書く。足したファイルは `app/models/__init__.py` で import する（Alembic が見つけられるように）。
  共通の土台（施設・ログインの情報・入居者・家族アカウント・職員）は `app/models/core.py`。
- 型は `Mapped[int]`（bigint）・`Mapped[str]`（text）・`Mapped[datetime]`（timestamptz）と書くと、data-model.md の決まりどおりになる。選択肢のある列は `check_in` で CHECK 制約を付ける。
- API では `session: Annotated[Session, Depends(get_session)]` でセッションを受け取り、書き込んだら `session.commit()` を呼ぶ。
  - **commit するのは API の関数の最後の 1 回だけ**。サービスの関数（`services/` の中。`create_reply_notice` など）は、受け取ったセッションに書くだけで commit しない（途中で失敗したら、全部まとめて取り消されるように）。
  - worker・決まった時刻の処理（`run_jobs()`）・`BackgroundTasks` など、API の応答のあとに動く処理は、API のセッションが閉じているので、自分で開く：`with Session(get_engine()) as session:`（`from sqlalchemy.orm import Session`、`from app.db import get_engine`）。

```bash
docker compose exec backend alembic upgrade head        # 今のマイグレーションを DB に当てる（最初の 1 回と、main を取り込んだあと）
docker compose exec backend alembic revision --autogenerate -m "<短い英語名>"   # 定義を変えたら、マイグレーションを作る
docker compose exec backend alembic downgrade -1        # 1 つ戻す
```

- **作る前に、必ず main を取り込む**（spec 001 の research.md R-17。2 人が同時に作ると head が 2 つになるため）。
- 自動で作ったファイルは、そのまま使わずに読む。シーケンスなど、自動では出ないものがある（最初のマイグレーションでは、シーケンスを手で足した）。
- 作ったファイルが手元で root の持ち物になるときは、`docker compose run --rm --user "$(id -u):$(id -g)" backend alembic revision ...` で作る。

## 確認のコマンド（CI と同じ）

```bash
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .   # 整形するときは --check を外す
docker compose exec backend python -m pytest
```

## 依存

- 本番でも使うものは `requirements.txt`、開発・テストだけで使うものは `requirements-dev.txt` に、`==` で版を固定して書く。
- 足したら `docker compose build backend` で作り直す。新しいライブラリは、チームに共有して `docs/技術選定.md` に理由を書く。
