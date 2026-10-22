# Implementation Plan: 家族がアプリから面会を予約する（G）

**Branch**: `docs/spec-003-visit-reservation` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-visit-reservation/spec.md`

## Summary

家族が、アプリで面会の空いている時間を見て予約・取り消しをできるようにし、施設は開始時刻の候補・休みの日を設定し、予約の一覧を見て
必要なら取り消す。家族は 30 分刻みの開始時刻から選び、予約が入るとその時刻から 1 時間 30 分に重なるほかの開始時刻は選べなくなる。
施設全体で 1 日 2 組まで、1 家族 1 日 1 回まで、予約・取り消しは前日 17 時まで、予約できるのは翌日から 4 週間先まで。

土台は [spec 001 の plan](../001-family-priority-report/plan.md) と同じ（FastAPI ＋ SQLAlchemy ＋ PostgreSQL、React（Vite）、ログインと役割、
お知らせとメールの送り方）。この spec の設計の柱は次の 2 つ（詳しくは [research.md](./research.md)）。

1. **同時に予約されても、DB で守る**：重なりと 1 家族 1 日 1 回は DB の決まり（排他制約・部分インデックス）、
   1 日 2 組は「その日だけの順番待ち」をしてから数える。予約を作る道は `book_visit` の 1 つだけ。Redis のロックは使わない
2. **家族には、自分の予約と「選べるかどうか」だけを返す**：入居者はログイン中の家族から決め、ほかの家族の予約は 404。選べない理由も返さない

## Technical Context

**Language/Version**: Python 3.13（バックエンド）、TypeScript 6・Node 24（フロントエンド）。spec 001 の plan と同じ

**Primary Dependencies**: spec 001 の plan と同じ（FastAPI、SQLAlchemy 2、Alembic、Pydantic 2、React（Vite）、React Router、TanStack Query、react-i18next、Tailwind CSS）。
新しいライブラリは足さない。PostgreSQL の `btree_gist` 拡張（最初から入っている）を使う（[research.md R-01](./research.md#r-01-同時に予約されても重なり1-日-2-組1-家族-1-日-1-回を守る)）

**Storage**:
- PostgreSQL：面会の設定・開始時刻の候補・休みの日・予約（[data-model.md](./data-model.md)）
- Redis：この spec では使わない（同時の予約は DB で守る。開発前MTG の決定事項）

**Testing**: pytest（テスト用の PostgreSQL。同時の予約はスレッドで同時に送って確かめる）、Vitest（予約の画面）、Playwright（[quickstart.md](./quickstart.md) の通しの確認）

**Target Platform**: spec 001 の plan と同じ（Docker Compose、Render。家族はスマートフォン、職員はタブレットのブラウザ）

**Project Type**: Web アプリケーション（`frontend/` と `backend/` を分ける）

**Performance Goals**:
- 家族が予約の画面を開いてから確定するまで 1 分以内・5 タップ以内（SC-001）
- 職員が取り消してから、家族にお知らせとメールが 5 分以内に届く（SC-003。`run_jobs()` が 1 分ごとに送る。spec 001 R-09）

**Constraints**:
- 面会の時間が重なる予約・1 日 3 組目の予約が、同時に予約されても 1 件も確定しない（SC-002）
- 家族はほかの家族の予約を見られず、取り消せない（SC-004）
- メールに入居者名・取り消しの理由を入れない（FR-014）
- 「前日 17 時」「翌日から 4 週間」「前日 20 時」は日本時間で数える

**Scale/Scope**: 施設 1 つ、家族アカウント 30、1 日 2 組まで（4 週間で最大 56 件程度）。
画面は家族向け 2（予約・自分の予約）、職員向け 1（今日の面会予定）、管理画面 2（予約の一覧、開始時刻の候補と休みの日）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 の前

| 原則・制約 | 確認 | 結果 |
|---|---|---|
| I. 家族が電話も遠慮もせずに知れる | 面会の日時の調整を、電話なしでアプリだけで行える（SC-005）。締め切りを過ぎたら電話の案内を出す | ✅ |
| II. 職員の入力負担を増やさない | 家族の予約は施設の承認を待たずに確定し、職員の入力は増えない。職員が入力するのは、取り消すときの理由だけ。開始時刻の候補は初期データで用意する | ✅ |
| III. AI は医療判断をしない | この spec では AI を使わない。AI（F）から予約する機能は扱わない | ✅（対象外） |
| IV. 開示は施設が選ぶ・家族は自分の入居者だけ | 家族は自分の入居者の予約だけを見て取り消せる。入居者はログイン中の家族から決め、ほかの家族の予約は 404（FR-015、R-05） | ✅ |
| V. 10 日間で動くものを優先 | ミニマム版は User Story 1 だけ。作り込みは US2〜US4。新しいライブラリは足さない | ✅ |
| UI 方針 | 固定の文言は辞書から引き、ふりがなは spec 001 の R-11 の書き方。ミニマム版は日本語だけ | ✅ |
| 利用者と権限 | 予約は家族、一覧と取り消しは職員のすべて、設定は事務員・相談員・施設長（R-06）。`require_staff(roles)` で確かめる | ✅ |
| 個人情報 | 架空データだけ。メールに入居者名・理由を入れない（FR-014） | ✅ |
| 課題要件：構成・コンテナ・キャッシュ | spec 001 と同じ構成。この spec では Redis を使わない（キャッシュの要件は spec 001 のセッションと開示設定のキャッシュで満たす） | ✅ |
| 課題要件：セキュリティ | 取り消しの理由は文字としてだけ出す（FR-016）。SQL は ORM でパラメータ化。家族の API に入居者の欄を作らない | ✅ |
| 課題要件：テスト・ログ | pytest・Vitest・Playwright。ログに入居者名・理由を出さず id だけを出す | ✅ |

**違反なし**。Complexity Tracking は空。

### Phase 1 のあと（設計後の確認）

| 確認したこと | 結果 |
|---|---|
| 予約を作る道が `book_visit` の 1 つだけで、その日だけの順番待ち・件数・同じ家族・重なりを確かめてから追加する（[research.md R-01](./research.md#r-01-同時に予約されても重なり1-日-2-組1-家族-1-日-1-回を守る)） | ✅ |
| 重なりと 1 家族 1 日 1 回は、DB の決まり（排他制約・部分インデックス）でも守る（[data-model.md](./data-model.md#visit_reservations)） | ✅ |
| 家族の API は入居者を受け取らず、選べない理由やほかの家族の情報を返さない（[contracts/api.md](./contracts/api.md#家族ゆう)） | ✅ |
| 職員・管理画面の API に、家族のロールでは入れない。役割は R-06 の表のとおり | ✅ |
| お知らせのテンプレートに、入居者名・取り消しの理由を渡さない（[contracts/api.md](./contracts/api.md#お知らせさとこ作り込み)） | ✅ |
| 新しいライブラリは増えていない | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/003-visit-reservation/
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

spec 001 の plan の構成に、面会予約の分を足す（すべてゆう）。

```text
backend/
├── app/
│   ├── models/visits.py            # visit_settings・visit_start_times・visit_closed_days・visit_reservations
│   ├── services/visits.py          # book_visit（予約を作る唯一の道）、取り消し、選べるかどうかの計算
│   ├── api/
│   │   ├── family/visits.py        # 家族の予約・自分の予約・取り消し
│   │   ├── staff/visits.py         # 今日の面会予定
│   │   └── admin/visits.py         # 予約の一覧・職員の取り消し・開始時刻の候補・休みの日
│   └── seed/visits.py              # 面会の設定・開始時刻の候補 8 つ・デモ用の予約
├── alembic/versions/               # btree_gist 拡張と、面会予約のテーブル
└── tests/
    ├── unit/test_visit_rules.py    # 締め切り・期間・重なりの判定
    └── api/test_visits.py          # 同時の予約、ほかの家族の予約は 404、役割

