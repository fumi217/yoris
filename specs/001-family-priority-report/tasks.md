---

description: "spec 001（連絡帳・知りたいこと・通知・施設からのお知らせ（献立表も、お知らせの添付で出す））のタスク一覧"
---

# Tasks: 家族の「知りたいこと」に職員が答える連絡帳（スプリント1: C→B→A）

**Input**: `specs/001-family-priority-report/` の [spec.md](./spec.md)・[plan.md](./plan.md)・[research.md](./research.md)・[data-model.md](./data-model.md)・[contracts/api.md](./contracts/api.md)・[quickstart.md](./quickstart.md)

**Tests**: テストのタスクを含める（Constitution の課題要件「単体テストはテストコードを書く」、plan の research.md R-19）。LLM・Stripe・メールはモックにする。

**Organization**: User Story ごとにまとめる。各タスクの末尾に **（担当・時期）** を書く。時期の「ミ」は Day 1〜4 のミニマム版、「作」は Day 5 の作り込み（Day は docs/マイルストーン.md の表が正。#53）（[plan.md の「ミニマム版と作り込み」](./plan.md#ミニマム版と作り込み)）。
issue は担当者が、ここから自分のタスクを選んで立てる（1 issue は 1 PR で 1,100 行以内に収まる量。`.claude/skills/github-workflow/SKILL.md`）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: ほかのタスクと並べて進められる（別のファイルで、終わっていないタスクに依存しない）
- **[Story]**: どの User Story のタスクか（US1〜US5）。Setup・Foundational・Polish には付けない
- パスは plan.md の構成（`backend/app/`・`frontend/src/`）に合わせる

---

## Phase 1: Setup（全員が使う土台）

**Purpose**: リポジトリの骨組みを作り、全員が `docker compose up` で動かせるようにする

- [X] T001 `docker-compose.yml` に frontend・backend・worker・db（PostgreSQL）・redis・mailpit を定義する。worker は backend と同じイメージを `python -m app.jobs.worker` で起動する。redis は `maxmemory-policy volatile-lru` にする（research.md R-12）（ようこ・ミ）
- [X] T002 バックエンドのひな形を作る：`backend/app/main.py`（FastAPI）、`backend/app/config.py`（環境変数。`APP_ENV` が未設定なら production 扱い）、依存は `backend/requirements.txt`・`backend/requirements-dev.txt`（CI がこの名前を見る）（ようこ・ミ）
- [X] T003 フロントエンドのひな形を作る：Vite ＋ React ＋ TypeScript、React Router、TanStack Query、Tailwind CSS。`frontend/vite.config.ts` で `/api` をバックエンドへ中継する（同じオリジン。research.md R-03）。`frontend/package-lock.json` をコミットする（ようこ・ミ）
- [X] T004 Alembic を `backend/alembic/` に用意し、`docker compose exec backend alembic upgrade head` で動くようにする（research.md R-17）（ようこ・ミ）
- [X] T005 [P] lint・format を設定する：`backend/pyproject.toml`（ruff）、`frontend/eslint.config.js`（ようこ・ミ）
- [ ] T006 [P] ログの出し方を `backend/app/logging.py` に作る：structlog、開発は読みやすい形式、本番は JSON で INFO 以上。氏名・メールアドレス・記録の値・返事の文・お知らせの本文・招待のトークンは出さず id だけ出す（FR-027・research.md R-18）（ようこ・ミ）
- [X] T007 [P] `env.example` に環境変数のキー名を足す：`APP_ENV`・`DATABASE_URL`・`REDIS_URL`・`MAIL_TRANSPORT`（`smtp`／`resend`）・`SMTP_HOST`・`SMTP_PORT`・`RESEND_API_KEY`・`MAIL_FROM`・`APP_BASE_URL`・`UPLOAD_DIR`・`OPENROUTER_API_KEY`・`OPENROUTER_MODEL`・`JOBS_TOKEN`（値は書かない。research.md R-09）（ようこ・ミ）

---

## Phase 2: Foundational（全 User Story の前に必要なもの）

**Purpose**: 共通のテーブル・ログイン中の人・エラーの形・辞書・初期データの仕組み

**⚠️ CRITICAL**: ここが終わるまで、各 User Story の API は作り始められない（画面のひな形は並べて進めてよい）

