---

description: "spec 002（J：システム利用料）のタスク一覧"
---

# Tasks: 施設がアプリの月額利用料を支払う（J：システム利用料）

**Input**: `specs/002-billing/` の [spec.md](./spec.md)・[plan.md](./plan.md)・[research.md](./research.md)・[data-model.md](./data-model.md)・[contracts/api.md](./contracts/api.md)・[quickstart.md](./quickstart.md)

**Tests**: テストのタスクを含める（Constitution の課題要件「単体テストはテストコードを書く」、research.md R-11）。Stripe はモックにし、鍵を使わない。

**Organization**: User Story ごとにまとめる。担当はすべてようこなので、各タスクの末尾には **時期** だけを書く。「ミ」は Day 1〜4 のミニマム版、「作」は Day 5 の作り込み（Day は docs/マイルストーン.md の表が正。#53）（[plan.md の「ミニマム版と作り込み」](./plan.md#ミニマム版と作り込み)）。
spec 001 のタスクは「001-T009」のように書く（[spec 001 の tasks.md](../001-family-priority-report/tasks.md)）。issue のタイトルには「spec 002」を入れ、spec 001 の T 番号と区別する。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: ほかのタスクと並べて進められる（別のファイルで、終わっていないタスクに依存しない）
- **[Story]**: どの User Story のタスクか（US1〜US3）。Setup・Foundational・Polish には付けない
- パスは plan.md の構成（`backend/app/`・`frontend/src/`）に合わせる

---

## Phase 1: Setup（決済の準備）

**Purpose**: Stripe のライブラリ・鍵の置き場所・Webhook を手元で受ける仕組みを用意する

- [X] T001 `stripe==16.0.0` を `backend/requirements.txt` に足し、`docs/技術選定.md` の 7 章の表に「Stripe の公式 Python ライブラリ。Python 3.13 で入り、既知の脆弱性がないことを確かめた」と理由を足す（research.md R-01）（ミ）
- [X] T002 [P] `env.example` に `STRIPE_SECRET_KEY`・`STRIPE_WEBHOOK_SECRET` を足し（値は書かない）、`backend/app/config.py` の `Settings` に同じ 2 つと、定数 `PLAN_NAME`（「月額プラン」）・`PLAN_AMOUNT_JPY`（`10000`）・`PLAN_LOOKUP_KEY`（`monthly_standard`）を足す（FR-022、R-01）（ミ）
- [X] T003 [P] `docker-compose.yml` に Stripe CLI のサービス `stripe`（イメージ `stripe/stripe-cli`、`profiles: [stripe]`、`command: listen --events checkout.session.completed,checkout.session.expired,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,invoice.payment_failed,invoice.paid --forward-to backend:8000/api/billing/webhook`（転送する知らせは R-03 の「扱う知らせ」だけ。Stripe CLI の新しい版は `--events` が必須。#69）、`.env` の `STRIPE_SECRET_KEY` を `STRIPE_API_KEY` として渡す）を足す（R-11）（ミ）
- [X] T004 Stripe のテスト環境で、商品「月額プラン」と価格「月額 10,000 円（JPY・毎月）」を作り、価格の lookup key を `monthly_standard` にする。`docker compose --profile stripe up -d stripe` で Webhook が手元に届くことを確かめる（quickstart.md の「用意するもの」）（ミ・手作業）

**Checkpoint**: Stripe CLI が backend に知らせを転送できる（受け口は Phase 3 で作るので、この時点では 404 でよい）

---

## Phase 2: Foundational（決済のすべての User Story の前に必要なもの）

**Purpose**: テーブル・ログイン用の ID・パスワードの決まり・Stripe を呼ぶ 1 か所

**⚠️ CRITICAL**: spec 001 の 001-T009（共通のテーブル）・001-T010（ログイン中の人）・001-T014（書き込みの確認）が main に入ってから始める

