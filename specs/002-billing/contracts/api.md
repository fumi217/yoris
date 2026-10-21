# API Contract: spec 002（J：システム利用料）

spec 001 の [contracts/api.md](../../001-family-priority-report/contracts/api.md) の「共通の決まり」（先頭は `/api`、書き込みは `X-Requested-With: fetch`、エラーの形、文言はコードで返す）に従う。
ここでは、決済で足す API と、例外だけを書く。担当はすべてようこ。

## 使うエラー

spec 001 の表にあるもの（`not_found`・`too_many_attempts`・`validation_error`）は同じコードを使い、決済だけのもの（`already_subscribed`・`signup_in_progress`・`email_mismatch`・`payment_service_unavailable`）を足す。

| HTTP | code | いつ | spec |
|---|---|---|---|
| 404 | `not_found` | 施設がすでにあるときの申し込みページ・申し込み（理由は出さない） | FR-016・US1 のシナリオ 9 |
| 409 | `already_subscribed` | 契約中なのに申し込もうとした | US1 のシナリオ 8 |
| 409 | `signup_in_progress` | ほかの申し込みが支払い待ち（作り込み） | FR-014 |
| 422 | `email_mismatch` | 2 回入力したメールアドレスが違う | FR-004・US1 のシナリオ 5 |
| 422 | `validation_error` | 必須の項目がない、パスワードの長さが決まりの外（R-06） | |
| 429 | `too_many_attempts` | 短い時間に何度も申し込んだ（作り込み。spec 001 のログインの試行回数の制限と同じコード） | FR-027 |
| 502 | `payment_service_unavailable` | Stripe を呼べなかった | |

## 申し込みページ（ログインなし）

| API | 誰が | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/billing/signup` | だれでも | ミ | プラン名・月額（`{plan_name, amount_jpy}`）。施設がすでにあれば 404 | FR-001・FR-016 |
| `POST /api/billing/signup` | だれでも | ミ | 本文 `{idempotency_key, facility_name, director_name, email, email_confirm, password}`。申し込みを作り、支払い画面の URL（`{checkout_url}`）を返す。同じ `idempotency_key` なら同じ URL（R-12）。施設がすでにあれば 404 | FR-001・FR-004・FR-006・FR-013 |
| `POST /api/billing/signup/cancel` | だれでも | ミ | 本文 `{idempotency_key}`。支払い画面から「戻る」で戻ったときに、その申し込みの支払い画面を失効させ、申し込みを消す（R-07）。対象は `pending` の申し込みだけ。`completed`・`rejected`・ないときは何もせず 204 | US1 のシナリオ 3・FR-006 |
| `GET /api/billing/signup/complete?session_id=` | だれでも | ミ | `{status}`：`confirming`（知らせ待ち）／`completed`（`login_id` も返す）／`not_completed`（支払われていない・期限切れ）。`session_id` は Stripe が付ける推測できない値。ID を返すのは、アカウントを作ってから 1 時間まで | FR-003・US1 のシナリオ 2〜4 |

- `POST /api/billing/signup` は、ほかの書き込みと同じく `X-Requested-With: fetch` を確かめる（FR-027）。
- パスワード・メールアドレスは、レスポンス・ログに出さない（FR-006・FR-023）。

## Stripe からの知らせ

| API | 誰が | 時期 | 中身 | spec |
|---|---|---|---|---|
| `POST /api/billing/webhook` | Stripe | ミ | 本文をそのまま署名の確認にかける。確かめられなければ 400。処理できたら 200（同じ知らせは何もせず 200）。処理に失敗したら 500（Stripe が送り直す） | FR-009〜FR-012 |

- **ログインと `X-Requested-With` の確認の対象外**（Stripe は付けないため）。代わりに `Stripe-Signature` ヘッダーの署名で確かめる（R-03）。

## 管理画面（施設長・事務員）

役割が `director`（施設長）・`clerk`（事務員）でないときは、spec 001 と同じく 403（`forbidden`）。
家族の画面の行き先には管理画面がないので、家族が URL を開いても画面は「ページが見つかりません」になる（FR-007）。
API を直接呼んだときは、家族にも 403 を返す（spec 001 の contracts と同じ決まり。役割のチェックを 1 つの形にそろえるため。
管理画面の API があること自体は、フロントのコードから分かるので、404 にしても隠せない。FR-007 の「知らせない」は画面のことと考える。PR #25 みさき）。

| API | 時期 | 中身 | spec |
|---|---|---|---|
| `GET /api/admin/billing` | ミ | `{status, plan_name, amount_jpy, current_period_end, cancel_at, can_subscribe, can_manage}`。`can_subscribe` は解約済みのとき true。`can_manage` は Stripe とつながっているとき true（初期データの施設は false） | FR-018・US2 |
| `POST /api/admin/billing/checkout` | 作 | 申し込み直し。開いている支払い画面があれば同じ URL を返す。契約中・解約予定・支払いに失敗のときは 409 `already_subscribed` | FR-001・FR-013 |
| `POST /api/admin/billing/portal` | 作 | Customer Portal の URL（`{portal_url}`）を返す。`can_manage` が false なら 409 | FR-020・US3 |

## 画面（フロントエンド）

| 画面 | パス | 誰が | 時期 |
|---|---|---|---|
| 申し込みページ | `/signup` | だれでも（ログインなし） | ミ |
| 申し込み完了 | `/signup/complete` | だれでも（Stripe から戻る先） | ミ |
| 利用料のお支払い | `/admin/billing` | 施設長・事務員 | ミ（契約の状態だけ）・作（申し込み直し・カードの変更など） |
