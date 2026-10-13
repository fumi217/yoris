# DB 設計

> ER 図は draw.io で作成し、リポジトリ内（例：`docs/diagrams/erd.drawio`）で管理することを推奨。
>
> - draw.io: https://www.drawio.com/
> - VSCode Extension: Draw.io Integration

## 1. 設計方針

- 採用 DBMS（例：PostgreSQL / MySQL）
- 命名規則（テーブル：複数形 / カラム：snake_case など）
- 物理削除 / 論理削除の方針
- マイグレーション運用方針

## 2. ER 図

> ![ERD](./diagrams/erd.svg)

## 3. テーブル定義

### users

| カラム名    | 型           | NULL | デフォルト | 説明                 |
| ----------- | ------------ | ---- | ---------- | -------------------- |
| id          | bigint       | NO   |            | 主キー               |
| email       | varchar(255) | NO   |            | ユーザーのメール     |
| password    | varchar(255) | NO   |            | ハッシュ済みパスワード |
| created_at  | timestamp    | NO   | now()      | 作成日時             |
| updated_at  | timestamp    | NO   | now()      | 更新日時             |

## 4. インデックス・制約

- ユニーク制約、外部キー、複合インデックスなど。

## 5. データ保持・整合性ルール

- 保存期間、アーカイブ、削除ポリシー。