- [X] T005 001-T009 のマイグレーションに足す（または続きのマイグレーションを作る）：`facilities.billing_email`（text、「一意にしない」、初期データの施設は空）・`facilities.stripe_customer_id`（text、「一意」、初期データの施設は空）と、シーケンス `staff_login_id_seq`（data-model.md）（ミ）
- [X] T006 [P] ログイン用の ID を作る関数を `backend/app/auth/login_ids.py` に作る：`staff_login_id_seq` の次の値から `s` ＋ 5 桁の数字（`s00001`）を返す。職員のアカウント（001-T088）と初期データ（001-T015）もこれを使う（R-06）（ミ）
- [X] T007 [P] パスワードの決まり（spec 001 の research.md R-03）を `backend/app/auth/passwords.py` に作る：「8 文字以上、64 文字まで」「文字の種類の組み合わせは求めない」「よく使われるパスワードの一覧（`backend/app/auth/common_passwords.txt.gz`）に当てはまれば使わせない」「半角の英数字と記号（空白も含む）でなければ 422（#65 で、全角は使えないことにした）」、bcrypt でハッシュにする関数。ログイン（001-T022）・職員のアカウント（001-T088）・家族の招待（001-T089）も使う（001 の R-03・R-06）（ミ）
- [X] T008 [P] テスト `backend/tests/unit/test_passwords.py`：7 文字は弾く、8 文字は通る、記号なしでも通る、一覧にあるものは弾く、かな・全角の文字が入っていると弾く（001 の R-03）（ミ）
- [X] T009 決済のテーブルを `backend/app/models/billing.py` に作り、マイグレーションを足す（data-model.md）：
  `facility_subscriptions`（`facility_id` は「一意（施設に 1 つ）」、`status` は「`active`／`payment_failed`／`cancel_scheduled`／`canceled`」、`stripe_subscription_id`・`current_period_end` は「初期データの施設は空」、`cancel_at`・`open_checkout_session_id`・`open_checkout_expires_at`・`updated_at`）、
  `subscription_status_histories`（`facility_id`・`from_status`（初めて作ったときは空）・`to_status`・`stripe_event_id`（初期データは空）・`changed_at`）、
  `billing_applications`（`idempotency_key` は「一意」、`facility_name`・`director_name`・`contact_email`・`password_hash`（「アカウントを作ったら消す」ので null を許す）、`status` は「`pending`／`completed`／`rejected`」、`stripe_checkout_session_id` は「一意」、`checkout_url`・`expires_at`・`created_facility_id`・`created_user_id`・`created_at`）、
  `billing_events`（`stripe_event_id` は「一意」、`type`・`received_at`。本文は保存しない）（ミ）
- [X] T010 Stripe を呼ぶところを `backend/app/services/stripe_client.py` の 1 か所にまとめる：lookup key で価格を探す、Checkout Session を作る（冪等キーを渡す、`expires_at` は 30 分後、顧客には施設名とメールアドレスだけを渡す）、Checkout Session を失効させる、Subscription を読む・解約する、顧客の名前を施設名にする、Webhook の署名を確かめる。Stripe を呼ぶときの待ち時間の上限は 10 秒（ライブラリの初期値は長いため）。テストではこのモジュールをモックにする（R-01・R-03・R-04・R-07・R-12、FR-025）（ミ）
- [X] T011 [P] Stripe の状態からアプリの状態を決める対応表を `backend/app/services/billing.py` の `to_app_status(subscription)` に作り、テスト `backend/tests/unit/test_billing_status.py` を書く：`active`→`active`、`active`＋`cancel_at_period_end`→`cancel_scheduled`、`past_due`・`unpaid`→`payment_failed`、`canceled`・`incomplete_expired`→`canceled`、`incomplete`・`trialing`・`paused`・表にないものは「変えない」（WARNING で状態のコードだけをログに出す）（R-05）（ミ）
- [X] T012 001-T014 の書き込みの確認（`backend/app/auth/csrf.py`）で、`/api/billing/webhook` だけを対象から外す（Stripe はヘッダーを付けないため。代わりに署名で確かめる。R-03）（ミ）
- [X] T013 001-T015 の初期データ（`backend/app/seed/__main__.py`）で、施設を作るときに `facility_subscriptions` を `status=active`（Stripe とつながっていない）で作る。職員の `login_id` は T006 の関数で作る（data-model.md の「初期データ」）（ミ）

**Checkpoint**: テーブルとパスワードの決まりができ、Stripe を呼ぶところがモックにできる

---

## Phase 3: User Story 1 - 施設長が申し込みページから申し込み、支払う（Priority: P1）🎯 MVP

**Goal**: ログインなしの申し込みページで入力して払うと、Webhook を確かめたうえで施設・施設長のアカウント・契約ができ、「契約中」になる

**Independent Test**: 空の DB で /signup を開き、テスト用のカードで払うと、完了の画面に ID が出て、その ID とパスワードでログインでき、「利用料のお支払い」に「契約中」と出る（quickstart.md の通しの確認 1〜6）

### Tests for User Story 1