- [X] T008 DB のセッションを `backend/app/db.py` に作る（SQLAlchemy 2）（ようこ・ミ）
- [X] T009 共通のテーブルを `backend/app/models/core.py` に作り、マイグレーションを足す：`facilities`、`users`（`kind`：`staff`／`family`、職員は `login_id`、家族は `email`、`password_hash`、`language`：`ja`／`id`／`en` 初期値 `ja`）、`residents`、`staff`（`role`：`care_worker`／`leader`／`counselor`／`clerk`／`director`、`display_name`）、`family_accounts`（`resident_id` は一意＝入居者に 1 つ）（data-model.md）（ようこ・ミ）
- [ ] T010 ログイン中の人（`CurrentUser`：user_id・kind・role・resident_id・language）と、役割のチェック（`require_family`・`require_staff(roles)`）を `backend/app/auth/deps.py` に作る（ようこ・ミ）
- [ ] T011 [P] Redis の接続を `backend/app/redis.py` に作る。キーには用途の接頭辞を付け、必ず期限を付ける決まりをコメントに書く（research.md R-12）（ようこ・ミ）
- [ ] T012 [P] エラーの形（`{"error": {"code", "message_key"}}`）とコード（`not_logged_in`・`forbidden`・`not_found`・`request_limit`・`theme_waiting`・`already_replied`・`request_cancelled`・`not_today`・`invalid_file`・`validation_error`）を `backend/app/errors.py` に作る（contracts/api.md）（ようこ・ミ）
- [ ] T013 開発用のユーザー切り替え `POST /api/dev/switch-user` を `backend/app/api/dev.py` に作る。`APP_ENV=development` のときだけルーターを登録する（research.md R-02）（ようこ・ミ）
- [ ] T014 書き込みの API で `X-Requested-With: fetch` ヘッダーを確かめるミドルウェアを `backend/app/auth/csrf.py` に作る。ブラウザから呼ばない `POST /api/internal/jobs/run`（合言葉で確かめる。contracts/api.md）は対象から外す（research.md R-03）（ようこ・ミ）
- [ ] T015 初期データの仕組みを `backend/app/seed/__main__.py` に作り、入居者 30 人・職員（`login_id` つき、各役割）・家族アカウント 30（入居者に 1 つ）を入れる（`python -m app.seed`）。**施設がまだなければ作り（契約中として）、すでにあればその施設に足す**（J の申し込みで施設ができたあとにも流せるように。PR #23 ようこ・spec 002）。ほかの人はここに自分の分を足す（ようこ・ミ）
- [ ] T016 [P] 多言語の辞書の仕組みを `frontend/src/i18n/index.ts`・`frontend/src/i18n/ja.json` に作る。ミニマム版は日本語だけ。文言は必ず辞書から引く。日本語のふりがなは `{漢字|かんじ}` の書き方で書く（research.md R-11）（みさき・ミ）
- [ ] T017 [P] ふりがなの部品 `frontend/src/i18n/Ruby.tsx` を作る：`{漢字|かんじ}` を `<ruby>` に変える。日本語以外では書き方を使わない。メール用に漢字だけにする関数も `backend/app/i18n.py` に作る（みさき・ミ）
- [ ] T018 [P] API を呼ぶ関数を `frontend/src/api/client.ts` に作る（`X-Requested-With: fetch` を付ける、エラーの `message_key` を辞書で引く）。OpenAPI から型を作るスクリプト（`npm run gen:api`、openapi-typescript）を `frontend/package.json` に足す（research.md R-16）（ようこ・ミ）
- [ ] T019 画面の枠を作る：`frontend/src/pages/family/`・`frontend/src/pages/staff/`・`frontend/src/pages/admin/` のレイアウトと、役割で画面を分けるルーティングを `frontend/src/App.tsx` に、開発用のユーザー切り替えを `frontend/src/components/DevUserSwitcher.tsx` に作る。
  家族の画面のメニューは、下に「連絡帳・知りたいこと・お知らせ」の 3 つ、そのほか（面会・アルバム・設定）は「☰ その他」にまとめる（Clarifications）。「☰ その他」は、ほかの機能が項目を足しやすい形にする（spec 003 の T014 が「面会」を足す）。
  家族には職員・管理画面へのリンクを出さず、URL を直接開いても家族の画面に戻す（API は 403 `forbidden`。spec 003 の plan.md）（ようこ・ミ）
- [ ] T020 テストの土台を `backend/tests/conftest.py` に作る：テスト用の PostgreSQL・Redis（コンテナ）、ログイン済みのクライアントを作るヘルパー。あわせて CI（`.github/workflows/ci.yml`）に PostgreSQL・Redis のサービスを足す（同じ PR で入れる。入れないと全員の CI が赤になるため）（research.md R-19）（ようこ・ミ）
- [ ] T021 [P] テスト `backend/tests/api/test_dev_switch.py`：`APP_ENV` を付けない設定で `POST /api/dev/switch-user` が 404 になる（research.md R-02）（ようこ・ミ）
- [ ] T022 本物のログインを `backend/app/auth/routes.py` に作る：`POST /api/auth/login`（職員は ID、家族はメールアドレス、bcrypt）、`POST /api/auth/logout`（セッションをすぐ消す）、`GET /api/me`。セッションは Redis（`session:<ランダムなID>`）、Cookie は `HttpOnly`・`Secure`（本番）・`SameSite=Lax`（research.md R-01・R-03）（ようこ・ミ・Day 2）
- [ ] T023 [P] テスト `backend/tests/api/test_auth.py`：職員は ID、家族はメールアドレスでログインできる。家族が職員の API を呼ぶと 403。ログアウトでセッションが消える（ようこ・ミ）
- [ ] T096 [P] 画面設計 `docs/画面設計.md` を作る：画面の一覧と遷移、職員の入居者一覧に出すもの（未記録・返事待ち・家族からのメッセージ・承認待ち・目印）の並べ方と置き場所、記録の画面に並ぶ部品（E の目印・D の「様子のメモを書く」・H の「写真を載せる」）の並べ方も決める（spec 006 の Assumptions、PR #40・#45）（ゆう・ミ）

**Checkpoint**: 土台ができた。User Story ごとの作業を並べて始められる

---

## Phase 3: User Story 1 - 職員がお世話の場で連絡帳をボタンで記録する（Priority: P1）🎯 MVP

**Goal**: 介護職員がタブレットで、食事量（5 段階＋食事なし）・機嫌・様子・眠り（3 段階）を文字の入力なしで記録し、その日の連絡帳を見返せる

**Independent Test**: 職員が 30 人分の昼食の食事量を記録し、記録一覧に入居者ごと・食事ごとの食事量と記録者・時刻が残る（spec の US1）

### Tests for User Story 1

