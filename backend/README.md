# Backend

FastAPI のバックエンド（Python 3.13）。技術の前提は [CLAUDE.md](../CLAUDE.md) と [docs/技術選定.md](../docs/技術選定.md)、
置き場所の決まりは [spec 001 の plan.md](../specs/001-family-priority-report/plan.md) の「Project Structure」を見る。

## 動かし方

リポジトリの一番上で `docker compose up -d` を実行すると、http://localhost:8000 で動く（API の一覧は http://localhost:8000/docs）。
ファイルを保存すると自動で読み直す。

- **worker**（メールの送信・20 時のまとめ。T057 ができるまでは `docker compose --profile worker up -d worker` で起動）は自動では読み直さない。`app/jobs/` などを変えたら `docker compose restart worker` で再起動する。
- アップロードしたファイルは、名前つきのボリューム `uploads`（コンテナの中の `/data/uploads`）に置く。手元の `backend/` には残らない。

## 確認のコマンド（CI と同じ）

```bash
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .   # 整形するときは --check を外す
docker compose exec backend python -m pytest
```

## 依存

- 本番でも使うものは `requirements.txt`、開発・テストだけで使うものは `requirements-dev.txt` に、`==` で版を固定して書く。
- 足したら `docker compose build backend` で作り直す。新しいライブラリは、チームに共有して `docs/技術選定.md` に理由を書く。