- [ ] T014 [P] [US1] テスト `backend/tests/api/test_billing_signup.py`：メールアドレスが違うと 422 `email_mismatch`、パスワードが決まりの外なら 422、同じ `idempotency_key` で 2 回送ると申し込みは 1 行で同じ `checkout_url`（SC-009）、同じ `idempotency_key` がほぼ同時に 2 つ届いても 500 にならず同じ `checkout_url`、`POST /api/billing/signup/cancel` で支払い画面が失効し申し込みが消える（`completed` の申し込みには何もせず 204）、期限が切れたあとに同じ `idempotency_key` で送ると、新しい申し込みと別の Stripe の冪等キーで作り直す、施設がすでにあると `GET`・`POST` とも 404、`X-Requested-With` がないと弾かれる（FR-027）、DB にパスワードが元の文字のまま残らない（SC-007）、Stripe に渡すのが施設名とメールアドレスだけ（FR-025・SC-010）（ミ）
- [ ] T015 [P] [US1] テスト `backend/tests/api/test_billing_webhook.py`：署名が違うと 400 で何も変わらない（SC-004）、同じ `checkout.session.completed` を 3 回送っても施設・アカウント・契約・履歴が 1 つずつ（SC-003）、ID が別の知らせで同じ申し込みが来ても 1 回だけ、2 つの申し込みの支払いが続けて確かめられても施設は 1 つで、もう一方は `rejected` になり、その Stripe の契約を解約する呼び出しがある（FR-016）、`completed`・`rejected` の申し込みの `password_hash`・`facility_name`・`director_name`・`contact_email` が空になる、`checkout.session.expired` で申し込みの行が消える（FR-006）（ミ）
- [ ] T016 [P] [US1] テスト `backend/tests/api/test_billing_admin.py`：`GET /api/admin/billing` は施設長・事務員だけで、介護職員・リーダー・生活相談員・家族は 403（FR-007・SC-006）、初期データの施設では `can_manage` が false（ミ）

### Implementation for User Story 1