- [ ] T024 [P] [US1] テスト `backend/tests/api/test_records.py`：記録の保存、押し直したら上書きされて `care_record_histories` に前の値が残る、同じ「入居者×日付×項目×区分」は 1 つだけ、家族アカウントでは 403（FR-001・FR-002・FR-005・FR-024）（ゆう・ミ）

### Implementation for User Story 1

- [ ] T025 [US1] `care_records` と `care_record_histories` を `backend/app/models/records.py` に作り、マイグレーションを足す。`item`：`meal`／`mood`／`sleep`、`slot`：食事は `breakfast`／`lunch`／`dinner`／`snack`、機嫌・眠りは `day`、`value`：meal は `10`／`8`／`5`／`2`／`0`／`none`、mood は `smile`／`normal`／`low`、sleep は `good`／`normal`／`poor`。一意は `(resident_id, date, item, slot) WHERE deleted_at IS NULL`（部分インデックス）。眠りの `date` は記録した朝の日付（data-model.md・research.md R-04・R-05）（ゆう・ミ）
- [ ] T026 [US1] 記録の保存・押し直しを `backend/app/services/records.py` に作る：上書きのときは前の値（`value`）を履歴に残す。日付は日本時間で決める（research.md R-14）（ゆう・ミ）
- [ ] T027 [US1] `PUT /api/staff/residents/{id}/records` を `backend/app/api/staff/records.py` に作る（役割：介護職員・リーダー・相談員・施設長）（contracts/api.md）（ゆう・ミ）
- [ ] T028 [US1] `GET /api/staff/residents?date=` を `backend/app/api/staff/residents.py` に作る：食事区分ごとの記録済み／未記録（FR-008）。返事待ちの件数は US3 で足す（ゆう・ミ）
- [ ] T029 [US1] `GET /api/staff/residents/{id}/contact-book?date=` を `backend/app/api/staff/contact_book.py` に作る：その日の記録を時刻順に（非開示も含む。職員向けなので共通の関数は通さない）（FR-024）（ゆう・ミ）
- [ ] T030 [P] [US1] 記録のサンプル（数日分）を `backend/app/seed/records.py` に作る（ゆう・ミ）
- [ ] T031 [P] [US1] 入居者一覧の画面を `frontend/src/pages/staff/ResidentList.tsx` に作る（未記録が分かる）（ゆう・ミ）
- [ ] T032 [US1] 記録の画面を `frontend/src/pages/staff/RecordPage.tsx` に作る：食事区分を選んで 5 段階＋「食事なし（外泊・入院など）」のボタン、機嫌・眠りの 3 段階のボタン。入居者を選んでから保存まで 3 タップ以内（FR-006・SC-003）。文言は辞書から引く（ゆう・ミ）
- [ ] T033 [P] [US1] その日の連絡帳の見返しの画面を `frontend/src/pages/staff/StaffContactBook.tsx` に作る（ゆう・ミ）
- [ ] T034 [US1] 当日中の記録の取り消し `DELETE /api/staff/records/{record_id}` を `backend/app/api/staff/records.py` に足す（`deleted_at`・`deleted_by` を入れる。今日でなければ 409 `not_today`）と、画面の取り消しボタン（Edge Cases）（ゆう・作）

**Checkpoint**: 職員が記録でき、その日の連絡帳を見返せる（初期データの家族は、US2・US3 がなくてもログインだけはできる）

---

## Phase 4: User Story 2 - 施設が家族に見せる記録項目を選ぶ（Priority: P2）

**Goal**: 相談員・施設長が、記録項目とテーマごとに見せる／見せないを施設全体で切り替えられ、見せない項目は家族のどこにも出ない

**Independent Test**: 「機嫌・様子」をオン、「眠り」をオフにして家族でログインし、食事量と機嫌・様子は見えて、眠りはどの画面にも出ない（spec の US2）

### Tests for User Story 2

- [ ] T035 [P] [US2] テスト `backend/tests/unit/test_disclosure.py`：非開示の項目は `get_disclosed_records` から返らない、非開示のテーマは `get_disclosed_themes` から返らない、非開示の項目は `is_item_disclosed` が偽を返す、開示設定を保存したら Redis のキャッシュが消えてすぐ反映される（FR-010・FR-012・SC-006）（ゆう・ミ）

### Implementation for User Story 2