frontend/
└── src/pages/
    ├── family/visits/              # 面会の予約・自分の予約（家族の画面の中に、面会予約だけのフォルダを分ける）
    ├── staff/TodayVisits.tsx       # 今日の面会予定
    └── admin/
        ├── VisitReservations.tsx   # 予約の一覧・取り消し
        └── VisitSettings.tsx       # 開始時刻の候補・1 日の組数・休みの日
```

**Structure Decision**: 家族の画面はさとこの担当だが、G は家族の予約画面も含めてゆうが作る（spec の Assumptions）。
同じファイルを同時に触らないよう、家族の画面の中に `family/visits/` のフォルダを分ける。家族の画面の枠（メニュー・ルーティング）に
「面会の予約」へのリンクを足すところだけ、ようこ（001-T019 の担当）と相談する。

## 担当とつながり

| 担当 | この spec で作るもの | ほかの人から使うもの |
|---|---|---|
| ゆう | 面会予約のテーブル・初期データ、`book_visit`、家族の予約の API と画面、職員の取り消し・予約の一覧・今日の予定、開始時刻の候補と休みの日の設定 | ようこ：`CurrentUser`（`resident_id`）・`require_staff(roles)`・共通のテーブル（施設・入居者・家族アカウント・職員）。みさき：辞書と `Ruby` |
| さとこ | `create_visit_notice(session, reservation_id, kind)`、`notifications` に `visit_reservation_id` と種類を足す、メールのテンプレート 3 つ、`run_jobs()` の前日 20 時の知らせ（作り込み） | ゆう：`visit_reservations` |

## ミニマム版と作り込み

| | ミニマム版（Day 1〜3） | 作り込み（Day 4〜） |
|---|---|---|
| ゆう | `visit_settings`・`visit_start_times`・`visit_reservations`（決まりを含む）、初期データ、`book_visit`、選べるかどうかの計算、`GET /api/family/visits/availability`・`POST /api/family/visits`、家族の予約の画面（User Story 1） | 自分の予約と取り消し（US2）、休みの日・開始時刻の候補の設定・予約の一覧・今日の面会予定（US3）、職員の取り消し（US4） |
| さとこ | なし | 面会のお知らせ 3 種類と、前日 20 時の知らせ（US4） |

ミニマム版では、予約が確定したことは画面の表示だけで、お知らせ・メールは送らない（[research.md R-07](./research.md#r-07-お知らせ予約確定施設からの取り消し前日-20-時)）。

## 未決定のこと（plan では仮に置いた）

| 項目 | 仮に置いた内容 | 決める場 |
|---|---|---|
| （決定）家族の画面の枠に「面会の予約」を足すところ | 家族の画面のメニューは、下に「連絡帳・知りたいこと・お知らせ」の 3 つ、そのほかは「☰ その他」にまとめる（spec 001 の Clarifications、PR #29）。「面会」は「☰ その他」の中に足し、`/family/visits` のルートを足す。枠（001-T019）はようこが、メニューを足しやすい形で作る | 決定済み |
| （決定）家族のロールで管理画面の API を開いたとき | **403 `forbidden`**（spec 001 の「役割がない＝403」にそろえる。PR #18 ようこ）。家族に管理画面を見せないのは、画面の側（001-T019 のルーティング）で守る。404 で存在を隠すのは、id で指定するデータ（ほかの家族の予約など）だけ | 決定済み |
| 予約の一覧を、介護職員が管理画面で見る形 | 職員のすべてが開けるようにした（Clarifications）。介護職員の画面からのリンクの置き方は、作り込みで決める | ゆう |

## Complexity Tracking

> Constitution Check に違反はないため、記入なし。
