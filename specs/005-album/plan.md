# Implementation Plan: 家族が入居者の写真を見られるアルバム（H）

**Branch**: `docs/spec-005-album` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-album/spec.md`

## Summary

職員が日中の合間にタブレットで入居者の写真を撮って（または選んで）載せ、その入居者の家族だけがアプリの「☰ その他」→「アルバム」から見られるようにする。
写真には任意の一言コメント（100 文字まで）を付けられる。職員は載せた写真を削除できる。施設は開示設定でアルバムを家族に見せる・見せないを選べる。
新しい写真は、記録のお知らせと同じ「まとめ」（毎日 20 時／毎週日曜 20 時）に入れて家族に知らせる。全体が作り込み（Day 4〜8）の範囲。

土台は [spec 001 の plan](../001-family-priority-report/plan.md) と同じ（FastAPI ＋ SQLAlchemy ＋ PostgreSQL、React（Vite）、ログインと役割、
ファイルの保存と配り方、お知らせとメールの送り方、開示設定）。新しい仕組みはほとんど作らず、spec 001 の仕組みを使い回す。
設計の柱は次の 3 つ（詳しくは [research.md](./research.md)）。

1. **ファイルは spec 001 の `uploaded_files` と `services/uploads.py` を使う**：形式の確認・Exif の削除・保存・配り方は共通。
   アルバムで足すのは、写真の向きの直し（`exif_transpose`）と一覧用の小さい画像（サムネイル）だけ。ライブラリは増やさない
2. **家族に出す道は 1 つだけ**：家族の写真の一覧も、写真のファイルを返す API も、「自分の入居者の写真か・削除されていないか・アルバムが開示されているか」を
   同じ関数 `get_visible_album_photos` で確かめる。URL を直接開いても同じ結果になる
3. **通知は新しい仕組みを作らず、まとめに 1 行足す**：`digest.py` が作る「今日のまとめ」に、載せた写真の有無を足す。通知の頻度の設定にそのまま従い、
   まとめる記録も写真も 1 件もない日は送らない

## Technical Context

**Language/Version**: Python 3.13（バックエンド）、TypeScript 6・Node 24（フロントエンド）。spec 001 の plan と同じ

**Primary Dependencies**: spec 001 の plan と同じ（FastAPI、SQLAlchemy 2、Alembic、Pydantic 2、Pillow、React（Vite）、React Router、TanStack Query、react-i18next、Tailwind CSS）。
**新しいライブラリは足さない**（Pillow は spec 001 の R-10 で入る予定）

**Storage**:
- PostgreSQL：アルバムの写真（[data-model.md](./data-model.md)）。ファイルそのものは spec 001 の `uploaded_files` と保存先（開発はボリューム、本番は S3 互換）
- Redis：開示設定のキャッシュ（spec 001 R-12）を読むだけ。この spec では新しいキャッシュを作らない

**Testing**: pytest（アクセス制御・Exif の削除・形式の偽装・削除・まとめ）、Vitest（載せる画面・アルバムの画面）、Playwright（[quickstart.md](./quickstart.md) の通しの確認）

**Target Platform**: spec 001 の plan と同じ（Docker Compose、Render。家族はスマートフォン、職員はタブレットのブラウザ）

**Project Type**: Web アプリケーション（`frontend/` と `backend/` を分ける）

**Performance Goals**:
- 職員が入居者を選んでから 1 枚載せ終わるまで 30 秒以内・4 タップ以内（SC-001）
- 家族が「☰ その他」→「アルバム」を開くまで 2 タップ以内（SC-002）
- 載せた写真・削除した写真が、家族の画面に 5 分以内に反映される（FR-009・FR-012。実際は載せた・消した直後に反映される）

**Constraints**:
- ほかの入居者の家族に写真が見えない・開けない。ログインしていなければファイルを開けない（SC-003）
- JPG・PNG 以外、10MB 超は載せられず、保存した写真に Exif が残らない（SC-004）
- 削除した写真は、画面からも URL からも見えず、保存先のファイルも消える（SC-005）
- 通知とメールに、写真・ファイル名・コメント・入居者名を入れない（SC-007）
- 日付のくくり（「載せた日ごと」）とまとめの時刻は日本時間（spec 001 R-14）

**Scale/Scope**: 施設 1 つ、入居者最大 30 人。写真は 1 日に数十枚程度。
画面は家族向け 1（アルバム）、職員向け 1（写真を載せる・載せた写真を見て削除する）、管理画面は既存の開示設定に 1 行足すだけ

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 の前

| 原則・制約 | 確認 | 結果 |
|---|---|---|
| I. 家族が電話も遠慮もせずに知れる | 文字では伝わらない様子や行事を、写真で見られる。聞かなくても見られる | ✅ |
| II. 職員の入力負担を増やさない | 撮って載せるだけ。一言コメントは任意（自由記述は任意の書き足しに限る）。4 タップ以内・30 秒以内を目標にする（SC-001）。記録 1 項目の 3 タップ・10 秒より長いのは、撮影が入るため | ✅ |
| III. AI は医療判断をしない | この spec では AI を使わない。AI（F）は写真を参照しない | ✅（対象外） |
| IV. 開示は施設が選ぶ・家族は自分の入居者だけ | 開示設定にアルバムを加える（施設全体で一括）。見せない設定のとき、メニュー・URL・通知のいずれにも出さない。家族は自分の入居者の写真だけ（R-03） | ✅ |
| V. 10 日間で動くものを優先 | 全体が作り込み。spec 001 の仕組み（ファイル・開示設定・まとめ）を使い回し、新しいライブラリを足さない | ✅ |
| UI 方針 | 固定の文言は辞書から引き、ふりがなは spec 001 の R-11 の書き方。職員のコメントは翻訳・ふりがなの対象外 | ✅ |
| 利用者と権限 | 載せる・削除は介護職員・リーダー・生活相談員・施設長（事務員は含めない）、開示設定の変更は相談員・施設長、見るのは家族（自分の入居者のみ）。`require_staff(roles)` で確かめる | ✅ |
| 個人情報 | 写真は要配慮個人情報として扱う。公開 URL を持たず、ログインと役割を確かめて返す。通信は https。架空の写真だけを使う。ログにファイル名・コメントを出さない | ✅ |
| 課題要件：構成・コンテナ・キャッシュ | spec 001 と同じ構成。開示設定のキャッシュ（R-12）を使い、アルバムを見せない設定にしたら古いキャッシュで出ないよう、保存時にキャッシュを消す（spec 001 T039 と同じ） | ✅ |
| 課題要件：セキュリティ | コメントは文字としてだけ出す。形式は先頭のバイトで確かめ、`nosniff` で返す。SQL は ORM でパラメータ化 | ✅ |
| 課題要件：テスト・ログ | pytest・Vitest・Playwright。ログには id だけを出す | ✅ |

**違反なし**。Complexity Tracking は空。

### Phase 1 のあと（設計後の確認）

| 確認したこと | 結果 |
|---|---|
| 家族に写真を出す道が `get_visible_album_photos` の 1 つで、一覧もファイルの配信もこれを通る（[research.md R-03](./research.md#r-03-家族に出す道は-1-つだけ)） | ✅ |
| 家族の API は入居者を受け取らず、ほかの入居者の写真・存在は 404 で隠す（[contracts/api.md](./contracts/api.md#家族)） | ✅ |
| 開示設定の「アルバム」は、`target_type = 'feature'` として別に持ち、記録項目の通知の選択肢（`notify_items`）に混ざらない（[data-model.md](./data-model.md#disclosure_settings既存に足す)） | ✅ |
| 通知の文面・メールに、写真・ファイル名・コメント・入居者名を渡さない（[research.md R-06](./research.md#r-06-新しい写真の通知まとめに足す)） | ✅ |
| 削除は、家族の画面から外す→保存先のファイルを消す、の順で、消えた写真が URL から開けない（[research.md R-05](./research.md#r-05-写真の削除)） | ✅ |
| 新しいライブラリは増えていない | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/005-album/
├── spec.md              # 仕様（/speckit-specify・clarify）
├── plan.md              # この文書
├── research.md          # 調べて決めたこと（Phase 0）
├── data-model.md        # テーブルの形・状態の動き（Phase 1）
├── quickstart.md        # 通しの確認手順（Phase 1）
├── contracts/
│   └── api.md           # API の一覧と決まりごと（Phase 1）
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks で作る（この plan では作らない）
```

