---

description: "spec 006（E：変化の検知）のタスク一覧"
---

# Tasks: 記録から入居者のいつもと違う様子に気づき、職員に知らせる（E：変化の検知）

**Input**: `specs/006-change-detection/` の [spec.md](./spec.md)・[plan.md](./plan.md)・[research.md](./research.md)・[data-model.md](./data-model.md)・[contracts/api.md](./contracts/api.md)・[quickstart.md](./quickstart.md)

**Tests**: テストのタスクを含める（Constitution の課題要件「単体テストはテストコードを書く」、research.md R-08）。各 User Story で、テストを先に書いて失敗することを確かめてから作る。

**Organization**: User Story ごとにまとめる。各タスクの末尾に **（担当）** を書く。この spec は **すべて作り込み（Day 5・10/28）** で、ミニマム版（Day 1〜4）には入れない（spec の User Scenarios・docs/マイルストーン.md）。
タスク番号はこの spec の中の番号。spec 001 のタスクは **001-T026** のように書いて区別する。issue のタイトルには「spec 006」を入れる。
issue は担当者が、ここから自分のタスクを選んで立てる（1 issue は 1 PR で 1,100 行以内に収まる量。`.claude/skills/github-workflow/SKILL.md`）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: ほかのタスクと並べて進められる（別のファイルで、終わっていないタスクに依存しない）
- **[Story]**: どの User Story のタスクか（US1〜US3）。Foundational・Polish には付けない
- パスは plan.md の構成（`backend/app/`・`frontend/src/`）に合わせる

---

## Phase 1: Setup

**Purpose**: この spec で足す土台はない。spec 001 の Phase 1（001-T001〜001-T007：Docker Compose・ひな形・Alembic・lint・ログ・`env.example`）をそのまま使う。新しいライブラリも足さない（plan の Technical Context）

---

## Phase 2: Foundational（変化の検知の全 User Story の前に必要なもの）

**Purpose**: 決まりの関数、変化の検知のテーブル、決まりの初期データ

**⚠️ CRITICAL**: spec 001 の 001-T009（共通のテーブル）・001-T010（`CurrentUser` と役割のチェック）・001-T012（エラーの形）・001-T015（初期データの仕組み）・001-T020（テストの土台）・001-T025（`care_records`）のあとに始める。
ただし T001・T002（決まりの関数とそのテスト）は DB を使わないので、いつでも始められる

- [ ] T001 [P] テスト `backend/tests/unit/test_change_rules.py` を書く（DB なし）：決まりの関数に、**当てはまる 10 件・当てはまらない 10 件**の記録の並びを渡し、付け間違い・付け忘れが 0 件（SC-002）。
  次を必ず含める：前の日の夜「少し」→ 朝「食べていない」は当てはまる（US1 シナリオ 1）／夜「食事なし」→ 朝「食事なし」は当てはまらない（すきまが 2 食続く）／昼「少し」→ おやつ「食べていない」は当てはまらない（おやつは数えない。US1 シナリオ 3a）／
  機嫌 月「元気がない」・火 未記録・水「元気がない」は当てはまる／機嫌 月「元気がない」・火〜木 未記録・金「元気がない」は当てはまらない（Edge Cases）／取り消した記録は数えない／最新の記録が「ほぼ全部」なら当てはまらない／
  まだ記録のない「これからの枠」はすきまに数えない／7 日より前の記録は読まない／当てはまったときに返す記録の id・日付・枠・値がすきまを含まない（research.md R-02）（みさき）
- [ ] T002 [P] 決まりの関数を `backend/app/services/change_rules.py` に作る（DB に触らない。research.md R-01・R-02）：決まりのコード **`meal_low`（`item = meal`、`slot` が `breakfast`・`lunch`・`dinner`、値 `2`・`0`、2 食）／`mood_low`（`item = mood`、値 `low`、2 日）／`sleep_poor`（`item = sleep`、値 `poor`、2 日）** を定数で持つ。
  入力は 1 人の入居者の記録の並び（取り消していないもの、直近 7 日分）、出力は「当てはまるか・続いた数・当てはまった記録の `{record_id, date, slot, value}` の一覧（古い順）」。
  いちばん新しい記録のある枠からさかのぼり、当てはまる値は数える、**未記録・取り消し・「食事なし（`none`）」はすきま**（当てはまる値として数えない）、すきまが 2 枠続いたら・当てはまらない値が来たらやめる。続いた数が 2 以上で当てはまる。T001 を通す（みさき）
