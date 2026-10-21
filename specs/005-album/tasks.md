---

description: "spec 005（アルバム）のタスク一覧"
---

# Tasks: 家族が入居者の写真を見られるアルバム（H）

**Input**: `specs/005-album/` の [spec.md](./spec.md)・[plan.md](./plan.md)・[research.md](./research.md)・[data-model.md](./data-model.md)・[contracts/api.md](./contracts/api.md)・[quickstart.md](./quickstart.md)

**Tests**: テストのタスクを含める（Constitution の課題要件「単体テストはテストコードを書く」、research.md R-08）。各 User Story で、テストを先に書いて失敗することを確かめてから作る。

**Organization**: User Story ごとにまとめる。各タスクの末尾に **（担当）** を書く。この spec は **すべて作り込み（Day 4〜8）** で、ミニマム版（Day 1〜3）には入れない（Clarifications）。
タスク番号はこの spec の中の番号。spec 001 のタスクは **001-T069** のように書いて区別する。
issue は担当者が、ここから自分のタスクを選んで立てる（1 issue は 1 PR で 1,100 行以内に収まる量。`.claude/skills/github-workflow/SKILL.md`）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: ほかのタスクと並べて進められる（別のファイルで、終わっていないタスクに依存しない）
- **[Story]**: どの User Story のタスクか（US1〜US4）。Foundational・Polish には付けない
- パスは plan.md の構成（`backend/app/`・`frontend/src/`）に合わせる

---

## Phase 1: Setup

**Purpose**: この spec で足す土台はない。spec 001 の Phase 1（001-T001〜001-T007：Docker Compose・バックエンドとフロントのひな形・Alembic・lint・ログ・`env.example`）をそのまま使う

---

## Phase 2: Foundational（アルバムの全 User Story の前に必要なもの）

**Purpose**: アルバムのテーブル、写真の処理、家族に出す共通の関数、開示設定の「アルバム」

**⚠️ CRITICAL**: spec 001 の 001-T009（共通のテーブル）・001-T010（`CurrentUser` と役割のチェック）・001-T012（エラーの形）・001-T015（初期データの仕組み）・001-T036（開示設定のテーブル）・001-T038（`disclosure.py`）・001-T068（`uploaded_files`）・001-T069（`uploads.py`）・001-T075（Exif の削除）のあとに始める

- [ ] T001 アルバムのテーブルを `backend/app/models/album.py` に作り、マイグレーションを足す（data-model.md）。`album_photos`：`resident_id`（→ `residents`）、`file_id`・`thumb_file_id`（→ `uploaded_files`、削除したら空にする）、
  `comment` は **`varchar(100)`、任意（空でよい）、削除したら空にする**、`posted_by`（→ `staff`）、`posted_at`、`deleted_by`・`deleted_at`。索引は `(resident_id, posted_at DESC, id DESC)`。
  `uploaded_files.purpose` に `album` を足す（元の写真もサムネイルも `album`）（FR-023・FR-012）（さとこ）
- [ ] T002 [P] 写真の処理を `backend/app/services/uploads.py` に足す（001-T069・001-T075 のあと）：呼び出し側が受け付ける形式を渡せるようにし、アルバムでは **`image/jpeg`・`image/png` だけ**にする（PDF は `invalid_file`）。
  画像を Pillow で開いたら、`ImageOps.exif_transpose` で向きを実際の画素に反映してから、Exif を付けずに保存する。サムネイル（**長い辺 480px の JPEG、画質 80**）を作って別の `uploaded_files` に保存する。
  画素数が極端に大きい画像は `Image.MAX_IMAGE_PIXELS` で、アニメーション PNG・壊れた画像と一緒に `invalid_file` にする。1 枚は **10MB まで**（research.md R-02。FR-003・FR-004）（さとこ）
