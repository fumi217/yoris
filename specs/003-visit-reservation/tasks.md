---

description: "spec 003（面会予約）のタスク一覧"
---

# Tasks: 家族がアプリから面会を予約する（G）

**Input**: `specs/003-visit-reservation/` の [spec.md](./spec.md)・[plan.md](./plan.md)・[research.md](./research.md)・[data-model.md](./data-model.md)・[contracts/api.md](./contracts/api.md)・[quickstart.md](./quickstart.md)

**Tests**: テストのタスクを含める（Constitution の課題要件「単体テストはテストコードを書く」、research.md R-09）。各 User Story で、テストを先に書いて失敗することを確かめてから作る。メールはモックにする。

**Organization**: User Story ごとにまとめる。各タスクの末尾に **（担当・時期）** を書く。時期の「ミ」は Day 1〜4 のミニマム版、「作」は Day 5 の作り込み（Day は docs/マイルストーン.md の表が正。#53）（[plan.md の「ミニマム版と作り込み」](./plan.md#ミニマム版と作り込み)）。
タスク番号はこの spec の中の番号。spec 001 のタスクは **001-T009** のように書いて区別する。
issue は担当者が、ここから自分のタスクを選んで立てる（1 issue は 1 PR で 1,100 行以内に収まる量。`.claude/skills/github-workflow/SKILL.md`）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: ほかのタスクと並べて進められる（別のファイルで、終わっていないタスクに依存しない）
- **[Story]**: どの User Story のタスクか（US1〜US4）。Foundational・Polish には付けない
- パスは plan.md の構成（`backend/app/`・`frontend/src/`）に合わせる

---

## Phase 1: Setup

**Purpose**: この spec で足す土台はない。spec 001 の Phase 1（001-T001〜001-T007：Docker Compose・バックエンドとフロントのひな形・Alembic・lint・ログ・`env.example`）をそのまま使う

---

## Phase 2: Foundational（面会予約の全 User Story の前に必要なもの）

**Purpose**: 面会予約のテーブルと決まり、時刻の判定、初期データ

**⚠️ CRITICAL**: spec 001 の 001-T009（共通のテーブル）・001-T010（`CurrentUser` と役割のチェック）・001-T012（エラーの形）・001-T015（初期データの仕組み）のあとに始める

- [x] T001 面会予約のテーブルを `backend/app/models/visits.py` に作り、マイグレーションを足す（data-model.md）。マイグレーションの最初に `CREATE EXTENSION IF NOT EXISTS btree_gist` を入れる。
  `visit_settings`（`facility_id` が主キー、`daily_limit` は「1 日に受け付ける組数。初期値 2。1 以上」）、
  `visit_start_times`（`start_time` は日本時間の `time`、`active` は boolean、一意は `(facility_id, start_time)`）、
  `visit_reservations`（`visit_date`・`start_time`・`starts_at`・`ends_at`（`ends_at = starts_at + 1 時間 30 分`）・`party_size`「1 以上、上限なし」・`status`：`booked`／`cancelled_by_family`／`cancelled_by_staff`・`created_at`・`cancelled_at`・`cancelled_by_staff_id`・`cancel_reason`）。
  決まり：`UNIQUE (resident_id, visit_date) WHERE status = 'booked'`、`EXCLUDE USING gist (facility_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) WHERE (status = 'booked')`、
  `CHECK (party_size >= 1)`、`CHECK (status <> 'cancelled_by_staff' OR (cancel_reason IS NOT NULL AND cancelled_by_staff_id IS NOT NULL))`（research.md R-01・R-02）（ゆう・ミ）