- [ ] T003 変化の検知のテーブルを `backend/app/models/change_flags.py` に作り、マイグレーションを足す（data-model.md）：
  `change_rules`（`code` は **主キー、`meal_low`／`mood_low`／`sleep_poor`**、`enabled` は **boolean、初期値 true**、`updated_at`、`updated_by` → `staff`（初期データは空））、
  `change_rule_histories`（`rule_code` → `change_rules`、`enabled_before`・`enabled_after`、`changed_by` → `staff`、`changed_at`）、
  `change_flags`（`resident_id` → `residents`、`rule_code` → `change_rules`、`started_at`、`cleared_at`（**空なら今の目印**）、`cleared_reason` は **`not_matching`／`rule_disabled`（消えたときだけ）**、`streak`（int）、`evidence`（jsonb、**`[{record_id, date, slot, value}]` 古い順**）、`status` は **`unconfirmed`／`confirmed`／`cleared`**、`updated_at`。**`CHECK ((status = 'cleared') = (cleared_at IS NOT NULL))`**。
  **一意：`(resident_id, rule_code) WHERE cleared_at IS NULL`**（部分インデックス））、
  `change_flag_confirmations`（`change_flag_id` → `change_flags`、`confirmed_by` → `staff`、`confirmed_at`、`note` は **100 文字まで・任意**、`streak_at_confirmation`（int））。マイグレーションを作る直前に main を取り込む（001 の R-17）（みさき）
- [ ] T004 [P] 決まりの初期データを `backend/app/seed/change_rules.py` に作り、001-T015 の `backend/app/seed/__main__.py` から呼ぶ：`change_rules` に 3 行（**すべて `enabled = true`**）。すでにあれば足さない（何度流してもよい）（みさき）

**Checkpoint**: 決まりの関数が単体テストを通り、テーブルと決まりの初期データができている

---

## Phase 3: User Story 1 - 職員がアプリを開くと、いつもと違う様子の入居者に目印が付いている（Priority: P1）🎯 MVP

**Goal**: 記録を保存・押し直し・取り消しすると、同じトランザクションで目印が付く・消える。入居者一覧の上のほうに目印が出て、入居者を開くと当てはまった決まりともとの記録が見える

**Independent Test**: 架空の入居者に、昨日の夜ごはん「少し」・今日の朝ごはん「食べていない」を記録し、職員で入居者一覧を開くと目印が付き、開くと理由が出る（quickstart.md の通しの確認 1〜3）

### Tests for User Story 1

- [ ] T005 [P] [US1] テスト `backend/tests/api/test_change_flags.py` を書く（テスト用の PostgreSQL）：
  記録の保存（`PUT /api/staff/residents/{id}/records`）で当てはまれば目印が付く（`status = unconfirmed`、`evidence` と `streak` が入る）／押し直し・取り消し（001-T034）で当てはまらなくなれば消える（`status = cleared`・`cleared_at`・`cleared_reason = not_matching`）／
  同じ記録で `evaluate_change_flags` を何度呼んでも目印は 1 つ（一意）／**目印がまだない入居者に、2 つのセッションでほぼ同時に記録を保存しても、目印は 1 つで一意制約の違反にならない**（research.md R-03）／2 つの決まりに当てはまると行は 2 つ・`get_flag_summary` の `unconfirmed_resident_count` は 1／
  `GET /api/staff/residents/{id}/change-flags` は介護職員・リーダー・生活相談員・施設長が開け、**事務員・家族は 403**（FR-006）／入居者一覧（`GET /api/staff/residents`）は、**事務員は 403**（spec 001 のまま。FR-006）／
  目印が付いても `notifications`・`email_outbox` の行が増えない（SC-004）／家族の連絡帳・通知のまとめ・spec 001 の共通の関数の返す値に目印が入らない（FR-007・SC-005）／ログに入居者の氏名・記録の値が出ない（FR-014）（みさき）