- [ ] T003 [P] 開示設定に「アルバム」を足す（**ゆうに依頼**。001-T036・001-T038 のあと）：`disclosure_settings.target_type` に `feature` を足し、初期データに `(facility_id, 'feature', 'album', visible = true)` の 1 行を入れる（`backend/app/seed/`）。
  `backend/app/services/disclosure.py` に `is_feature_disclosed(code)` を足す（開示設定のキャッシュを読む。`get_disclosed_records` や通知の項目の選択肢に `feature` の行が混ざらないようにする）（FR-013・research.md R-04）（ゆう）
- [ ] T004 家族に出す共通の関数を `backend/app/services/album.py` に作る：`get_visible_album_photos(resident_id, before=None, limit=30)`（アルバムが「見せる」のとき、その入居者の削除されていない写真を新しい順に返す。「見せない」のときは呼び出し側が 404 にする）、
  `can_family_view_photo(photo, resident_id)`（自分の入居者の写真・削除されていない・アルバムが「見せる」）、`count_new_photos(resident_id, since, until)`（削除されていない写真の数）。家族に写真を出す道は、これらの関数だけにする（T003 のあと。research.md R-03。FR-006・FR-014）（さとこ）
- [ ] T005 [P] テスト用の架空の画像を作る補助を `backend/tests/helpers/images.py` に作る：位置情報（Exif）の入った JPG、縦向きの JPG、PNG、名前だけ `.jpg` の PDF、10MB を超える画像を、テストの中で作る（実在の人物の写真は使わない。research.md R-08）（さとこ）

**Checkpoint**: マイグレーションが通り、サムネイルつきで写真を保存でき、開示設定の「アルバム」（見せる）が入っている

---

## Phase 3: User Story 1 - 職員が写真を撮って載せ、家族が見る（Priority: P1）🎯

**Goal**: 職員が入居者を選んで写真を載せ（コメントは任意）、その入居者の家族だけが「☰ その他」→「アルバム」で日ごとの一覧を見て、タップで大きく見られる。ほかの入居者の家族・ログインしていない人には見えない

**Independent Test**: quickstart.md の 1〜10（職員が載せる → 家族 A が見る → 家族 B には見えない・URL を直接開いても 404 → ログインなしは 401）

### Tests for User Story 1（先に書いて、失敗することを確かめる）⚠️

- [ ] T006 [P] [US1] 単体テスト `backend/tests/unit/test_album_visibility.py`：`can_family_view_photo`（自分の入居者の写真は見える、ほかの入居者の写真・削除された写真・アルバムを見せない設定は見えない）、`get_visible_album_photos`（新しい順、30 枚で切る、`before` で続きを読む）（さとこ）
- [ ] T007 [P] [US1] API テスト `backend/tests/api/test_album.py`（載せる）：職員が 1 枚載せられる／**コメントなしで載る**／コメントが **100 文字**までは載り、101 文字は 422 `validation_error`／JPG・PNG 以外（PDF、名前だけ JPG の PDF）と 10MB 超は 422 `invalid_file`／
  保存した写真に **Exif が残っていない**／縦向きの画像の向きが保たれる／家族のロールで載せる API を呼ぶと 403（FR-001・FR-003・FR-004・FR-023）（さとこ）
- [ ] T008 [P] [US1] API テスト `backend/tests/api/test_album.py`（見る）：家族 A が自分の入居者の写真を日ごとに見られる／**家族 B が家族 A の入居者の写真を一覧でも、ファイルの URL（`/api/files/{id}`）でも見られず 404**／ログインなしは 401／写真が 0 枚のときは空の配列（FR-005〜008）（さとこ）

### Implementation for User Story 1

- [ ] T009 [US1] 職員の API を `backend/app/api/staff/album.py` に作る：`POST /api/staff/residents/{id}/album`（`multipart/form-data`、写真 **1 枚**＋任意の `comment`。T002 の処理を通して保存し、`album_photos` に足す。載せた職員と日時を残す）、
  `GET /api/staff/residents/{id}/album`（削除されていない写真の一覧と、`family_visible`）。役割：職員のすべて（CW・L・CO・CL・D）。422：`invalid_file`・`validation_error`（FR-001・FR-002）（さとこ）