- [x] T002 [P] 日本時間の「今」を返す関数を使えるようにする：spec 001 で作られていればそれを使い、なければ `backend/app/clock.py` に `now_jst()` を作る。テストで時刻を固定できるよう、差し替えられる形にする（research.md R-04・R-09）（ゆう・ミ）
- [x] T003 [P] エラーのコードを、001-T012 のエラーの形に足す（`forbidden`・`not_found` は 001-T012 でようこが足すので、ここでは足さない）：`visit_overlap`・`visit_day_full`・`visit_already_booked_day`・`visit_deadline_passed`・`visit_closed_day`・`visit_day_has_reservations`（409）、`visit_out_of_range`（422）。日本語の文言は `frontend/src/i18n/ja.json` の `error.*` に足す（contracts/api.md）（ゆう・ミ）
- [x] T004 [P] 初期データを `backend/app/seed/visits.py` に作り、001-T015 の仕組みに足す：`visit_settings`（`daily_limit = 2`）、`visit_start_times`（10:00・10:30・13:00・13:30・14:00・14:30・15:00・15:30、すべて `active = true`）、デモ用の予約（来週の平日に 1〜2 件、架空の家族）。施設がすでにあれば、その施設に足す（001-T015 の決まりに合わせる）（ゆう・ミ）

**Checkpoint**: マイグレーションと初期データが通り、DB に開始時刻の候補 8 つと 1 日 2 組の設定が入っている

---

## Phase 3: User Story 1 - 家族が空いている時間を見て面会を予約する（Priority: P1）🎯 ミニマム版

**Goal**: 家族が、日付ごとの開始時刻の候補と「選べるかどうか」を見て、開始時刻と人数を選んで予約できる。同時に予約されても、時間の重なり・1 日 3 組目・同じ家族の同じ日の 2 回目は確定しない

**Independent Test**: quickstart.md の 1〜9（家族 A が 10:30 を予約 → 家族 B から 10:00・10:30 が選べない → 家族 B が 13:00 を予約 → その日は満員 → 同時の予約は 1 件だけ確定）

### Tests for User Story 1（先に書いて、失敗することを確かめる）⚠️

- [x] T005 [P] [US1] 単体テスト `backend/tests/unit/test_visit_rules.py`：予約できる日（明日 ≦ 日付 ≦ 今日＋28 日）、明日の予約は今日の 17:00 より前だけ、面会の時間が重なるかの判定（10:30 の予約に対して 10:00・10:30 は重なり、13:00 は重ならない）、開始時刻が候補にないとき。時刻は T002 の関数を差し替えて固定する（FR-004・FR-007・FR-008、research.md R-04）（ゆう・ミ）
- [x] T006 [P] [US1] API テスト `backend/tests/api/test_visits.py`（予約）：
  予約が確定する／**2 つの家族が同じ日の 13:00 と 13:30 をスレッドで同時に予約すると、1 件だけ確定し、もう一方は 409 `visit_overlap`**／
  **1 組入っている日に、2 つの家族が 13:00 と 15:00 を同時に予約すると、1 件だけ確定し、もう一方は 409 `visit_day_full`**／
  同じ家族の同じ日の 2 回目は 409 `visit_already_booked_day`／前日 17 時を過ぎた明日の予約は 409 `visit_deadline_passed`／
  4 週間より先・過去は 422 `visit_out_of_range`／人数 0 は 422／本文に `resident_id` を入れても受け付けない（422）、または無視され、ログイン中の家族の入居者で予約される／
  職員のロールで家族の API を呼ぶと 403／ログインしていないと 401（FR-002・FR-003・FR-005・FR-008・SC-002、research.md R-01・R-05）（ゆう・ミ）
- [x] T007 [P] [US1] API テスト（選べるかどうか）を `backend/tests/api/test_visits.py` に足す：返り値に、ほかの家族の名前・入居者名・人数・選べない理由が入っていない。その家族が予約している日は `mine: true`。2 組入った日は、すべて `selectable: false`（FR-001・FR-004、research.md R-03）（ゆう・ミ）

### Implementation for User Story 1

- [x] T008 [US1] 判定の関数を `backend/app/services/visit_rules.py` に作る：予約できる日か、締め切り前か、開始時刻が候補にあるか、面会の時間の範囲（開始＋1 時間 30 分）、重なるか。DB を読まない純粋な関数にする（T005 を通す）（ゆう・ミ）
- [x] T009 [US1] 予約を作る唯一の道 `book_visit(session, current_user, visit_date, start_time, party_size)` を `backend/app/services/visits.py` に作る（research.md R-01）：
  1 つのトランザクションの中で、`pg_advisory_xact_lock(<visit_date から作った数>)` → その日の `booked` の件数 < `daily_limit` → 同じ入居者のその日の `booked` がない → 重なりがない → 追加。
  入居者は `current_user.resident_id` から決める。DB の決まり（一意制約・排他制約）に引っかかったときも、それぞれ 409 `visit_already_booked_day`・`visit_overlap` に変える（T006 を通す）（ゆう・ミ）