- [ ] T006 [P] [US1] テスト `frontend/src/components/change-flags/ChangeFlagPanel.test.tsx` を書く（Vitest）：`rule_code`・`evidence` から「食事量：昨日の夜ごはんから 2 食続けて、少し以下」のような文を辞書で組み立てる／案内「気になるときは、看護職員・生活相談員に相談してください。急変は電話で」が出る／
  **辞書の目印まわり（`change.*`）の日本語に、医療の言葉（病気・疑い・診断・症状・脱水 など）が入っていない**（SC-003・research.md R-06）（みさき）

### Implementation for User Story 1

- [ ] T007 [US1] 調べ直しを `backend/app/services/change_detection.py` の `evaluate_change_flags(session, resident_id)` に作る（research.md R-03）：**関数の中では commit しない**。最初に **`residents` のその入居者の行**を `SELECT ... FOR UPDATE` で押さえ（目印がまだなくても同時の調べ直しが順番になる）、
  オンの決まりごとに直近 7 日分の `care_records`（`deleted_at` が空のもの。非開示の項目も含めて直接読む。001 の R-06）を T002 の関数に渡し、今の目印（`cleared_at` が空）と突き合わせる：
  当てはまる・目印なし → 作る（`unconfirmed`）／当てはまる・目印あり → `evidence`・`streak` を上書きし、`confirmed` で `streak` が最後の `streak_at_confirmation` より増えたら `unconfirmed` に戻す（FR-010）／当てはまらない・目印あり → `status = cleared`・`cleared_at`・`cleared_reason = not_matching` を 1 回の更新でまとめて入れる（FR-008）。
  ログは目印の id・決まりのコード・付いた／消えたの別・入居者の id だけ（FR-014）（みさき）
- [ ] T008 [US1] 記録の保存・押し直し（`backend/app/services/records.py`、001-T026）と取り消し（001-T034）の処理のあとに、`evaluate_change_flags(session, resident_id)` を**同じセッションで**呼ぶ（記録と目印が同じトランザクションで確定する。spec 001 の `create_reply_notice` と同じ形。PR #40）（ゆう）
- [ ] T009 [P] [US1] 初期データで記録を入れたあと（001-T030 の `backend/app/seed/records.py` のあと）、入居者全員について `evaluate_change_flags` を呼ぶ処理を `backend/app/seed/change_rules.py` に足す。あわせて、デモ用に目印が付く架空の記録（ある入居者の前の日の夜「少し」・朝「食べていない」）を入れる（みさき）
- [ ] T010 [US1] 入居者一覧に返すものを `backend/app/services/change_detection.py` の `get_flag_summary(session)` に作る：`residents: {resident_id: {has_flag, has_unconfirmed}}`（今の目印がある入居者だけ）と、`unconfirmed_resident_count`（**まだ確かめていない目印がある入居者の人数**。research.md R-04）（data-model.md）（みさき）
- [ ] T011 [US1] 入居者一覧の API（`backend/app/api/staff/residents.py`、001-T028）で `get_flag_summary` を呼び、`residents[].change_flag`（目印がなければ `null`）と `unconfirmed_flag_count` を足す。一覧を開けるのは事務員以外の職員だけ（spec 001）なので、役割で分けない（contracts/api.md）（ゆう）
- [ ] T012 [US1] `GET /api/staff/residents/{id}/change-flags` を `backend/app/api/staff/change_flags.py` に作る（役割：介護職員・リーダー・生活相談員・施設長。`require_staff(roles)`）：`current`（今の目印：`id`・`rule_code`・`started_at`・`streak`・`evidence`・`status`・`confirmations`）と
  `history`（消えた目印：あわせて `cleared_at`・`cleared_reason`。新しい順）を返す。文言は返さずコードで返す。確かめた職員は `display_name` だけ。ない入居者は 404。ルーターを `backend/app/main.py` に登録する（contracts/api.md）（みさき）