- [ ] T017 [US1] `GET /api/billing/signup`・`POST /api/billing/signup` を `backend/app/api/billing.py` に作る（ログインなし）：施設がすでにあれば 404 `not_found`（理由は出さない）、入力を確かめ（2 回のメールアドレスが同じ、T007 のパスワードの決まり）、同じ `idempotency_key` があればその `checkout_url` を返す（期限が過ぎていれば行を消して作り直す）、なければ申し込みを作って T010 で Checkout Session を作り（Stripe の冪等キーは `signup-<申し込みの id>`）、`client_reference_id` に申し込みの id を入れる。行の追加から `checkout_url` を書くまでを 1 つのトランザクションにし、同じ `idempotency_key` がほぼ同時に届いたら、2 つ目は `INSERT ... ON CONFLICT DO NOTHING` で 1 つ目の確定を待ってから行を読み直して同じ URL を返す（Stripe に頼み直さない）。Checkout の `cancel_url` は `/signup?canceled=1&key=<idempotency_key>`。Stripe を呼べなければ申し込みを消して 502 `payment_service_unavailable`。あわせて `POST /api/billing/signup/cancel`（`pending` の申し込みだけ、支払い画面を失効させて行を消す。それ以外は何もせず 204）を作る（contracts/api.md、R-02・R-07・R-12）（ミ）
- [ ] T018 [US1] `POST /api/billing/webhook` を `backend/app/api/billing.py` に作る：本文をそのまま T010 の署名の確認にかけ、だめなら 400 とログ（WARNING、「確かめられなかった」だけ）。`billing_events` に `stripe_event_id` を足す処理と知らせの処理を 1 つのトランザクションで行い、すでにある id なら何もせず 200。失敗は 500（R-03・R-13）（ミ）
- [ ] T019 [US1] `checkout.session.completed` の処理を `backend/app/services/billing.py` に作る：`pg_advisory_xact_lock` で 1 つずつにし、申し込みを `FOR UPDATE` で押さえ、`completed`・`rejected` なら何もしない。施設がすでにあれば、T010 でその Stripe の契約を解約し、`rejected` にしてログ。なければ T010 で顧客の名前を施設名にし、 `facilities`（`billing_email`・`stripe_customer_id`）・`users`（`kind=staff`、T006 の `login_id`、申し込みの `password_hash`）・`staff`（`role=director`、`display_name`＝施設長の名前）・`facility_subscriptions`（`active`、`stripe_subscription_id`・`current_period_end`）・`subscription_status_histories` を作り、申し込みを `completed` にする。`completed`・`rejected` のどちらでも、申し込みの `password_hash`・`facility_name`・`director_name`・`contact_email` を消す。Stripe を呼ぶ操作は DB を確定する前に行い、失敗したら 500。再送に備え、解約は Subscription を読み直してすでに `canceled` なら呼ばない（「すでに解約済み」のエラーも成功として扱う）（R-04）（ミ）
- [ ] T020 [US1] `checkout.session.expired` の処理を `backend/app/services/billing.py` に足す：`pending` の申し込みの行を消す（FR-006、R-07）（ミ）
- [ ] T021 [US1] `GET /api/billing/signup/complete?session_id=` を `backend/app/api/billing.py` に足す：`confirming`／`completed`（`login_id` を付ける。アカウントを作ってから 1 時間まで）／`not_completed`（contracts/api.md）（ミ）
- [ ] T022 [US1] `GET /api/admin/billing` を `backend/app/api/admin/billing.py` に作る（役割：施設長・事務員）：ミニマム版は `status`・`plan_name`・`amount_jpy`・`can_subscribe`・`can_manage`（contracts/api.md）（ミ）
- [ ] T023 [US1] ルーターを `backend/app/main.py` に登録する（T017〜T022）（ミ）
- [ ] T024 [P] [US1] 申し込みページを `frontend/src/pages/signup/Signup.tsx` に作る：`idempotency_key` を `crypto.randomUUID()` で作って `localStorage` に残す（使えないときは画面の中だけ。読み書きは try/catch で囲む）、施設名・施設長の名前・メールアドレス（2 回）・パスワード（8 文字以上）の入力、「申し込む」は押したらすぐ押せなくし、返ってきた `checkout_url` へ移る。支払い画面から戻ったとき（`?canceled=1&key=`）は `POST /api/billing/signup/cancel` を呼び、`idempotency_key` を作り直して「お申し込みは完了していません」。文言は辞書から引く（US1 のシナリオ 1・3・5、R-12）（ミ）
- [ ] T025 [P] [US1] 申し込み完了の画面を `frontend/src/pages/signup/SignupComplete.tsx` に作る：`session_id` で T021 を 3 秒ごとに読み、`confirming` の間は「お支払いを確認しています」、`completed` で ID と「控えてください」（メールの一文はまだ出さない）とログイン画面へのボタンを出し、`localStorage` の `idempotency_key` を消す（US1 のシナリオ 2・4、R-12）（ミ）
- [ ] T026 [P] [US1] 利用料のお支払いの画面を `frontend/src/pages/admin/Billing.tsx` に作る：ミニマム版は契約の状態（契約中など）とプラン名・月額だけ（US1 の Independent Test）（ミ）
- [ ] T027 [US1] 001-T019 の画面の枠に、`/signup`・`/signup/complete` をログインなしの枠に、`/admin/billing` を管理画面の枠（施設長・事務員だけ。介護職員などには「この画面を使う権限がありません」）に足す（FR-007）（ミ）
- [ ] T028 [US1] quickstart.md の「通しの確認」1〜7 と「ぶつかる場面・守りの確認」を手で通す（Stripe のテスト環境と Stripe CLI を使う）（ミ・Day 3）
- [ ] T029 [US1] ID を書いたメール：`email_outbox` にテンプレート `owner_account`（params は `login_id` とログイン画面のリンクだけ。パスワードは入れない、末尾に「心当たりがない場合は、このメールを破棄してください」）を足し、T019 のトランザクションの中で送る予定を作る。完了の画面に「同じ内容をメールでもお送りしました」を足す（FR-005、R-08。さとこの 001-T048・001-T057 のあと）（作）
- [ ] T030 [US1] 申し込みを同時に 1 つだけにする：T017 で、期限内の `pending` があれば 409 `signup_in_progress`。テストを T014 に足す（FR-014、R-07）（作）
- [ ] T031 [US1] 申し込みの回数の制限：Redis の `ratelimit:signup:<接続元>`（期限つき）で、短い時間に何度も申し込まれたら 429 `too_many_attempts`。テストを T014 に足す（FR-027）（作）
- [ ] T032 [US1] 申し込み直し `POST /api/admin/billing/checkout` を `backend/app/api/admin/billing.py` に足す：解約済みのときだけ、施設の `stripe_customer_id` で Checkout Session を作り、`open_checkout_session_id` が期限内ならその URL を返す（施設長と事務員が同時に押しても同じ画面）。それ以外は 409 `already_subscribed`。`checkout.session.completed` の処理（T019）で、申し込み直しのときは契約を結び直す。画面の「申し込む」ボタンを T026 に足す（US1 のシナリオ 6・8、FR-013、R-10）（作）