- [ ] T036 [US2] `themes`・`reply_templates`・`disclosure_settings`・`disclosure_setting_histories` を `backend/app/models/disclosure.py` に作り、マイグレーションを足す。`disclosure_settings` の一意は `(facility_id, target_type, target_code)`、`target_type`：`item`／`theme`、`visible` の初期値は `true`（data-model.md）（ゆう・ミ）
- [ ] T037 [US2] テーマ 8 個と定型文（テーマごとに 3〜5 個）の初期データを `backend/app/seed/themes.py` に、日本語の文言を `frontend/src/i18n/ja.json` に足す。キーは変わらないコード（例：`theme.daily_life`、`template.daily_life.smile`）。開示設定はすべて `true` で入れる（FR-013・FR-030）（ゆう・ミ）
- [ ] T038 [US2] 共通の関数を `backend/app/services/disclosure.py` に作る：`get_disclosed_records(resident_id, date_from, date_to, items=None)`（開示済みの、取り消していない記録。id・日付・項目・区分・値・記録した時刻・記録した職員の表示名）、`get_disclosed_themes()`、`is_item_disclosed(code)`（その記録項目を家族に見せる設定か。spec 007 の `get_disclosed_memos` が `is_item_disclosed("memo")` で呼ぶ。spec 005 の `is_feature_disclosed(code)` と同じ形）。開示設定は Redis の `cache:disclosure:<施設ID>`（期限は開発前MTG の決定事項のとおり 5 分）から読む（research.md R-06・R-12）（ゆう・ミ）
- [ ] T039 [US2] `GET /api/admin/disclosure`・`PUT /api/admin/disclosure` を `backend/app/api/admin/disclosure.py` に作る（役割：相談員・施設長）。保存したら開示設定のキャッシュを必ず消す（FR-009・FR-012）（ゆう・ミ）
- [ ] T040 [US2] 開示設定の画面を `frontend/src/pages/admin/DisclosureSettings.tsx` に作る：記録項目とテーマのオン／オフ（ゆう・ミ）
- [ ] T041 [US2] 開示設定の変更履歴：保存のときに `disclosure_setting_histories` に残し、`GET /api/admin/disclosure/history` を足し、画面に履歴を出す（FR-011）（ゆう・作）
- [ ] T042 [US2] 関係しそうな組み合わせ（例：記録項目「機嫌・様子」を見せないのに、テーマ「楽しく過ごせているか」は見せる）の注意書きを、`GET /api/admin/disclosure` の返り値と画面に足す（FR-009）（ゆう・作）

**Checkpoint**: 見せない項目が、共通の関数から 1 件も返らない

---

## Phase 5: User Story 3 - 家族が「知りたいこと」を職員に頼み、連絡帳で返事を見る（Priority: P3）

**Goal**: 家族がテーマのボタンで頼み、職員が定型文のボタンで返事をすると、家族の連絡帳のいちばん上に返事が出て、メールとアプリ内のお知らせで届く（スプリント 1 のゴール）

**Independent Test**: 家族が「👫 他の入居者との関わり」を頼み、職員が定型文で返事をしたあと、家族が連絡帳を開くとファーストビューの一番上にその返事が職員の名前つきで出る（spec の US3）

### Tests for User Story 3

- [ ] T043 [P] [US3] テスト `backend/tests/api/test_requests.py`：返事待ちは 3 件まで（4 件目は 409 `request_limit`）、同じテーマは 1 件まで（409 `theme_waiting`）、返事の前だけ取り消せる、ほかの家族のリクエストの id では取り消せない（404）（FR-014・research.md R-08・R-19）（さとこ・ミ）
- [ ] T044 [P] [US3] テスト `backend/tests/api/test_replies.py`：2 人がほぼ同時に返事をすると先の 1 人だけ保存され、もう一方は 409 `already_replied`。取り消されたリクエストへの返事は 409 `request_cancelled`。返事の文に `<script>` を入れても文字として返る（FR-030・Edge Cases・research.md R-07・SC-009）（ゆう・ミ）
- [ ] T045 [P] [US3] テスト `backend/tests/api/test_notifications.py`：返事を保存すると、同じトランザクションで `notifications`（`reply`）と `email_outbox` ができる。`email_outbox.params` に返事の中身が入らない。ほかの家族の返事の id では既読にできない（404）（SC-010・research.md R-09・R-19）（さとこ・ミ）

### Implementation for User Story 3