- [ ] T013 [US1] 目印の欄 `frontend/src/components/change-flags/ChangeFlagPanel.tsx` を作る：当てはまった決まりともとの記録（日付・項目・区分・値）を辞書で組み立てて表示し、そばに案内「気になるときは、看護職員・生活相談員に相談してください。急変は電話で」を出す（FR-003・FR-004）。
  目印・決まりの名前・案内の日本語を `frontend/src/i18n/ja.json` の `change.*` に足す（医療の言葉を使わない）。T006 を通す（みさき）
- [ ] T014 [P] [US1] 入居者一覧の上の部品 `frontend/src/components/change-flags/UnconfirmedFlagFilter.tsx` を作る：「確かめていない目印：◯件」（`unconfirmed_flag_count`）を出し、押すと目印の付いた入居者だけに絞れる（FR-003）。（みさき）
- [ ] T015 [US1] 入居者一覧（`frontend/src/pages/staff/ResidentList.tsx`、001-T031）に `UnconfirmedFlagFilter` を置き、目印のある入居者の行に「⚠️ いつもと違う様子」を出して上のほうに並べる。記録の画面（`frontend/src/pages/staff/RecordPage.tsx`、001-T032）に `ChangeFlagPanel` を置く（事務員のときは出さない）。
  ほかの表示との並べ方は、ゆうの画面設計で決めたとおりにする（plan の Structure Decision）（ゆう）

**Checkpoint**: 記録すると目印が付き・消え、入居者一覧と入居者の画面で見られる。家族・事務員には出ない。通知・音は出ない

---

## Phase 4: User Story 2 - 職員が目印を確かめ、対応したことを残す（Priority: P2）

**Goal**: 「確かめた」とひとことを残せ、次の勤務の職員が見られる。続いたら確かめ済みから戻る。過去の目印を見返せる

**Independent Test**: 目印の付いた入居者で「確かめた」とひとことを残すと、別の職員でログインしたときに、確かめた職員・日時・ひとことが見える（quickstart.md の通しの確認 4〜7）

### Tests for User Story 2

- [ ] T016 [P] [US2] テスト `backend/tests/api/test_change_flags.py` に足す：`POST /api/staff/residents/{id}/change-flags/confirm` で、その入居者の `unconfirmed` の目印がまとめて `confirmed` になり、目印ごとに `change_flag_confirmations` が 1 行（`note`・`streak_at_confirmation`）できる／
  確かめていない目印がなければ **409 `already_confirmed`**（2 人がほぼ同時に押したときの後の人も）／`note` が **100 文字を超えると 422 `validation_error`**／確かめたあとにさらに続くと `unconfirmed` に戻り、前の確かめた記録は残る（FR-010）／
  事務員・家族は 403／`note` の `<script>` がそのまま文字として返る（FR-013）／ログにひとことが出ない（FR-014）（みさき）

### Implementation for User Story 2

- [ ] T017 [US2] 確かめる処理を `backend/app/services/change_detection.py` に足し、`POST /api/staff/residents/{id}/change-flags/confirm` を `backend/app/api/staff/change_flags.py` に作る（役割：介護職員・リーダー・生活相談員・施設長）：本文 `{note}`（**100 文字まで・任意**）。
  `residents` のその入居者の行、続いてその入居者の今の目印を `FOR UPDATE` で押さえ（T007 と同じ順番）、`unconfirmed` のものを `confirmed` にして、それぞれに `change_flag_confirmations`（`confirmed_by`・`confirmed_at`・`note`・`streak_at_confirmation` ＝そのときの `streak`）を足す。1 つもなければ 409 `already_confirmed`（research.md R-04、contracts/api.md）（みさき）