- [ ] T010 [US1] 家族の API を `backend/app/api/family/album.py` に作る：`GET /api/family/album?before=&limit=`（`get_visible_album_photos` を通す。載せた日（日本時間）ごとにまとめ、1 回で最大 30 枚、`next_before` で続きを読む。アルバムを見せない設定のときは 404）、
  `GET /api/family/features`（`{ "album": true }`。開示設定の `feature` の状態だけ）。入居者は送らせず、ログイン中の家族から決める（FR-005・FR-006・FR-010）（T004 のあと）（さとこ）
- [ ] T011 [US1] `GET /api/files/{id}` に、アルバムの写真の条件を `backend/app/api/files.py` に足す（001-T071 のあと）：職員は削除されていないものを開ける。家族は `can_family_view_photo` が真のときだけ開ける。それ以外は 404、ログインなしは 401。`Content-Type` は保存した形式に固定し、`X-Content-Type-Options: nosniff` を付ける（FR-006・FR-007・FR-022）（さとこ）
- [ ] T012 [US1] 家族のアルバムの画面を `frontend/src/pages/family/Album.tsx` に作る：載せた日ごとにサムネイルを並べ、タップで元の写真を大きく出す。コメントは**文字としてのみ**写真の下に出す（辞書を通さず、HTML として解釈しない）。「もっと見る」で続きを読む。写真がないときは「まだ写真はありません」。
  固定の文言は辞書（`frontend/src/i18n/ja.json`）から引き、ふりがなは spec 001 の R-11 の書き方にする（FR-005・FR-008・FR-021・FR-022）（さとこ）
- [ ] T013 [US1] 家族の画面の枠に、「☰ その他」の中の「アルバム」のリンクと `/family/album` のルートを足す（`frontend/src/pages/family/` の枠。001-T019 のあと）。`GET /api/family/features` が `album: false` のときは出さない。spec 003 の面会の置き方と同じ形にする（FR-010）（さとこ）
- [ ] T014 [US1] 職員の「写真を載せる」画面を `frontend/src/pages/staff/AlbumUpload.tsx` に作る：「📷 撮る」（`<input type="file" accept="image/jpeg,image/png" capture="environment">`）と「🖼 写真から選ぶ」（複数枚・**10 枚まで**）を置き、選んだ写真にプレビューと、
  写真ごとの一言コメント欄（**任意・100 文字まで**）を出す。**1 枚ずつ**順に送り（T009）、成功・失敗を表示し、失敗した写真だけ「もう一度送る」を出す。10MB を超える写真は送る前に断る。文章の入力を求めない（research.md R-01。FR-001・FR-023・SC-001）（さとこ）
- [ ] T015 [US1] 職員の入居者の画面（`frontend/src/pages/staff/RecordPage.tsx`、001-T032）の上に「📷 写真を載せる」のボタンを足す。同じファイルを 2 人で触らないよう、**ボタンはゆうが足す**（載せる画面 T014 はさとこが作り、ボタンからつなぐ）。
  #38（D の「様子のメモを書く」）のボタンも同じ場所に並べる予定なので、みさきと合わせる。入居者を選んでから 4 タップ以内で載せ終われるようにする（SC-001）（ゆう）
- [ ] T016 [US1] アルバムの固定の文言を `frontend/src/i18n/ja.json`（ふりがな付き）に足す。`id.json`・`en.json` も足す（日本語以外ではふりがなを付けない。001 の R-11）（さとこ）

**Checkpoint**: 職員が載せた写真が、その入居者の家族のアルバムだけに出る。ほかの入居者の家族・ログインなしでは開けない

---

## Phase 4: User Story 2 - 職員が載せた写真を削除する（Priority: P2）

**Goal**: 職員が、載せた写真を削除でき、家族の画面からもファイルの URL からも消える。保存先のファイルも消える。誰がいつ削除したかが残る

**Independent Test**: quickstart.md の 11〜14（削除 → 家族の画面から消える → URL を直接開くと 404 → 家族のロールでは削除できない）

### Tests for User Story 2 ⚠️