- [ ] T046 [P] [US3] `requests` を `backend/app/models/requests.py` に作り、マイグレーションを足す。`status`：`waiting`／`answered`／`cancelled`。一意は `(resident_id, theme_id) WHERE status = 'waiting'`（data-model.md）（さとこ・ミ）
- [ ] T047 [P] [US3] `replies` を `backend/app/models/replies.py` に作り、マイグレーションを足す。`template_ids` は `bigint[]`（1 つ以上）、`note` は「100 文字まで、任意」、`contact_book_date`、`edited_at`、`read_at`。一意は `(request_id)`（返事は取り消さない）（data-model.md）（ゆう・ミ）
- [ ] T048 [P] [US3] `notifications`・`email_outbox` を `backend/app/models/notifications.py` に作り、マイグレーションを足す。`notifications.kind`：`reply`／`daily_digest`／`weekly_digest`／`announcement`。`email_outbox.params` には種類・タイトル・リンクだけを入れる（data-model.md）（さとこ・ミ）
- [ ] T049 [US3] リクエストの作成・取り消しを `backend/app/services/requests.py` に作る：作るときは `family_accounts` の行を `FOR UPDATE` で押さえて返事待ちを数え、テーマが `get_disclosed_themes()` にあるかを確かめる（research.md R-08）（さとこ・ミ）
- [ ] T050 [US3] `GET /api/family/themes`・`GET /api/family/requests`・`POST /api/family/requests`・`DELETE /api/family/requests/{id}` を `backend/app/api/family/requests.py` に作る。入居者は `CurrentUser.resident_id` から決める（FR-013・FR-014・FR-020）（さとこ・ミ）
- [ ] T051 [US3] お知らせとメールの送る予定を作る関数 `create_reply_notice(session, reply_id)` を `backend/app/services/notifications.py` に作る：関数の中では commit しない。作った `email_outbox` の id を返す（呼んだ側が、コミットのあとにその場で送るため。T057）。メールのテンプレート（`backend/app/templates/email/`）には種類とリンクだけを渡す（research.md R-09）（さとこ・ミ）
- [ ] T052 [US3] 返事の保存を `backend/app/services/replies.py` に作る：`UPDATE requests SET status='answered' WHERE id=:id AND status='waiting'` が 0 件なら保存しない（`answered` なら `already_replied`、`cancelled` なら `request_cancelled`）。返事の追加と `create_reply_notice(session, reply_id)` を同じトランザクションで行う（research.md R-07・R-09）（ゆう・ミ）
- [ ] T053 [US3] `GET /api/staff/residents/{id}/requests`・`POST /api/staff/requests/{id}/reply` を `backend/app/api/staff/requests.py` に作り、`GET /api/staff/residents` に返事待ちの件数を足す。返事の保存をコミットしたあとに、BackgroundTasks で T057 の `send_email_now(outbox_id)` を呼ぶ（`outbox_id` は `create_reply_notice` の返り値）。職員への通知・音は出さない（FR-029・FR-030・SC-013、research.md R-09）（ゆう・ミ）
- [ ] T054 [US3] 共通の関数 `get_active_replies(resident_id, date_from, date_to)` を `backend/app/services/disclosure.py` に足す（保存された返事。テーマ・定型文のコード・短い文・職員の表示名・時刻・既読か）（research.md R-06）（ゆう・ミ）
- [ ] T055 [US3] `GET /api/family/contact-book?date=` を `backend/app/api/family/contact_book.py` に作る：まだ読んでいない返事を（日付に関わらず）先頭に、`get_disclosed_records` の記録を食事 → 機嫌・様子 → 眠りの順に、未記録の欄を「まだ記録されていません」のコードで返す。記録を直接読まない（FR-015・FR-017・FR-019）（さとこ・ミ）
- [ ] T056 [US3] `POST /api/family/replies/{reply_id}/read`・`GET /api/family/notifications` を `backend/app/api/family/notifications.py` に作る。ログイン中の家族のものかを確かめる（FR-015・FR-023）（さとこ・ミ）
- [ ] T057 [US3] メールを送る処理を作る：`backend/app/jobs/run.py` の `run_jobs()` が、`email_outbox` の未送信を `FOR UPDATE SKIP LOCKED` で数十件まで取り出して送り、`sent_at` を入れる（失敗は 5 回まで送り直す）。
  送り方は `MAIL_TRANSPORT` で切り替える（`smtp`：開発の Mailpit、`resend`：本番の Resend の API に https で POST。呼ぶ道具は作るときに決める。research.md R-09）。メールを 1 件だけ送る関数 `send_email_now(outbox_id)` も作り、その行だけを同じく押さえて送る（すでに送ってあれば何もしない）。返事・お知らせを保存した API は、**保存をコミットしたあとに**、応答のあとの BackgroundTasks でこれを呼ぶ（コミットの前に呼ぶと、行がまだ見えず送れない）。
  開発用に、1 分ごとに `run_jobs()` を呼ぶ `backend/app/jobs/worker.py` を作る（本番は T092 の API を外から呼ぶ。research.md R-09）（さとこ・ミ）
- [ ] T058 [P] [US3] リクエストと返事のサンプル（返事待ち・返事あり・取り消し）を `backend/app/seed/requests.py` に作る（さとこ・ミ）
- [ ] T059 [US3] 家族の連絡帳の画面を `frontend/src/pages/family/ContactBook.tsx` に作る：返事のカードを一番上に（職員の名前つき）、カードが画面に出たら自動で既読にする、未記録の欄、画面の下に「緊急のときは、施設から電話します」（FR-015・FR-017・FR-028・research.md R-15）。ミニマム版は「今日」だけ（過去の日付は T094）（さとこ・ミ）
- [ ] T060 [US3] 「知りたいこと」を頼む画面と送ったリクエストの一覧を `frontend/src/pages/family/Requests.tsx` に作る：テーマのボタン（3 タップ以内）、「施設に届きました」と送った日時・日数、3 日たったら「お急ぎのときは、施設にお電話ください」、返事の前の取り消し（FR-013・FR-014・SC-002）（さとこ・ミ）
- [ ] T061 [P] [US3] お知らせの一覧の画面を `frontend/src/pages/family/Notifications.tsx` に作る（さとこ・ミ）
- [ ] T062 [US3] 職員の返事の画面を `frontend/src/pages/staff/ReplyPage.tsx` に作る：テーマ・送られた日・日数、定型文のボタン（1 つ以上）、100 文字までの書き足し。リクエストを開いてから 3 タップ以内で保存（FR-030・SC-007）（ゆう・ミ）
- [ ] T063 [US3] 当日中の返事の修正 `PATCH /api/staff/replies/{reply_id}` を `backend/app/api/staff/requests.py` に足す：`template_ids`・`note` を上書きして `edited_at` を入れる、再通知はしない、今日でなければ 409 `not_today`。画面に「直す」を足す（返事の取り消しはしない）（FR-030）（ゆう・作）
- [ ] T064 [US3] `notification_settings` を `backend/app/models/notifications.py` に足し（`notify_reply` 初期値 `true`、`notify_items` 初期値 `{meal,mood,sleep}`、`frequency`：`daily`（初期値）／`weekly`／`none`）、`GET/PUT /api/family/notification-settings` と画面 `frontend/src/pages/family/NotificationSettings.tsx` を作る。送り先のメールアドレスを表示する（FR-023・Edge Cases）（さとこ・作）
- [ ] T065 [US3] まとめの通知を `backend/app/jobs/digest.py` に作り、`run_jobs()` から呼ぶ：日本時間で 20:00 を過ぎて最初に呼ばれたときに、毎日「1 日 1 回」、日曜は「1 週間に 1 回」の家族へ（締めは 20:00）、`get_disclosed_records` で新しい記録があるときだけまとめを作る。`digest_runs`（一意：`(family_account_id, kind, period_end)`）で 2 回送らない。止まっていたらその日のうちだけ取り戻す。`--at` で時刻を指定して動かせる（research.md R-13・quickstart.md）（さとこ・作）
- [ ] T066 [P] [US3] テスト `backend/tests/api/test_digest.py`：同じ時刻で 2 回動かしても 1 回だけ、記録がない日は送らない、非開示の項目だけの日は送らない、20 時台に `run_jobs()` が何度も呼ばれても 1 回だけ、`run_jobs()` と `--at` のコマンドが重なっても 2 回送らない（SC-010・research.md R-13）（さとこ・作）
- [ ] T094 [US3] 家族の連絡帳で過去の日付を選べるようにする（日数の制限なし。過去の日の記録と返事を出す）を `frontend/src/pages/family/ContactBook.tsx` に足す（FR-019。T059 から分けた。PR #23 さとこ）（さとこ・作）
- [ ] T095 [P] [US3] 家族の画面の単体テスト `frontend/tests/unit/ContactBook.test.tsx`（Vitest）：未記録の欄に「まだ記録されていません」が出る、未読の返事のカードが一番上に出る（FR-015・FR-017。PR #23 さとこ）（さとこ・ミ）