- [ ] T018 [US2] `ChangeFlagPanel.tsx` に足す：「確かめた」ボタンとひとことの入力（100 文字まで・任意。文字としてだけ表示）、確かめ済みの目印を色を変えて区別し、確かめた職員・日時・ひとことを出す（FR-009・FR-010）。
  `history` を「過去の目印」として、付いた日・消えた日・当てはまった決まり・確かめた職員・ひとことを新しい順に並べる（FR-008）。409 のときは「ほかの職員が確かめました」と出して読み直す。文言を `ja.json` の `change.*` に足す（みさき）

**Checkpoint**: 確かめた記録が引き継げ、続いたら戻り、過去の目印を見返せる

---

## Phase 5: User Story 3 - 施設が、どの変化に目印を付けるかを選ぶ（Priority: P3）

**Goal**: 生活相談員・施設長が、管理画面で決まりをオン／オフでき、変更履歴が残る

**Independent Test**: 管理画面で「眠り」の決まりをオフにすると、眠りの記録が続いても目印が付かない（quickstart.md の「決まりの設定」）

### Tests for User Story 3

- [ ] T019 [P] [US3] テスト `backend/tests/api/test_change_rules_admin.py` を書く：`GET /api/admin/change-rules` は生活相談員・施設長だけで、**介護職員・リーダー・事務員・家族は 403**（FR-011）／オフにすると、その決まりの今の目印が消え（`status = cleared`・`cleared_reason = rule_disabled`）、記録が続いても付かない／
  オンに戻すと全員が調べ直されて目印が付く（research.md R-07）／変更ごとに `change_rule_histories` が 1 行でき、`GET /api/admin/change-rules/history` に新しい順で出る／ない決まりのコードは 404（みさき）

### Implementation for User Story 3

- [ ] T020 [US3] 決まりのオン／オフを `backend/app/services/change_detection.py` に足し、`GET /api/admin/change-rules`・`PUT /api/admin/change-rules/{code}`・`GET /api/admin/change-rules/history` を `backend/app/api/admin/change_rules.py` に作る（役割：生活相談員・施設長）：
  オフにしたら、その決まりの今の目印に `status = cleared`・`cleared_at`・`cleared_reason = rule_disabled` をまとめて入れる。オンにしたら、同じトランザクションで入居者全員について `evaluate_change_flags` を呼ぶ。変更者・日時・前後の値を `change_rule_histories` に残す。ルーターを `backend/app/main.py` に登録する（research.md R-07、contracts/api.md）（みさき）
- [ ] T021 [US3] 設定の画面 `frontend/src/pages/admin/ChangeRules.tsx` を作り、001-T019 の管理画面の枠（生活相談員・施設長だけ）に `/admin/change-rules` として足す：決まり 3 つとオン／オフの切り替え、変更履歴（いつ・誰が・どの決まりを・どう変えたか）。文言を `ja.json` の `change.*` に足す（みさき）

**Checkpoint**: 決まりをオン／オフでき、履歴が残る

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T022 [P] 目印まわり（`change.*`）の日本語にふりがなを付け、インドネシア語・英語の辞書 `frontend/src/i18n/id.json`・`frontend/src/i18n/en.json` に足す（001-T082・001-T083 の仕組み。Constitution の UI 方針。職員のひとことは対象外）（みさき）
- [ ] T023 [P] 問い合わせ AI（spec 004）のツールの返す値に目印が入らないことを、spec 004 のテストに 1 件足す（spec 004 のツールができてから。FR-007・SC-005）（みさき）
- [ ] T024 quickstart.md の確認をすべて通し、`docs/テスト設計書.md` に変化の検知のテストシナリオと結果を書く（Constitution の課題要件のテスト。001-T093 と一緒に）（みさき）

---

## Dependencies & Execution Order

### Phase の順番

- **Setup（Phase 1）**：spec 001 の Phase 1 をそのまま使う
- **Foundational（Phase 2）**：T001・T002 はいつでも始められる（DB なし）。T003・T004 は 001-T009・001-T015・001-T025 のあと
- **US1（Phase 3）**：Foundational のあと。T008・T011・T015 はゆうの 001-T026・001-T028・001-T031・001-T032・001-T034 のあと
- **US2（Phase 4）**：US1 のあと（目印がないと確かめられない）
- **US3（Phase 5）**：Foundational のあと。US1 の T007（`evaluate_change_flags`）を使うので、T007 のあと。US2 とは並べて進められる
- **Polish（Phase 6）**：US1〜US3 のあと。T023 は spec 004 のツールができてから