- [ ] T017 [P] [US2] API テスト `backend/tests/api/test_album.py`（削除）：職員（各役割）が削除できる／削除後、家族の一覧から消え、ファイルの URL（元・サムネイル）が 404／**保存先のファイルが消えている**／`album_photos` に `deleted_by`・`deleted_at` が残り、`file_id`・`thumb_file_id`・`comment` が空／
  家族のロールで削除の API を呼ぶと 403／削除済みの写真をもう一度削除しても壊れない（FR-011・FR-012）（さとこ）

### Implementation for User Story 2

- [ ] T018 [US2] 削除の処理を `backend/app/services/album.py` に足す：1 つのトランザクションで `deleted_by`・`deleted_at` を入れ、`file_id`・`thumb_file_id`・`comment` を空にして `uploaded_files` の 2 行を消す。**そのあとで**保存先のファイル 2 つを消す。消せなかったときは、`storage_key` の id をログに出す（ファイル名・コメントは出さない）（research.md R-05）（さとこ）
- [ ] T019 [US2] `DELETE /api/staff/album/{id}` を `backend/app/api/staff/album.py` に足す（役割：職員のすべて。家族のロールは 403）（FR-011）（さとこ）
- [ ] T020 [US2] 載せた写真の一覧と削除のボタンを `frontend/src/pages/staff/AlbumUpload.tsx` に足す（削除の前に確認を出す）。アルバムを家族に見せていないとき（`family_visible = false`）は、「いま家族には見せていません」を出す（FR-011・FR-016）（さとこ）

**Checkpoint**: 削除した写真は、画面からも URL からも見えず、保存先のファイルも消える

---

## Phase 5: User Story 3 - 施設がアルバムを家族に見せるかどうかを選ぶ（Priority: P3）

**Goal**: 生活相談員・施設長が、開示設定の画面でアルバムを「見せる」「見せない」に切り替えられる。「見せない」ときは、メニュー・URL・通知のどこにも出ない。変更の履歴が残る

**Independent Test**: quickstart.md の 15〜19（見せない → メニューから消える・URL を直接開くと 404 → 職員は載せられる → 見せるに戻すとそのまま見られる）

### Tests for User Story 3 ⚠️

- [ ] T021 [P] [US3] API テスト `backend/tests/api/test_album.py`（開示）：「見せない」にすると家族の一覧・ファイルが 404 になり、`GET /api/family/features` が `album: false`／職員は載せられ、`family_visible = false`／「見せる」に戻すと前に載せた写真が見られる／介護職員のロールで開示設定の API を呼ぶと 403／変更が `disclosure_setting_histories` に残る（FR-013〜016）（さとこ）

### Implementation for User Story 3

- [ ] T022 [US3] 開示設定の API が `feature` の行（アルバム）を扱えるようにする（**ゆうに依頼**。001-T039 のあと）：`GET /api/admin/disclosure` の返り値に `feature` の行を足し、`PUT /api/admin/disclosure` で変えられるようにする。保存したら開示設定のキャッシュを必ず消す。
  変更は `disclosure_setting_histories`（誰が・いつ・何を）に残る。役割：生活相談員・施設長（FR-013・FR-015）（ゆう）
- [ ] T023 [US3] 開示設定の画面に「アルバム」の行（見せる／見せない）を足す（**ゆうに依頼**。001-T040 のあと）：`frontend/src/pages/admin/DisclosureSettings.tsx`。履歴の画面にも出る（FR-013・FR-015）（ゆう）
- [ ] T024 [US3] 「見せない」設定のときの動きを確かめる・直す：メニュー（T013）、アルバムの API（T010）、ファイル（T011）、通知の選択肢（T028）のどれにも出ない。開示設定を保存した直後に、古いキャッシュで出ないことをテストで確かめる（FR-014）（さとこ）

**Checkpoint**: 「見せない」にすると、家族の画面・URL・通知のどこにもアルバムが出ない

---

## Phase 6: User Story 4 - 新しい写真が載ったことを家族に知らせる（Priority: P4）

