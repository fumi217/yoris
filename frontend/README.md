# Frontend

このディレクトリには、本プロジェクトのフロントエンドアプリケーションを配置する。

## 技術スタック

| 種別             | 採用技術 |
| ---------------- | -------- |
| 言語             | TypeScript |
| フレームワーク   | （例：Next.js / React）|
| スタイリング     | （例：Tailwind CSS / CSS Modules）|
| 状態管理         | （例：Zustand / TanStack Query）|
| テスト           | （例：Vitest / Playwright）|
| Lint / Format    | ESLint / Prettier |

> 詳細は [`docs/技術選定.md`](../docs/技術選定.md) を参照。

## 前提

- Node.js: `.nvmrc` / `package.json` の `engines` に従う
- パッケージマネージャ：（例：pnpm / npm / yarn）

## セットアップ

```bash
# 依存関係のインストール
pnpm install

# 環境変数ファイルの用意
cp .env.example .env.local
```

## 開発

```bash
pnpm dev          # 開発サーバー起動
pnpm build        # 本番ビルド
pnpm start        # 本番ビルドの起動
pnpm lint         # Lint
pnpm test         # テスト実行
```

## ディレクトリ構成（例）

```
frontend/
├── public/             # 静的ファイル
├── src/
│   ├── app/            # ルーティング / ページ
│   ├── components/     # 再利用可能な UI コンポーネント
│   ├── features/       # 機能単位のモジュール
│   ├── lib/            # ユーティリティ / API クライアント
│   └── styles/         # グローバルスタイル
└── tests/              # テストコード
```

## コーディング規約

- フォーマッタ・Lint は CI で強制する。
- コンポーネントは単一責務を意識し、`features/` 配下に機能ごとに整理する。
- 型は `any` を避け、API レスポンスは OpenAPI スキーマから自動生成することを推奨。

## 関連ドキュメント

- [PRD](../docs/PRD.md)
- [要件定義](../docs/要件定義.md)
- [画面設計](../docs/画面設計.md)
- [API 設計](../docs/API設計.md)
- [テスト設計書](../docs/テスト設計書.md)
- [セキュリティ設計](../docs/セキュリティ設計.md)