### spec 001 とのつながり

| spec 006 のタスク | 先に要る spec 001 のタスク |
|---|---|
| T003（テーブル） | 001-T009（共通のテーブル）・001-T025（`care_records`） |
| T004・T009（初期データ） | 001-T015（初期データの仕組み）・001-T030（記録のサンプル） |
| T005・T012・T016〜T020（役割のチェック・エラー） | 001-T010（`CurrentUser`・`require_staff`）・001-T012（エラーの形）・001-T020（テストの土台） |
| T008（記録の保存から呼ぶ） | 001-T026（記録の保存・押し直し）・001-T034（取り消し） |
| T011（入居者一覧の API） | 001-T028（入居者一覧の API） |
| T015（画面に置く） | 001-T031（入居者一覧の画面）・001-T032（記録の画面） |
| T021（設定の画面） | 001-T019（画面の枠） |
| T022（辞書） | 001-T016・001-T082・001-T083（辞書とふりがな） |

### ゆうとのつなぎ目（PR #40 のレビューで決めた形）

- ゆうのタスクは T008・T011・T015 の 3 つ。どれも「みさきの関数・部品を呼ぶ・置く」だけ
- みさきが先に T007（`evaluate_change_flags`）・T010（`get_flag_summary`）・T013・T014（部品）を作り、関数の名前と返す形を共有してから、ゆうが足す

### User Story の中の順番

- テスト → テーブル（Foundational）→ サービス → API → 画面
- T001 のテストを先に書き、T002 で通す。T005 のテストを先に書き、T007〜T012 で通す

---

## Parallel Example

### Foundational

```text
いつでも：T001（テスト）と T002（決まりの関数）を同時に。DB を待たない
001-T025 のあと：T003（テーブル）→ T004（初期データ）
```

### User Story 1

```text
テストを並べて：T005（API）・T006（画面）
バックエンド：T007 → T010 → T012。ゆうは T007 ができたら T008、T010 ができたら T011
画面を並べて：T013・T014（API の形が決まっていれば、T012 と同時に始められる）→ ゆうが T015
```

---

## Implementation Strategy

### 最初に作る範囲（US1）

1. T001・T002（決まりの関数とテスト）。DB がなくても先に作れるので、ほかの作り込みの合間に始める
2. T003〜T004（テーブル・初期データ）→ T005〜T015（目印が付き、一覧と入居者の画面で見られる）
3. quickstart.md の通しの確認 1〜3 で、US1 を単独でデモできる

### そのあと

- US2（T016〜T018）→ US3（T019〜T021）の順。US3 は US2 と並べてもよい
- 仕上げ（Day 5〜6。ふりがな・多言語は Day 5、テストは Day 6）：ふりがなと多言語、AI のテストへの足し、テストシナリオ（T022〜T024）

---

## Notes

- [P] のタスクは別のファイルで、終わっていないタスクに依存しない
- 決まりは記録の値だけで判断し、AI も文（様子のメモなど）も読まない（spec の Clarifications）
- 目印は家族の API・通知・問い合わせ AI に出さない。事務員にも見せない（FR-006・FR-007）
- 目印が付いても、職員のタブレットに通知・音・画面を遮る表示を出さない（FR-005）
- ログには目印の id・決まりのコード・付いた／消えたの別だけを出し、入居者の氏名・記録の値・ひとことは出さない（FR-014）
- plan の「未決定のこと」（食事なしの扱い・件数の数え方・確かめる単位・オフにしたときの目印）がレビューで変わったら、関係するタスク（T001・T002・T010・T017・T020）を直す
- 1 PR は 1,100 行以内（`specs/` とロックファイルは数えない）。超えそうなら issue とブランチを分ける