**Checkpoint**: 記録 → 開示 → 頼む → 返事 → メール の通しのデモ（quickstart.md の 1〜9）ができる

---

## Phase 6: ファイルの共通の処理（User Story 4 は削除。User Story 5 とアルバム（H）が使う）

**Goal**: （User Story 4「献立表」は削除。Session 2026-10-22）お知らせの添付とアルバムの写真で使う、ファイルの形式の確認・Exif の削除・保存・配信を作る。毎月の献立表も、お知らせの添付で出す

**Independent Test**: 事務員で、行事の案内（PDF）を添付してお知らせを投稿し、家族で開ける。ログインしていないと開けない（spec の US5）

### Tests（ファイルの共通の処理）

- [ ] T067 [P] [US5] テスト `backend/tests/api/test_uploads.py`：PDF・JPG・PNG 以外（先頭のバイトで判定）や 10MB を超えるファイルは 422 `invalid_file`、ログインしていないと `GET /api/files/{id}` は 401（FR-034・SC-016）（さとこ・作）

### Implementation（ファイルの共通の処理）

- [ ] T068 [P] [US5] `uploaded_files` を `backend/app/models/files.py` に作り、マイグレーションを足す。`content_type`：`application/pdf`／`image/jpeg`／`image/png`、`size_bytes` は 10MB まで、`purpose`：`announcement`／`album`（data-model.md）（さとこ・作）
- [ ] T069 [US5] アップロードの共通の処理を `backend/app/services/uploads.py` に作る：先頭のバイトで形式を確かめる（PDF は `%PDF-`、JPEG は `FF D8 FF`、PNG は `89 50 4E 47`）、10MB まで、推測できない `storage_key` で `UPLOAD_DIR` に保存（お知らせ・アルバムで共通。research.md R-10）（さとこ・作）
- T070 [US4] （削除: 献立表の専用の機能をやめたため。毎月の献立表は、お知らせの添付で出す（FR-034）。Session 2026-10-22）
- [ ] T071 [US5] `GET /api/files/{id}` を `backend/app/api/files.py` に作る：ログインと役割を確かめてから返す。`Content-Type` は保存した形式に固定し、`X-Content-Type-Options: nosniff` を付ける（FR-025・FR-034・research.md R-10）（さとこ・作）
- T072 [US4] （削除: 献立表の専用の機能をやめたため。毎月の献立表は、お知らせの添付で出す（FR-034）。Session 2026-10-22）
- T073 [US4] （削除: 献立表のアップロードの画面と、連絡帳の「献立を見る」をやめたため。Session 2026-10-22）
- [ ] T074 [US5] 架空のお知らせの PDF（献立表など）を iPhone の Safari と Android の Chrome で、別タブと画面の中の両方で開けるかを確かめ、結果を research.md R-10 に書く。表示できない環境があれば、PDF を `Content-Disposition: attachment` にする（さとこ・作）
- [ ] T075 [US5] 画像の Exif を取り除く処理（Pillow で開き直して保存）を `backend/app/services/uploads.py` に足し、テストを `backend/tests/api/test_uploads.py` に足す（FR-034）（さとこ・作）
- [ ] T076 [US5] 本番の保存先（S3 互換のオブジェクトストレージ、非公開のバケット）への切り替えを `backend/app/services/uploads.py` に足す（環境変数で切り替える）（さとこ・作）

**Checkpoint**: ファイルの形式の確認・Exif の削除・保存・配信ができ、ログインしていない人は開けない

---

## Phase 7: User Story 5 - 施設が全家族にお知らせを出す（Priority: P5）

**Goal**: 事務員・相談員・施設長が、タイトル・本文・添付 1 つまでのお知らせを全家族に出し、メールにはタイトルだけが届く

**Independent Test**: 施設長で「面会を一時中止します」を投稿し、家族のメール（Mailpit）にタイトルだけのメールが届き、アプリのお知らせ一覧から本文が読める（spec の US5）

### Tests for User Story 5

- [ ] T077 [P] [US5] テスト `backend/tests/api/test_announcements.py`：投稿で全家族に `notifications` と `email_outbox` ができ、メールに本文・添付が入らない。頻度が「通知しない」の家族にも届く。投稿のあとに作った家族にも過去のお知らせが出る。取り消すと一覧から消え、添付も開けない（404）（FR-034・SC-016）（さとこ・作）