### Source Code (repository root)

spec 001 の plan の構成に、アルバムの分を足す（すべてさとこ。開示設定に足す部分だけゆう）。

```text
backend/
├── app/
│   ├── models/album.py              # album_photos
│   ├── services/
│   │   ├── album.py                 # 写真を載せる・削除する、get_visible_album_photos（家族に出す唯一の道）
│   │   ├── uploads.py               # （spec 001）写真の向きの直しとサムネイルを足す
│   │   ├── disclosure.py            # （spec 001・ゆう）feature の開示設定を読む関数を足す
│   │   └── notifications.py         # （spec 001）まとめに「写真あり」を足す
│   ├── api/
│   │   ├── family/album.py          # 家族のアルバムの一覧
│   │   ├── staff/album.py           # 写真を載せる・載せた写真の一覧・削除
│   │   └── files.py                 # （spec 001）アルバムの写真を返す条件を足す
│   ├── jobs/digest.py               # （spec 001）まとめに写真を足す
│   └── seed/album.py                # 開示設定の「アルバム」（見せる）と、デモ用の架空の写真
├── alembic/versions/                # album_photos、uploaded_files・notifications・notification_settings に列を足す
└── tests/
    ├── unit/test_album_visibility.py
    └── api/test_album.py            # 他の入居者の写真は 404、Exif、形式の偽装、削除、まとめ

frontend/
└── src/pages/
    ├── family/Album.tsx             # アルバム（日ごとの一覧・タップで大きく）
    ├── staff/AlbumUpload.tsx        # 写真を載せる（撮る／選ぶ・コメント）と、載せた写真の一覧・削除
    └── admin/DisclosureSettings.tsx # （spec 001・ゆう）「アルバム」の行を足す
```

