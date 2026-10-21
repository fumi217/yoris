# Frontend

React（Vite）・TypeScript のフロントエンド（Node 24）。技術の前提は [CLAUDE.md](../CLAUDE.md) と [docs/技術選定.md](../docs/技術選定.md)、
置き場所の決まりは [spec 001 の plan.md](../specs/001-family-priority-report/plan.md) の「Project Structure」を見る。

## 動かし方

リポジトリの一番上で `docker compose up -d` を実行すると、http://localhost:5173 で動く。
`/api` で始まる呼び出しは、バックエンドへ中継される（同じオリジンにして CORS を開けない。research.md R-03）。

## 確認のコマンド（CI と同じ）

```bash
docker compose exec frontend npm run lint
docker compose exec frontend npm run format:check   # 整形するときは npm run format
docker compose exec frontend npm run test
docker compose exec frontend npm run build
```

## 依存

- `npm install -E <名前>`（開発だけで使うものは `-E -D`）で、版を固定して足す。`package-lock.json` もコミットする。
- 足したら `docker compose build frontend` で作り直し、`docker compose up -d --renew-anon-volumes frontend` で起動し直す
  （コンテナの中の node_modules を入れ直すため）。新しいライブラリは、チームに共有して `docs/技術選定.md` に理由を書く。
