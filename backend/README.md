# Backend

このディレクトリには、本プロジェクトのバックエンドアプリケーションを配置する。

## 技術スタック

| 種別             | 採用技術 |
| ---------------- | -------- |
| 言語             | TypeScript |
| フレームワーク   | （例：Express / NestJS）|
| ORM              | （例：Prisma / TypeORM）|
| DB               | （例：PostgreSQL）|
| 認証             | （例：JWT / OAuth）|
| テスト           | （例：Vitest / Jest + Supertest）|
| Lint / Format    | ESLint / Prettier |

> 詳細は [`docs/技術選定.md`](../docs/技術選定.md) を参照。

## 前提

- Node.js: `.nvmrc` / `package.json` の `engines` に従う
- パッケージマネージャ：（例：pnpm / npm / yarn）
- Docker / Docker Compose（DB のローカル起動用）

## セットアップ

```bash
# 依存関係のインストール
pnpm install

# 環境変数ファイルの用意
cp .env.example .env

# DB をローカルで起動
docker compose up -d

# マイグレーション
pnpm migrate
```

## 開発

```bash
pnpm dev          # 開発サーバー起動（ホットリロード）
pnpm build        # 本番ビルド
pnpm start        # 本番ビルドの起動
pnpm lint         # Lint
pnpm test         # テスト実行
pnpm migrate      # DB マイグレーション
```

## ディレクトリ構成（例）

```
backend/
├── src/
│   ├── routes/         # ルーティング定義
│   ├── controllers/    # リクエスト/レスポンスのハンドリング
│   ├── services/       # ビジネスロジック
│   ├── repositories/   # データアクセス層
│   ├── domain/         # ドメインモデル
│   ├── middlewares/    # 認証 / ロギング等のミドルウェア
│   └── config/         # 設定
├── prisma/             # スキーマ・マイグレーション（採用時）
├── tests/              # テストコード
└── openapi.yaml        # OpenAPI スキーマ
```

## API ドキュメント

- OpenAPI スキーマ：`backend/openapi.yaml`
- Swagger UI：開発時は `/docs` で参照可能（例）

## コーディング規約

- レイヤ間の依存方向を守る（routes → controllers → services → repositories）。
- ドメインロジックはフレームワーク非依存に保つ。
- すべての公開 API は OpenAPI スキーマで仕様を管理する。

## 関連ドキュメント

- [PRD](../docs/PRD.md)
- [要件定義](../docs/要件定義.md)
- [API 設計](../docs/API設計.md)
- [DB 設計](../docs/DB設計.md)
- [テスト設計書](../docs/テスト設計書.md)
- [運用設計](../docs/運用設計.md)
- [性能設計](../docs/性能設計.md)
- [ログ設計](../docs/ログ設計.md)
- [可用性設計](../docs/可用性設計.md)
- [セキュリティ設計](../docs/セキュリティ設計.md)