**Checkpoint**: 申し込みページから払うと「契約中」になる。Day 4 の通しのデモの J の部分ができる

---

## Phase 4: User Story 2 - 施設長・事務員が契約の状態と請求の予定を確かめる（Priority: P2）

**Goal**: 支払いに失敗・解約予定・解約済みが Stripe の知らせで反映され、管理画面で状態と次の請求日が見られる

**Independent Test**: 契約中の施設と、支払いに失敗した施設で「利用料のお支払い」を開き、状態と次の請求日が正しく出る（quickstart.md の「作り込みの確認」）

- [ ] T033 [P] [US2] テスト `backend/tests/api/test_billing_webhook.py` に足す：`customer.subscription.updated` などを受けたら Stripe から読み直した状態に合わせる、「解約」のあとに古い「支払い完了」を送っても状態が戻らない（SC-008）、状態が変わったときだけ履歴が 1 件増える（FR-019）（作）
- [ ] T034 [US2] `customer.subscription.created`・`updated`・`deleted`、`invoice.payment_failed`・`invoice.paid` の処理を `backend/app/services/billing.py` に足す：知らせの中身を信じず、T010 で Subscription を読み直して T011 の対応表で状態を決め、`current_period_end`・`cancel_at` を上書きし、変わったら履歴を足す（FR-009・FR-012・FR-019、R-03・R-05）（作）
- [ ] T035 [US2] `GET /api/admin/billing` に `current_period_end`・`cancel_at` を足し、`frontend/src/pages/admin/Billing.tsx` に次の請求日、支払いに失敗のときの「お支払いに失敗しました」とカードを確かめる案内、解約予定のときのいつまで使えるかを出す（FR-018、US2 のシナリオ 1・2）（作）
- [ ] T036 [US2] 家族・職員の画面に利用料の案内が出ないこと、契約の状態に関係なく使えることを確かめる（FR-017、US2 のシナリオ 3）。Stripe の管理画面で、支払い失敗のメール（決済サービスの標準の機能）をオンにする（FR-021）（作）

**Checkpoint**: 支払いに失敗・解約が管理画面に反映される

---

## Phase 5: User Story 3 - 施設長・事務員がカードの変更・解約・請求の履歴を扱う（Priority: P3）

**Goal**: 管理画面から Stripe の Customer Portal に移り、カードの変更・解約・請求と領収書の確認ができる

**Independent Test**: 契約中の施設で Portal に移り、テスト用の別のカードに変える・解約する・請求の履歴を見るができ、解約がアプリの状態に反映される（US3）

- [ ] T037 [US3] Stripe のテスト環境の Customer Portal の設定で、「カードの変更・解約（期間の終わりに）・請求の履歴」だけを有効にする（R-10）（作・手作業）
- [ ] T038 [US3] `POST /api/admin/billing/portal` を `backend/app/api/admin/billing.py` に足す（役割：施設長・事務員。`can_manage` が false なら 409）。テストを `backend/tests/api/test_billing_admin.py` に足す（FR-020、contracts/api.md）（作）
- [ ] T039 [US3] `frontend/src/pages/admin/Billing.tsx` に「カードの変更・解約・請求の履歴」ボタンを足し、返ってきた URL へ移る（US3 のシナリオ 1）（作）

**Checkpoint**: カードの変更・解約・領収書が Stripe の画面でできる

---

## Phase 6: Polish & Cross-Cutting Concerns（作り込み・仕上げ）

- [ ] T040 [P] Stripe の鍵を、必要な操作（Checkout・Subscription の読み取り・Customer Portal）だけができる制限付きの鍵に替え、漏れたときの差し替えの手順を quickstart.md に書く（FR-026）（作）
- [ ] T041 [P] 申し込みページ・完了・利用料のお支払いの文言にふりがなを付け、インドネシア語・英語の辞書に足す（みさきの 001-T082・001-T083 の仕組みを使う。Constitution の UI 方針）（作）
- [ ] T042 本番の Webhook の受け口を Stripe の管理画面に登録し、本番用の `STRIPE_WEBHOOK_SECRET` と `STRIPE_SECRET_KEY`（テスト環境の鍵）を Render に置く（001-T092 と一緒に）（作）
- [ ] T043 quickstart.md の確認をすべて通し、`docs/テスト設計書.md` に決済のテストシナリオと結果を書く（Constitution の課題要件のテスト。001-T093 と一緒に）（作）