**Goal**: 新しい写真が載ると、家族が選んだ頻度のまとめ（毎日 20 時／毎週日曜 20 時）に「アルバムに新しい写真が載りました」が入る。載せるたびにはすぐ知らせない。通知とメールに、写真・ファイル名・コメント・入居者名を入れない

**Independent Test**: quickstart.md の 20〜25（3 枚載せる → まだ届かない → 20 時のまとめを手で動かす → 1 通だけ届く → 2 回動かしても増えない → 削除した写真はまとめに入らない）

### Tests for User Story 4 ⚠️

- [ ] T025 [P] [US4] テスト `backend/tests/api/test_digest.py`（アルバム）：写真が載った日のまとめに `has_album = true` が入り、**3 枚載せても知らせは 1 回**／同じ時刻で 2 回動かしても 1 回だけ／削除した写真は入らない／記録も写真も 0 件の日は送らない／
  頻度が「通知しない」・`notify_album = false`・アルバムを見せない設定のときは写真の分が入らない／20 時より後に載せた写真は次のまとめに入る／メールとお知らせに、写真・ファイル名・コメント・入居者名がない（FR-017〜019・SC-007）（さとこ）

### Implementation for User Story 4

- [ ] T026 [US4] `notifications` に `has_album`（boolean、初期値 `false`）を、`notification_settings` に `notify_album`（boolean、初期値 `true`）を足し、マイグレーションを足す（`backend/app/models/notifications.py`。001-T048・001-T064 のあと。data-model.md）（さとこ）
- [ ] T027 [US4] まとめにアルバムを足す（`backend/app/jobs/digest.py`。001-T065 のあと）：記録のまとめを作るとき、`count_new_photos(resident_id, 前回のまとめのあと, 今回の 20:00)` が 1 以上で、`notify_album` が真で、アルバムが「見せる」なら、`has_album = true` にする。
  記録も写真も 0 件なら送らない。同じまとめを 2 回送らない仕組み（`digest_runs`）はそのまま使う。文面は辞書から引く：記録だけ・写真だけ・両方の 3 通り。テンプレートに渡すのは `has_album` とリンクだけ（research.md R-06。FR-018・FR-019）（さとこ）
- [ ] T028 [US4] 通知設定の API と画面に「アルバムの新しい写真」を足す（`GET/PUT /api/family/notification-settings` の `notify_album`、`frontend/src/pages/family/` の通知設定の画面。アルバムを見せない設定のときは項目を出さない）（FR-017）（さとこ）
- [ ] T029 [US4] お知らせ一覧の画面で、まとめの `has_album` を文言に反映する（`frontend/src/pages/family/` のお知らせ一覧。辞書から引く）（FR-018）（さとこ）

**Checkpoint**: 写真を載せると、次のまとめに 1 回だけ入り、メールに中身が入らない

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T030 [P] 家族の画面の単体テスト `frontend/tests/unit/Album.test.tsx`（Vitest）：日ごとに並ぶ、写真がないとき「まだ写真はありません」、コメントが文字としてのみ出る（`<script>` を入れても実行されない）（さとこ）
- [ ] T031 [P] 職員の画面の単体テスト `frontend/tests/unit/AlbumUpload.test.tsx`（Vitest）：10 枚まで選べる、コメントが 100 文字を超えると送れない、失敗した写真だけ「もう一度送る」が出る、10MB を超える写真は送る前に断る（さとこ）
- [ ] T032 デモ用の架空の写真を `backend/app/seed/album.py` に作り、初期データに足す（顔の写っていない風景や物の画像を数枚。実在の人物の写真は使わない）（さとこ）
- [ ] T033 E2E テストを `frontend/tests/e2e/album.spec.ts` に Playwright で作る：quickstart.md の 1〜14 の通しの確認（職員が載せる → 家族 A が見る → 家族 B には見えない → 削除する）（ようこの E2E の土台に足す）（さとこ）
- [ ] T034 quickstart.md の確認をすべて通し、`docs/テスト設計書.md` にアルバムの結合・総合テストのシナリオと結果を書く（Constitution の課題要件のテスト）（さとこ）
- [ ] T035 [P] ログを確かめる：アルバムの処理が、ファイル名・コメント・入居者名をログに出さず、写真・入居者・職員の id と結果だけを出していることを、コードとテストで確かめる（research.md R-09）（さとこ）