**Structure Decision**: アルバムの作りはさとこがまとめて持つ（spec の Assumptions）。同じファイルを同時に触るのは次の 3 か所だけで、足す量は小さい。
1. 開示設定（ゆう）：`disclosure.py` に `is_feature_disclosed(code)` を足し、設定の画面に「アルバム」の行を足す。ゆうに頼む（下の「担当とつながり」）
2. 職員の画面（ゆう）：入居者を選んだあとの記録の画面（`RecordPage.tsx`）に「📷 写真を載せる」のボタンを足す。ボタンはゆうが足し、さとこの載せる画面につなぐ
3. 家族の画面の枠（さとこ）：「☰ その他」の中にアルバムへのリンクを足す。spec 003 の面会と同じ置き方

## 担当とつながり

| 担当 | この spec で作るもの | ほかの人から使うもの |
|---|---|---|
| さとこ | `album_photos`、`services/album.py`、家族・職員のアルバムの API と画面、`uploads.py` への足し、`files.py` への足し、まとめ（`digest.py`・`notification_settings`）への足し | ようこ：`CurrentUser`・`require_staff(roles)`・共通のテーブル。ゆう：開示設定（`disclosure.py`・設定の画面） |
| ゆう | `disclosure.py` に `is_feature_disclosed(code)` を足す、開示設定の画面と API に `feature`（アルバム）の行を足す、初期データ | — |
| ゆう | 職員の記録の画面（`RecordPage.tsx`）に「📷 写真を載せる」のボタンを足す（T015）。#38 のボタンと並べるため、みさきと合わせる | さとこ：載せる画面（T014） |

## 作る順番（すべて作り込み）

| 順 | 内容 | spec |
|---|---|---|
| 1 | `album_photos`・`uploads.py` の足し（サムネイル・向き）・`files.py` の足し・`get_visible_album_photos` | US1・FR-003〜007 |
| 2 | 職員の API と画面（載せる、載せた写真の一覧）、家族の API と画面、「☰ その他」への置き | US1・FR-001・FR-005・FR-010・FR-023 |
| 3 | 削除（API・画面・保存先のファイルを消す） | US2・FR-011・FR-012 |
| 4 | 開示設定に「アルバム」を足す（ゆうと相談）、見せない設定のときの動き | US3・FR-013〜016 |
| 5 | まとめに写真を足す（`notification_settings`・`digest.py`） | US4・FR-017〜019 |

## 未決定のこと（plan では仮に置いた）

| 項目 | 仮に置いた内容 | 決める場 |
|---|---|---|
| 開示設定の `feature` の行を足すのを、ゆうと相談する | `target_type = 'feature'`、`target_code = 'album'`。`GET/PUT /api/admin/disclosure` が `feature` を扱えるようにする。ゆうに頼む | #37 のレビュー（ゆう） |
| （決定）職員の画面のボタンの置き方 | 記録の画面（`RecordPage.tsx`）の上に「📷 写真を載せる」のボタンを 1 つ置く。ボタンはゆうが足す（PR #39 ゆう）。#38 のボタンと並べるため、みさきと合わせる | 決定済み |
| サムネイルの大きさ | 長い辺 480px（JPEG）。表示の速さを見て、実装のときに変えてよい | 実装のとき |

## Complexity Tracking

> Constitution Check に違反はないため、記入なし。