---

## Dependencies & Execution Order

### Phase の順番

- **Setup（Phase 1）**：いつでも始められる（T004 の手作業は、鍵が手元にあれば先にやっておける）
- **Foundational（Phase 2）**：spec 001 の 001-T009・001-T010・001-T014 が main に入ってから。T005〜T013 が終わると、US1 を始められる
- **US1（Phase 3）**：Foundational のあと。ミニマム版は T014〜T028
- **US2・US3（Phase 4・5）**：US1 のあと（契約ができていないと確かめられない）。US2 と US3 は並べて進められる
- **Polish（Phase 6）**：ミニマム版の通しのデモ（Day 4）のあと

### spec 001 とのつながり（すべてようこ自身）

| spec 002 のタスク | 先に要る spec 001 のタスク |
|---|---|
| T005（列とシーケンス） | 001-T009（共通のテーブル） |
| T012（Webhook を確認から外す） | 001-T014（書き込みの確認） |
| T013（初期データの契約） | 001-T015（初期データ） |
| T016・T022（施設長・事務員だけ） | 001-T010（ログイン中の人と役割のチェック） |
| T025 のログイン画面への移動、T028 のログインの確認 | 001-T022（本物のログイン） |
| T027（画面の枠） | 001-T019（画面の枠） |
| T029（ID を書いたメール） | 001-T048・001-T057（さとこ：`email_outbox` と worker） |

逆に、T006（ログイン用の ID）と T007（パスワードの決まり）は、spec 001 の 001-T015・001-T022・001-T088・001-T089 が使う。T007 は 001-T022（Day 2）より先に作る。

### User Story の中の順番

- テスト → テーブル（Foundational）→ サービス → API → 画面
- Webhook の処理（T018〜T020）は、T015 のテストを先に書き、テストを通しながら作る

---

## Parallel Example

### Day 1〜2（spec 001 の基盤と並べて）

```text
Day 1：001-T009 と一緒に T005、001-T014 と一緒に T012、001-T015 と一緒に T013
Day 1 の空き時間：T001・T002・T003、T004（Stripe の管理画面での準備）
Day 2 の午前：T006・T007・T008（001-T022 の前に）→ 001-T022
Day 2 の午後：T009 → T010・T011（並べて）→ T014・T015・T016（テスト、並べて）
```

### User Story 1（Day 2 の夕方〜Day 3）

```text
バックエンド：T017 → T018 → T019・T020 → T021・T022 → T023
画面は並べて：T024・T025・T026（API の形が決まっていれば、T017 と同時に始められる）
最後に：T027 → T028（通しの確認）
```

---

## Implementation Strategy

### ミニマム版（Day 1〜4）

1. Setup と Foundational（T001〜T013）。spec 001 の基盤のタスクと一緒に進める
2. US1 の「ミ」のタスク（T014〜T028）
3. **Day 4 の通しのデモ**：空の DB で申し込む → 払う → ID でログイン → 「契約中」→ 初期データを入れて spec 001 のデモへ（quickstart.md）

いちばん詰まりやすいのは、Webhook を手元で受けるところ（Stripe CLI と署名の秘密）。Day 1 の空き時間に T003・T004 を済ませ、知らせが届くことだけでも先に確かめておく。

### 作り込み（Day 5）

- US1 の「作」（T029〜T032）→ US2（T033〜T036）→ US3（T037〜T039）の順。ID を書いたメール（T029）は、さとこの `email_outbox` ができてから
- 遅れそうなときは、US3 を後回しにする（決済の MUST は US1 で満たせる）

### 仕上げ（Day 5〜6）

- 制限付きの鍵、ふりがなと多言語、本番の Webhook、テストシナリオ（T040〜T043）

---

## Notes

- [P] のタスクは別のファイルで、終わっていないタスクに依存しない
- カード情報はアプリのどこでも受け取らない。Stripe の画面だけで入力する（FR-008）
- 自動テストでは Stripe を呼ばない（`services/stripe_client.py` をモックにする）。鍵を CI に置かない
- ログには申し込み・施設・知らせの id と種類だけを出し、施設名・名前・メールアドレス・パスワード・鍵は出さない（R-13）
- 1 PR は 1,100 行以内（`specs/` とロックファイルは数えない）。超えそうなら issue とブランチを分ける