- [x] T010 [US1] 選べるかどうかの計算 `get_availability(session, current_user, date_from, date_to)` を `backend/app/services/visits.py` に作る：
  日付ごとに `active` な開始時刻の候補と `selectable`、その家族の予約がある日は `mine: true`。選べない理由やほかの家族の情報は返さない（research.md R-03）（T007 を通す）（ゆう・ミ）
- [x] T011 [US1] `GET /api/family/visits/availability?from=&to=`・`POST /api/family/visits` を `backend/app/api/family/visits.py` に作る（`require_family`）。
  POST の入力は `visit_date`・`start_time`・`party_size` だけで、入居者の欄は持たない（Pydantic で余分な項目を受け付けない）。ルーターを `backend/app/main.py` に登録する（contracts/api.md）（ゆう・ミ）
- [x] T012 [P] [US1] 家族の面会の予約の画面を `frontend/src/pages/family/visits/VisitBooking.tsx` に作る：日付を選ぶ → 開始時刻のボタン（`selectable: false` は押せない）→ 人数（1 以上）→ 「予約する」。
  確定したら日時・人数とともに「予約が確定しました」。409 のときは `message_key` の文言を出して、空きを読み直す。画面を開いてから確定まで 5 タップ以内（SC-001）。文言は辞書（001-T016）から引く（ゆう・ミ）
- [x] T013 [P] [US1] Vitest `frontend/src/pages/family/visits/VisitBooking.test.tsx`（ほかのテストと同じく画面の隣に置く。型チェックは `src` だけが対象のため）：`selectable: false` の開始時刻が押せない、`mine: true` の日は「予約済み」と出る（research.md R-09）（ゆう・ミ）
- [x] T014 [US1] 家族の画面の枠（001-T019）に、面会の予約の画面へのルート（例：`/family/visits`）を足し、「☰ その他」のメニューの中に「面会」を足す（家族の画面のメニューは、下に連絡帳・知りたいこと・お知らせの 3 つ、そのほかは「☰ その他」。spec 001 の Clarifications、PR #29）。連絡帳（ホーム）の画面は触らない。家族の画面のほかのファイルは触らない（plan.md の Structure Decision）。メニューの枠は、ようこ（001-T019）が作る（ゆう・ミ。001-T019 の担当のようこと相談）

**Checkpoint**: quickstart.md の 1〜9 が通る。ここまでが Day 4 の通しのデモに入る

---

## Phase 4: User Story 2 - 家族が自分の予約を見て、取り消す（Priority: P2）

**Goal**: 家族が自分のこれからの予約を見て、前日 17 時までなら取り消せる

**Independent Test**: quickstart.md の 11・12

### Tests for User Story 2 ⚠️

- [x] T015 [P] [US2] API テストを `backend/tests/api/test_visits.py` に足す：自分のこれからの予約だけが返る／前日 17 時より前の取り消しは成功し、その時間がまた選べる／過ぎたら 409 `visit_deadline_passed`／
  **ほかの家族の予約の id を指定した取り消しは 404**（存在するかも知らせない）（FR-006・FR-007・FR-015・SC-004）（ゆう・作）

### Implementation for User Story 2

- [x] T016 [US2] 家族の取り消し `cancel_by_family(session, current_user, reservation_id)` を `backend/app/services/visits.py` に作る：自分の入居者の `booked` でなければ 404、締め切りは T008 の関数で判定、`status = 'cancelled_by_family'`・`cancelled_at` を入れる。家族が自分で取り消したときは、お知らせを作らない（research.md R-07）（ゆう・作）
- [x] T017 [US2] `GET /api/family/visits`・`DELETE /api/family/visits/{id}` を `backend/app/api/family/visits.py` に足す。職員が取り消した予約は、理由もいっしょに返す（contracts/api.md）（ゆう・作）
- [x] T018 [P] [US2] 自分の予約の画面を `frontend/src/pages/family/visits/MyVisits.tsx` に作る：これからの予約（日時・人数・状態）と「取り消す」ボタン。締め切りを過ぎたら「締め切りを過ぎたため、施設にお電話ください」。職員が取り消した予約は理由を文字として出す（HTML として埋め込まない。FR-016）（ゆう・作）