### Implementation for User Story 5

- [ ] T078 [P] [US5] `facility_announcements` を `backend/app/models/announcements.py` に作り、マイグレーションを足す。`title` は `varchar(40)`、`body` は `varchar(1000)`、`file_id` は任意・1 つ（data-model.md）（さとこ・作）
- [ ] T079 [US5] `GET/POST /api/admin/announcements`・`DELETE /api/admin/announcements/{id}` を `backend/app/api/admin/announcements.py` に作る（役割：事務員・相談員・施設長。だれが投稿したものでも取り消せる）。投稿で全家族のお知らせとメールの送る予定を作る（FR-034）（さとこ・作）
- [ ] T080 [US5] `GET /api/family/announcements/{id}` を `backend/app/api/family/announcements.py` に作り、`GET /api/family/notifications` に取り消していない施設からのお知らせを合わせて並べる（FR-034）（さとこ・作）
- [ ] T081 [US5] 投稿の画面を `frontend/src/pages/admin/Announcements.tsx` に（注意書き「入居者個人の体調や事故の連絡には使わず、電話でお知らせください」「本文に入居者の名前を書かないでください」）、家族のお知らせの詳細を `frontend/src/pages/family/AnnouncementDetail.tsx` に作る（FR-034）（さとこ・作）

**Checkpoint**: 施設からのお知らせが、全家族にタイトルだけのメールで届く

---

## Phase 8: Polish & Cross-Cutting Concerns（作り込み・仕上げ）

**Purpose**: 多言語・ふりがな、ログインの作り込み、E2E、本番デプロイ

- [ ] T082 [P] インドネシア語・英語の辞書 `frontend/src/i18n/id.json`・`frontend/src/i18n/en.json` を作る（テーマ・定型文・ボタン・見出し・案内文。ふりがなの書き方は使わない）（FR-021）（みさき・作）
- [ ] T083 spec 001 の全画面（ログイン・記録・開示設定・職員の返事・家族の連絡帳・知りたいこと・お知らせ・管理画面など、ほかの人が作った画面も含む）の日本語の文言に `{漢字|かんじ}` でふりがなを付ける（固定の文言だけ。利用者が自由に入力した文・お知らせの添付ファイルは対象外）。各画面の文言が固まってから（Day 5）まとめて付ける。spec 002〜007 の画面は、それぞれの spec のタスク（002-T041・003-T035・005-T016・006-T022・007-T029 など）で各担当が付ける。どちらも `ja.json` を書き換えてぶつかりやすいので、ほかの spec のふりがなのタスクは Day 5 より前に済ませるか、T083 のあとに行う（PR #54 ゆう）。最後に T085 で全体の付け忘れを確かめる（担当は PR #52 の相談で決めた）（FR-021）（みさき・作）
- [ ] T084 表示言語の切り替え `PUT /api/me/language` を `backend/app/auth/routes.py` に、切り替えの部品を `frontend/src/components/LanguageSwitcher.tsx` に作る。メールは家族の言語の文言で、漢字だけにして送る（FR-021）（みさき・作）
- [ ] T085 [P] テスト `frontend/tests/unit/i18n.test.ts`：`ja.json` にふりがなの付いていない漢字が残っていない、`id.json`・`en.json` に `{|}` の書き方がない（SC-011）（みさき・作）
- [ ] T086 職員は操作がないまま 30 分で自動ログアウト、家族は 30 日、を `backend/app/auth/` に足す（research.md R-01）（ようこ・作）
- [ ] T087 ログインの試行回数の制限（Redis の `ratelimit:login:<ID>`、例：15 分に 10 回、超えたら 429 `too_many_attempts`）を `backend/app/auth/routes.py` に足す（research.md R-03）（ようこ・作）
- [ ] T088 職員のアカウントを作る `POST /api/admin/staff`（ID と初期パスワード）と画面 `frontend/src/pages/admin/StaffAccounts.tsx` を作る（ようこ・作）
- [ ] T089 家族の招待：`invitations`（家族だけ、7 日で切れる、1 回だけ使える）を `backend/app/models/core.py` に足し、`POST /api/admin/invitations`・`POST /api/invitations/accept`（トークンは本文で受ける、メールのリンクは `#token=`）と画面を作る。招待のメールは `email_outbox`（`invitation`）を使う（research.md R-03）（ようこ・作）
- [ ] T090 CI（`.github/workflows/ci.yml`）に `alembic heads` が 1 つであることの確認を足す（PostgreSQL・Redis のサービスは T020 で入れる。research.md R-17）（ようこ・作）
- [ ] T091 E2E テストを `frontend/tests/e2e/` に Playwright で作る：quickstart.md の通しの確認（記録 → 開示 → 頼む → 返事 → メール → お知らせ）と、家族が職員の画面を開けないこと（ようこ・作）
- [ ] T092 本番デプロイ（Render の無料のプラン）：フロントは Static Site に置き、書き換えのルールで `/api/*` をバックエンド（無料の Web Service 1 つだけ）に中継する構成（最初に、中継を通してログインの Cookie が付くかを確かめる）、https、本番のメール送信サービス（Resend。送信元のドメインの確認）とファイルの保存先の環境変数（research.md R-03・R-09・R-10）。
  決まった時刻の処理の受け口 `POST /api/internal/jobs/run` を `backend/app/api/internal.py` に作り（`JOBS_TOKEN` が空なら登録しない。テストつき。contracts/api.md）、cron-job.org から 1 分ごとに呼ぶ設定をする（ようこ・作）
