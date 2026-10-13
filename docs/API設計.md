# API 設計

> OpenAPI（Swagger）で記述する。スキーマファイルは `backend/openapi.yaml` 等で管理し、本ドキュメントは概要と運用ルールを示す。
>
> - Swagger: https://swagger.io/
> - 参考：https://zenn.dev/nekoniki/articles/acd946cc349d1e

## 1. 設計方針

- スタイル：REST / GraphQL / RPC
- 認証方式：JWT / セッション / OAuth など
- バージョニング：URL 埋め込み（`/v1/...`）/ ヘッダー
- エラーレスポンスの共通フォーマット

## 2. エンドポイント一覧

| メソッド | パス              | 概要               | 認証   |
| -------- | ----------------- | ------------------ | ------ |
| POST     | /v1/auth/login    | ログイン           | 不要   |
| GET      | /v1/users/me      | 自分の情報を取得   | 必要   |

## 3. リクエスト / レスポンス例

````http
POST /v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "********"
}
````

````json
{
  "accessToken": "...",
  "expiresIn": 3600
}
````

## 4. エラーレスポンス

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "メールアドレスまたはパスワードが正しくありません"
  }
}
```

## 5. レート制限・冪等性

- レート制限の方針
- POST に対する冪等キーの扱いなど