---

## Dependencies & Execution Order

### Phase の順番

- Phase 1（Setup）→ Phase 2（Foundational：T001〜T005）→ User Story（Phase 3〜6）→ Phase 7（Polish）
- User Story は、US1 → US2 → US3 → US4 の順に作る（US2 以降は US1 の T004・T009〜T011 のあと）

### User Story のつながり

| User Story | 先に必要なもの |
|---|---|
| US1（載せる・見る） | Phase 2 すべて、spec 001 の 001-T019（家族の画面の枠）・001-T071（`GET /api/files/{id}`） |
| US2（削除） | US1 の T004・T009〜T011 |
| US3（開示設定） | T003（ゆう）、US1。T022・T023 は spec 001 の 001-T039・001-T040（開示設定の API と画面）のあと |
| US4（通知） | US1。spec 001 の 001-T048（`notifications`・`email_outbox`）・001-T057（worker）・001-T064・001-T065（通知設定とまとめ） |

### 人をまたぐつなぎ目（先に形を合わせる）

| つなぎ目 | 渡す人 → 受ける人 | タスク |
|---|---|---|
| 開示設定の `feature`（`is_feature_disclosed`、`feature` の行の API と画面） | ゆう → さとこ | T003・T022・T023 → T004・T010・T024 |
| 職員の画面の「写真を載せる」ボタン（`RecordPage.tsx` に足す） | ゆう → さとこ（ボタンから、さとこの載せる画面につなぐ） | T015 → T014 |
| ファイルの共通の処理（`uploads.py`、`GET /api/files/{id}`） | さとこ → さとこ | 001-T069・001-T071 → T002・T011 |
| まとめ（`digest.py`、`notification_settings`） | さとこ → さとこ | 001-T064・001-T065 → T026・T027 |

**ゆうに頼むのは、T003・T022・T023（開示設定に「アルバム」の行を足す小さな変更）と、T015（記録の画面に「📷 写真を載せる」のボタンを足す）の 4 つだけ**。ほかはすべてさとこが作る。

### User Story の中の順番

テスト → テーブル・処理 → API → 画面 の順。T002・T003・T005 は並べて進められる（別のファイル）。

## Parallel Example

### Phase 2（Day 4）

- T001（`models/album.py`）、T002（`uploads.py`）、T003（`disclosure.py`・ゆう）、T005（`tests/helpers/images.py`）は並べて進められる。T004 は T001・T003 のあと

### User Story 1（Day 4〜5）

- T006・T007・T008（テスト）は並べて書ける
- T009（職員の API）と T012（家族の画面）は、T004 のあとなら並べて作れる

### 作り込み（Day 5〜8）

- US2（T017〜T020）と US3 のゆうの作業（T022・T023）は並べて進められる

## Implementation Strategy

### ミニマム版（Day 1〜3）

この spec は入れない。

### 作り込み（Day 4〜8）

1. Phase 2（T001〜T005）：テーブル・写真の処理・開示設定の「アルバム」・共通の関数
2. US1（T006〜T016）：載せる・見る。**ここまでで、デモ（SC-008）ができる**
3. US2（T017〜T020）：削除（載せてしまった写真をすぐ取り下げられる、安全のために US1 のすぐあとに作る）
4. US3（T021〜T024）：開示設定
5. US4（T025〜T029）：通知（なくても写真は見られるので、最後に作る）

### 仕上げ（Day 9〜10）

- Phase 7（T030〜T035）：テスト、デモ用の写真、通しの確認

## Notes

- 全体で 35 タスク。担当は、T003・T015・T022・T023（ゆう）以外はさとこ。
- 写真は要配慮個人情報として扱う。公開 URL を持たず、ログインと役割を確かめて返す。デモ・開発・テストでは架空の写真だけを使う。
- 1 つのタスクを終えるたびに、quickstart.md の該当する行で動きを確かめる。