- [ ] T093 quickstart.md の確認をすべて通し、`docs/テスト設計書.md` に結合・総合テストのシナリオと結果を書く（Constitution の課題要件のテスト）（全員・作）

---

## Dependencies & Execution Order

### Phase の順番

- **Setup（Phase 1）**：最初に。ようこが Day 1 の午前に進める
- **Foundational（Phase 2）**：Setup のあと。T009（共通のテーブル）・T010（ログイン中の人）・T015（初期データ）ができると、各 User Story の API を始められる。T022（本物のログイン）は Day 2 で、それまでは T013（ユーザー切り替え）で進める
- **User Story（Phase 3〜7）**：Foundational のあと。担当が分かれているので、US1・US2・US4 は並べて進められる
- **Polish（Phase 8）**：ミニマム版の通しのデモ（Day 4）のあと

### User Story のつながり

- **US1（P1）**：Foundational のあとすぐ始められる
- **US2（P2）**：テーブルは US1 と別。`get_disclosed_records`（T038）は `care_records`（T025）が要る
- **US3（P3）**：`get_disclosed_records`・`get_disclosed_themes`（T038）、テーマ・定型文（T037）が要る。記録がない状態でも、テーマと返事だけでデモできる
- **US4（P4）**：削除（Session 2026-10-22）。ファイルの共通の処理（T067〜T069・T071・T074〜T076）は、US5 の前に作る
- **US5（P5）**：`uploaded_files`・`services/uploads.py`（T068・T069）と、`notifications`・`email_outbox`・worker（T048・T057）が要る

### 人をまたぐつなぎ目（先に形を合わせる）

| つなぎ目 | 作る人 → 使う人 | タスク |
|---|---|---|
| `CurrentUser` と役割のチェック | ようこ → 全員 | T010 → 全 API |
| 共通の関数 3 つ | ゆう → さとこ・みさき（F） | T038・T054 → T049・T055・T065 |
| `create_reply_notice(session, reply_id)`（`email_outbox` の id を返す） | さとこ → ゆう | T051 → T052 |
| `send_email_now(outbox_id)`（メールを 1 件だけその場で送る。返事の保存をコミットしたあとに呼ぶ） | さとこ → ゆう | T057 → T053 |
| メールの送る予定（`email_outbox`） | さとこ → ようこ（招待） | T048・T057 → T089 |
| 辞書と `Ruby` の部品 | みさき → 全員の画面 | T016・T017 → 全画面 |
| アップロードの共通の処理 | さとこ → さとこ（お知らせ）・アルバム（H） | T069 → T079 |

### User Story の中の順番

- テスト → テーブル（モデル）→ サービス → API → 画面
- マイグレーションは作る直前に main を取り込む（research.md R-17）

---

## Parallel Example

### Day 1（Setup・Foundational と並べて）

```text
ようこ：T001 → T002・T003 → T004・T008 → T009 → T010・T013・T015
みさき：T016・T017（辞書と Ruby の土台）
ゆう：  T025（care_records のモデル。T009 のあと）、T031（入居者一覧の画面のひな形）
        → T036・T038（開示設定と共通の関数）のすぐあとに T047・T054（replies と get_active_replies。さとこの T055 が使うため前倒し。PR #23 ゆう）
さとこ：T059（家族の連絡帳の画面のひな形）、T046・T048（モデル。T009 のあと）
```

ようこは T001・T002・T003（フロントのひな形と ESLint＝T005 を含む）を朝いちばんに作り、T012 は T010 と一緒に入れる。T018・T019 もようこが持つ（PR #23 ようこ）。

### User Story 3（Day 2〜4）

```text
並べて進める：T043（さとこ）・T044（ゆう）・T045（さとこ）のテスト
並べて進める：T046（さとこ）・T047（ゆう）・T048（さとこ）のモデル
つなぎ目：T051（さとこ）が先 → T052（ゆう）
画面は並べて：T059・T060・T061（さとこ）・T062（ゆう）
```

---

## Implementation Strategy

### ミニマム版（Day 1〜4）

1. Phase 1・2（「ミ」のタスク）
2. US1・US2・US3 の「ミ」のタスク
3. **Day 4 の終わりに通しのデモ**：quickstart.md の 1〜9（職員が記録 → 開示 → 家族が頼む → 職員が返事 → メールが届く）。F（AI）・J（決済）は別の spec で同じ日にミニマム版を動かす（Constitution 原則 V）

### 作り込み（Day 5）

- 「作」のタスクを、担当ごとの優先順位で進める。さとこは「返事のお知らせ → 通知設定とまとめ → ファイルの共通の処理 → 施設からのお知らせ（献立表の投稿も含む）」の順（plan.md）
- 各 User Story の Checkpoint で、quickstart.md の該当する確認を通してから次へ進む

### 仕上げ（Day 5〜6）

- Phase 8 のふりがな・多言語の仕上げ、E2E、テストシナリオの実施（T093）、本番デプロイの確認

---

## Notes

- [P] のタスクは別のファイルで、終わっていないタスクに依存しない
- 家族に出すものは、必ず共通の関数（`get_disclosed_records`・`get_disclosed_themes`・`get_active_replies`）を通す。家族向けの API で記録を直接読まない
- 家族の連絡帳はキャッシュしない（開発前MTG の決定事項）
- メールの文面に、記録・返事・お知らせの本文を入れない
- 1 PR は 1,100 行以内（`specs/` とロックファイルは数えない）。超えそうなら issue とブランチを分ける
