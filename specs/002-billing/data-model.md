# Data Model: spec 002（J：システム利用料）

spec 001 の [data-model.md](../001-family-priority-report/data-model.md) の共通の土台（`facilities`・`users`・`staff`）に、決済の列とテーブルを足す。担当はすべてようこ。
理由は [research.md](./research.md) を見る。

## テーブルの一覧

| テーブル | 中身 | 時期 | spec |
|---|---|---|---|
| `facilities`（列を足す） | 利用料の連絡先と、Stripe の顧客 | ミニマム | FR-002・FR-025 |
| `facility_subscriptions` | 施設の契約（施設に 1 つ） | ミニマム | FR-009・FR-015・FR-018 |
| `subscription_status_histories` | 契約の状態の変更履歴 | ミニマム | FR-019 |
| `billing_applications` | 申し込みページからの申し込み（支払いが確かめられるまで） | ミニマム | FR-001・FR-002・FR-006・FR-013・FR-014 |
| `billing_events` | 受け取った Stripe の知らせ（同じ知らせを 2 回処理しないため） | ミニマム | FR-010・FR-011 |

## `facilities`（spec 001 のテーブルに列を足す）

| 列 | 型 | 説明 |
|---|---|---|
| billing_email | text | 利用料について連絡するメールアドレス（申し込みのときの連絡用のアドレス）。一意にしない。初期データの施設は空（R-09） |
| stripe_customer_id | text | Stripe の顧客の ID。一意。初期データの施設は空 |

- 施設は 1 つだけ（FR-016）。2 つ目を作らないことは、作る処理の中で確かめる（R-04）。

## `users`・`staff`（spec 001 のまま。施設長の作り方だけ決める）

- 申し込みで作る施設長は、`users`（`kind=staff`、`login_id` はシーケンスから作る `s00001` の形、`password_hash` は申し込みのときのもの）と、
  `staff`（`role=director`、`display_name` は申し込みのときの施設長の名前）の 2 行（R-04・R-06）。
- `users.email` は使わない（家族だけの列。R-09）。
- **基盤への追加**：`login_id` を作るためのシーケンス `staff_login_id_seq` を、T009 のマイグレーションで作る（職員のアカウントを作る T088 と、初期データ T015 も同じものを使う）。

## `facility_subscriptions`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | **一意**（施設に 1 つ。FR-015） |
| status | text | `active`／`payment_failed`／`cancel_scheduled`／`canceled`（R-05） |
| stripe_subscription_id | text | Stripe の契約の ID。初期データの施設は空 |
| current_period_end | timestamptz | 次の請求日（今の期間の終わり）。初期データの施設は空 |
| cancel_at | timestamptz | 解約予定のとき、使える最後の日時 |
| open_checkout_session_id | text | 申し込み直しで開いている支払い画面（R-10。作り込み） |
| open_checkout_expires_at | timestamptz | その支払い画面の期限 |
| updated_at | timestamptz | |

- 状態は、Stripe から読み直した契約に合わせて上書きする（R-03）。状態が変わったら、同じトランザクションで履歴を足す。

### 状態の動き

```text
（申し込みの支払いが確かめられる）→ active
active → payment_failed（毎月の支払いに失敗） → active（再請求で払えた）
active → cancel_scheduled（Customer Portal で解約） → active（解約の取り消し）
cancel_scheduled → canceled（期間が終わった）
payment_failed → canceled（再請求でも払えなかった）
canceled → active（申し込み直し。作り込み）
```

## `subscription_status_histories`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | |
| from_status | text | 初めて作ったときは空 |
| to_status | text | |
| stripe_event_id | text | 変わるきっかけになった知らせ（初期データは空） |
| changed_at | timestamptz | |

## `billing_applications`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| idempotency_key | text | **一意**。申し込みページが開いたときに作る値（二度押し対策。R-12） |
| facility_name | text | 施設名。`completed`・`rejected` になったら消す（R-04） |
| director_name | text | 施設長の名前。同上 |
| contact_email | text | 連絡用のメールアドレス。同上 |
| password_hash | text | bcrypt。同上 |
| status | text | `pending`（支払い待ち）／`completed`（アカウントを作った）／`rejected`（施設がすでにあったので作らず、Stripe の契約を解約した） |
| stripe_checkout_session_id | text | **一意**。Stripe の支払い画面 |
| checkout_url | text | 二度押しのときに同じ画面を返すため |
| expires_at | timestamptz | 支払い画面の期限（30 分。R-07） |
| created_facility_id | bigint → facilities | `completed` のとき |
| created_user_id | bigint → users | `completed` のとき。完了の画面で ID を出すため |
| created_at | timestamptz | |

- 期限が切れた申し込み（`checkout.session.expired`）と、支払い画面から「戻る」で取り消した申し込み（R-07）は、行ごと消す（FR-006）。
- `completed`・`rejected` の行は、id・状態・Stripe の Checkout Session の ID・作った施設とアカウントの id だけを残す（完了の画面と、問い合わせのときの確認のため）。
- 作り込み：期限内の `pending` があるあいだは、新しい申し込みを受け付けない（FR-014）。
- 支払い画面を作れなかった（Stripe の呼び出しが失敗した）ときは、行を消してエラーを返す。

## `billing_events`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| stripe_event_id | text | **一意**。同じ知らせが来たら、何もしない（FR-011） |
| type | text | 知らせの種類（`checkout.session.completed` など） |
| received_at | timestamptz | |

- 知らせの中身（本文）は保存しない（メールアドレスなどが入るため）。必要なときは Stripe の管理画面で見る。
- 知らせの処理と、この行の追加は同じトランザクションで行う。処理が失敗したら行も残らないので、Stripe の再送で処理し直せる。

## 初期データ（spec 001 の T015 に足すもの）

- 施設がまだなければ、施設を作り、`facility_subscriptions` を `status=active`（Stripe とつながっていない）で作る。
- 施設がすでにあれば（申し込みで作ったあと）、施設も契約も作らず、入居者・職員・家族だけを足す。