**Checkpoint**: quickstart.md の 11・12 が通る

---

## Phase 5: User Story 3 - 施設が開始時刻の候補と休みの日を管理し、予約を確認する（Priority: P3）

**Goal**: 事務員・相談員・施設長が開始時刻の候補・1 日の組数・休みの日を設定でき、職員のすべてが予約の一覧と今日の面会予定を見られる

**Independent Test**: quickstart.md の 13〜15

### Tests for User Story 3 ⚠️

- [x] T019 [P] [US3] API テスト `backend/tests/api/test_visit_admin.py`：
  設定（開始時刻の候補・組数・休みの日）は事務員・相談員・施設長だけ（介護職員・リーダーは 403、家族は 403）／予約の一覧と今日の面会予定は職員のすべてが見られる（家族は 403）／
  開始時刻＋1 時間 30 分が 17:00 を超える候補は 422／候補から外しても、すでに入っている予約は残る／
  予約が入っている日を休みにすると 409 `visit_day_has_reservations`（件数つき）、`confirm_cancel: true` と理由を付けると、その日の予約が職員の取り消しになって休みになる／休みの日の予約は 409 `visit_closed_day`（FR-009〜FR-011、research.md R-06・R-08）（ゆう・作）

### Implementation for User Story 3

- [x] T020 [US3] `visit_closed_days`（一意は `(facility_id, closed_date)`）を `backend/app/models/visits.py` に足し、マイグレーションを足す（data-model.md）（ゆう・作）
- [x] T021 [US3] 休みの日を、`book_visit`（T009）と `get_availability`（T010）に足す：休みの日は 409 `visit_closed_day`・すべて `selectable: false`（FR-010）（ゆう・作）
- [x] T022 [US3] `GET /api/admin/visit-settings`・`PUT /api/admin/visit-settings` を `backend/app/api/admin/visits.py` に作る（`require_staff(["clerk","counselor","director"])`）（FR-009）（ゆう・作）
- [x] T023 [US3] `GET /api/admin/visit-closed-days`・`POST /api/admin/visit-closed-days`・`DELETE /api/admin/visit-closed-days/{id}` を `backend/app/api/admin/visits.py` に足す。
  予約がある日の `confirm_cancel: true` は、その日の予約を T031 と同じ取り消しの処理で取り消してから休みにする（1 つのトランザクション。research.md R-08）（ゆう・作）
- [x] T024 [US3] `GET /api/admin/visits?from=&to=`（職員のすべて）を `backend/app/api/admin/visits.py` に、`GET /api/staff/visits/today`（職員のすべて）を `backend/app/api/staff/visits.py` に作る（FR-011）（ゆう・作）
- [ ] T025 [P] [US3] 開始時刻の候補・1 日の組数・休みの日の画面を `frontend/src/pages/admin/VisitSettings.tsx` に作る（予約がある日を休みにするときは、警告と理由の入力を出す）（ゆう・作）
- [ ] T026 [P] [US3] 予約の一覧の画面を `frontend/src/pages/admin/VisitReservations.tsx` に作る（日付・時刻・入居者名・人数・予約した日時・状態）（ゆう・作）
- [ ] T027 [P] [US3] 今日の面会予定の画面を `frontend/src/pages/staff/TodayVisits.tsx` に作り、職員の画面（入居者一覧など）からリンクする（ゆう・作）

**Checkpoint**: quickstart.md の 13〜15 が通る

---

## Phase 6: User Story 4 - 施設が予約を取り消し、家族に知らせる（Priority: P4）

**Goal**: 職員が理由を入れて予約を取り消せ、家族に予約の確定・取り消し・前日 20 時の知らせが、メールとアプリ内のお知らせで届く

**Independent Test**: quickstart.md の 16〜19

### Tests for User Story 4 ⚠️

- [ ] T028 [P] [US4] API テスト `backend/tests/api/test_visit_notices.py`：
  職員の取り消しは理由が必須（ないと 422）、取り消した職員・日時・理由が残る／取り消しの理由に `<script>` を入れても文字として返る／
  予約の確定と職員の取り消しで、`notifications` と `email_outbox` が同じトランザクションで 1 件ずつできる（取り消しが失敗したら、お知らせもできない）／
  家族が自分で取り消したときは、お知らせができない／`email_outbox` の `params` に入居者名・理由が入っていない（FR-012〜FR-014・FR-016・SC-003）（ゆう・作）
- [ ] T029 [P] [US4] テスト `backend/tests/unit/test_visit_reminder.py`：前日 20 時の処理を 2 回動かしても（20 時台に `run_jobs()` が何度呼ばれても）、同じ予約への `visit_reminder` は 1 件だけ。取り消された予約には送らない（FR-013）（さとこ・作）

### Implementation for User Story 4

- [x] T030 [US4] `notifications` に `visit_reservation_id`（→ `visit_reservations`）と、種類 `visit_confirmed`・`visit_cancelled`・`visit_reminder` を足し、`UNIQUE (visit_reservation_id, kind) WHERE kind = 'visit_reminder'` を付ける。
  `create_visit_notice(session, reservation_id, kind)` を `backend/app/services/notifications.py` に作る（関数の中では commit しない。通知の頻度の設定には関係なく作る）。T001 のあと（さとこ・作）
- [ ] T031 [US4] 職員の取り消し `POST /api/admin/visits/{id}/cancel`（職員のすべて。`reason` は必須）を `backend/app/api/admin/visits.py` に、処理を `backend/app/services/visits.py` に作り、同じトランザクションで `create_visit_notice(..., "visit_cancelled")` を呼ぶ。
  予約の一覧の画面（T026）に、理由を入れて取り消すボタンを足す。締め切りは設けない（FR-012・FR-013）（ゆう・作。T030 のあと）
- [ ] T032 [US4] `book_visit`（T009）で、予約を追加したあと同じトランザクションで `create_visit_notice(..., "visit_confirmed")` を呼ぶ（ゆう・作。T030 のあと）
- [x] T033 [P] [US4] メールのテンプレート `visit_confirmed`（面会の予約が確定しました）・`visit_cancelled`（面会の予約が取り消されました）・`visit_reminder`（明日は面会の予定があります。本文に「変更・取り消しは、施設にお電話ください」）を足す。渡すのは**日時とリンクだけ**（入居者名・理由は渡さない。FR-014）（さとこ・作）
- [ ] T034 [US4] 前日 20 時の知らせを `backend/app/jobs/visit_reminder.py` に作り、`run_jobs()`（001-T057）から呼ぶ：日本時間で 20:00 を過ぎて最初に呼ばれたときに、翌日の `booked` ごとに `visit_reminder` を作る（同じ予約に 1 回だけ。20 時台に何度呼ばれても増えない）。`--at` で時刻を指定して動かせる（spec 001 R-13 と同じ形）（さとこ・作）

**Checkpoint**: quickstart.md の 16〜19 が通る

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T035 [P] 面会予約の画面の固定の文言に、`{漢字|かんじ}` でふりがなを付ける（`frontend/src/i18n/ja.json`）。インドネシア語・英語の訳は 001-T082（みさき）にまとめて頼む（FR-021 は spec 001。Constitution の UI 方針）（ゆう・作）
- [ ] T036 [P] E2E（Playwright）に、quickstart.md の 1〜7（予約 → 重なる時刻が選べない → 2 組で満員 → 同じ家族の 2 回目）を `frontend/tests/e2e/visits.spec.ts` として足す（001-T091 の E2E の仕組みを使う）（ゆう・作。ようこと相談）
- [ ] T037 `docs/テスト設計書.md` に、面会予約の結合・総合テストのシナリオ（quickstart.md の 1〜19）と結果を書く（001-T093 と同じ形）（ゆう・作）
- [ ] T038 quickstart.md の確認をすべて通す（ゆう・作）

---

## Dependencies & Execution Order

### Phase の順番

- **Phase 2（Foundational）**：spec 001 の 001-T009・001-T010・001-T012・001-T015 のあと。T001 のあとに T004、T002・T003 は並べて進められる
- **Phase 3（US1）**：Phase 2 のあと。ミニマム版（Day 4 まで）
- **Phase 4〜6（US2〜US4）**：US1 のあと。作り込み（Day 5）。US2・US3 は並べて進められる。US4 は T030（さとこ）が先
- **Phase 7（Polish）**：Day 4 の通しのデモのあと

### User Story のつながり

- **US1（P1）**：Phase 2 だけで始められる
- **US2（P2）**：US1 の予約が要る（自分の予約を取り消すため）
- **US3（P3）**：US1 の `book_visit`・`get_availability` に休みの日を足す（T021）
- **US4（P4）**：US1（`book_visit`）と US3（予約の一覧の画面 T026）が要る。お知らせはさとこの T030 が先

### 人をまたぐつなぎ目（先に形を合わせる）

| つなぎ目 | 作る人 → 使う人 | タスク |
|---|---|---|
| 共通のテーブル（施設・入居者・家族アカウント・職員） | ようこ → ゆう | 001-T009 → T001 |
| `CurrentUser`（`resident_id`）と役割のチェック（`require_family`・`require_staff(roles)`） | ようこ → ゆう | 001-T010 → T011・T017・T022〜T024・T031 |
| エラーの形 | ようこ → ゆう | 001-T012 → T003 |
| 開発用のユーザー切り替え（家族 A・B・C で試す） | ようこ → ゆう | 001-T013 → quickstart の確認 |
| 初期データの仕組み | ようこ → ゆう | 001-T015 → T004 |
| 辞書と `Ruby` の部品 | みさき → ゆう | 001-T016・001-T017 → T003・T012・T035 |
| 家族の画面の枠（メニュー・ルーティング） | ようこ → ゆう | 001-T019 → T014 |
| `visit_reservations` | ゆう → さとこ | T001 → T030 |
| `create_visit_notice(session, reservation_id, kind)` | さとこ → ゆう | T030 → T031・T032 |
| `email_outbox`・`run_jobs()` の 20:00 の処理 | さとこ → さとこ | spec 001 の通知（001-T048・001-T057・001-T065）→ T033・T034 |
| E2E の仕組み | ようこ → ゆう | 001-T091 → T036 |

### User Story の中の順番

- テスト → テーブル（モデル）→ サービス → API → 画面
- マイグレーションは作る直前に main を取り込む（spec 001 の research.md R-17）

---

## Parallel Example

### User Story 1（Day 2〜4）

```text
並べて進める（テスト）：T005・T006・T007
並べて進める（画面）  ：T012・T013（API の形は contracts/api.md で決まっているので、T011 と並べてよい）
順番に進める          ：T008 → T009 → T010 → T011 → T014
```

### 作り込み（Day 5）

```text
並べて進める：US2（T015〜T018）と US3（T019〜T027）
さとこと並べて：T030・T033・T034（さとこ）が先 → T031・T032（ゆう）
```

---

## Implementation Strategy

### ミニマム版（Day 1〜4）

1. Phase 2（T001〜T004。spec 001 の土台のあと）
2. Phase 3（US1：T005〜T014）
3. **Day 4 の通しのデモ**：quickstart.md の 1〜7（家族 A が予約 → 家族 B から重なる時刻が選べない → 2 組で満員）。同時の予約（8・9）はテストで見せる

### 作り込み（Day 5）

- US2 → US3 → US4 の順。US4 はさとこの T030 ができてから
- 各 User Story の Checkpoint で、quickstart.md の該当する確認を通してから次へ進む

### 仕上げ（Day 5〜6）

- Phase 7 のふりがな、E2E、テスト設計書、quickstart の通し

---

## Notes

- [P] のタスクは別のファイルで、終わっていないタスクに依存しない
- 予約を作る道は `book_visit` の 1 つだけ。ほかの API・画面・初期データから `visit_reservations` に直接追加しない（初期データは例外として、決まりに合う予約だけを入れる）
- 家族の API は入居者を受け取らない。ログイン中の家族の `resident_id` から決める
- メールに入居者名・取り消しの理由を入れない
- 1 PR は 1,100 行以内（`specs/` とロックファイルは数えない）。超えそうなら issue とブランチを分ける
