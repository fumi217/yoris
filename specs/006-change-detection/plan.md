# Implementation Plan: 記録から入居者のいつもと違う様子に気づき、職員に知らせる（E：変化の検知）

**Branch**: `docs/spec-006-plan` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-change-detection/spec.md`

## Summary

連絡帳の記録（食事量・機嫌・眠り）が保存・押し直し・取り消しされるたびに、その入居者が決まり（例：食事量が 2 食続けて「少し」以下）に当てはまるかを調べ直し、
当てはまれば職員の入居者一覧に「⚠️ いつもと違う様子」の目印を付け、当てはまらなくなれば消す。職員は入居者を開いて、当てはまった決まりともとになった記録を見て、
「確かめた」とひとことを残せる。生活相談員・施設長は、決まりをオン／オフできる。全体が作り込み（Day 5・10/28。docs/マイルストーン.md）の範囲。

土台は [spec 001 の plan](../001-family-priority-report/plan.md) と同じ（FastAPI ＋ SQLAlchemy ＋ PostgreSQL、React（Vite）、ログインと役割、記録のテーブル `care_records`）。
設計の柱は次の 3 つ（詳しくは [research.md](./research.md)）。

1. **決まりは「記録の値だけで決まる関数」にする**：AI を使わず、記録の並びを受け取って「当てはまるか・どの記録が当てはまったか」を返す純粋な関数にする。
   同じ記録からはいつも同じ結果になり、spec の例（当てはまる 10 件・当てはまらない 10 件）をそのまま単体テストにできる（R-01・R-02）
2. **記録の保存と同じトランザクションで調べ直す**：ゆうの記録の保存・押し直し・取り消しの処理から `evaluate_change_flags(session, resident_id)` を呼び、関数の中では commit しない。
   記録だけ保存されて目印がずれる、ということが起きない。調べ直しは「今の記録から当てはまる状態を作り直して、今の目印と突き合わせる」形にし、何度呼んでも同じ結果になる（R-03）
3. **職員向けだけの道にする**：目印は家族の API・通知・問い合わせ AI の道（spec 001 の共通の関数）を通らない別のテーブルに置き、家族向けのどこからも読まない。
   職員でも事務員は職員の画面を開けないので、目印も見えない（R-05）

## Technical Context

**Language/Version**: Python 3.13（バックエンド）、TypeScript 6・Node 24（フロントエンド）。spec 001 の plan と同じ（技術選定 7 章）

**Primary Dependencies**: spec 001 の plan と同じ（FastAPI、SQLAlchemy 2、Alembic、Pydantic 2、structlog、React（Vite）、React Router、TanStack Query、react-i18next、Tailwind CSS）。
**新しいライブラリは足さない**

**Storage**:
- PostgreSQL：変化の決まり・決まりの変更履歴・変化の目印・確かめた記録（[data-model.md](./data-model.md)）。記録は spec 001 の `care_records` を直接読む（spec 001 R-06 の「職員向けは直接読んでよい」）
- Redis：使わない（目印はキャッシュしない。記録を保存したときに DB で作り直すため、古い目印が残る心配がない）

**Testing**: pytest（決まりの関数の単体テスト＝SC-002 の 20 件、調べ直し・役割・家族に出ないことの API テスト）、Vitest（目印の表示・絞り込み）、Playwright（[quickstart.md](./quickstart.md) の通しの確認）

**Target Platform**: spec 001 の plan と同じ（Docker Compose、Render。職員は施設のタブレットのブラウザ） （10/28 の会議で決定：今回の開発ではデプロイしないので、Render の部分は作らない）

**Project Type**: Web アプリケーション（`frontend/` と `backend/` を分ける）

**Performance Goals**:
- 決まりに当てはまる記録が保存されてから、入居者一覧を開き直したときに目印が出るまで 1 分以内（SC-001。実際は保存と同時に目印ができる）
- 1 回の調べ直しは、1 人の入居者の直近 7 日分の記録（最大 7 日 × 5 件）を読むだけ。記録の保存の応答を目立って遅くしない
- 目印の付いた入居者を開いてから、何がいつから当てはまっているかを 10 秒以内に把握できる（SC-006）

**Constraints**:
- 目印の文に医療の判断・助言を入れない。画面には決まりのコードと記録の値のコードだけを返し、文言は辞書から引く（SC-003・FR-004）
- 職員のタブレットに通知・音・画面を遮る表示を出さない（SC-004・FR-005）
- 家族の画面・通知・問い合わせ AI のどこにも目印を出さない（SC-005・FR-007）
- 事務員・家族には目印を見せない（FR-006）
- ログに入居者の氏名・記録の値・ひとことを出さない（FR-014）
- 「続けて」の判断と日付は日本時間（spec 001 R-14）

**Scale/Scope**: 施設 1 つ、入居者最大 30 人、決まり 3 つ。画面は、職員の入居者一覧への足し（ゆう）、入居者を開いた画面の目印の欄、管理画面の「変化の目印」の設定の 3 か所

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 の前

| 原則・制約 | 確認 | 結果 |
|---|---|---|
| I. 家族が電話も遠慮もせずに知れる | 家族が直接使う機能ではない。施設が変化に早く気づき、必要なときは人が電話する（家族への見え方は変えない） | ✅（家族の体験を変えない） |
| II. 職員の入力負担を増やさない | 目印は記録から自動で付き、職員の入力は増えない。「確かめた」はワンタップ、ひとことは任意（100 文字）。通知・音は出さず、入居者一覧を開いたときに見える | ✅ |
| III. AI は医療判断をしない | AI を使わない。決まりは記録の値だけで判断し、目印の文は記録の事実だけ。そばに「看護職員・生活相談員に相談」と案内する（急変・事故の電話の案内は、様子のメモを書く画面に出す。spec 007） | ✅ |
| IV. 開示は施設が選ぶ・家族は自分の入居者だけ | 目印は家族に出さない。職員向けなので非開示の項目（例：眠り）も含めて調べる（家族に出さないので原則 IV に反しない。spec 001 R-06） | ✅ |
| V. 10 日間で動くものを優先 | 全体が作り込み。新しいライブラリを足さず、spec 001 の記録・入居者一覧・役割のチェックを使い回す | ✅ |
| UI 方針 | 決まりの名前・目印・案内は辞書から引き、ふりがなは spec 001 の R-11 の書き方。職員のひとことはふりがな・翻訳の対象外 | ✅ |
| 利用者と権限 | 目印を見る・確かめる：介護職員・リーダー・生活相談員・施設長。決まりのオン／オフ：生活相談員・施設長。事務員・家族は不可（`require_staff(roles)` で確かめる） | ✅ |
| 個人情報 | 架空の入居者・記録だけを使う。ログに氏名・記録の値・ひとことを出さない | ✅ |
| 課題要件：構成・コンテナ・キャッシュ | spec 001 と同じ構成。この spec では新しいキャッシュを作らない（目印は保存のたびに DB で作り直す） | ✅ |
| 課題要件：セキュリティ | ひとことは文字としてだけ出す（React の通常の表示）。SQL は ORM でパラメータ化 | ✅ |
| 課題要件：テスト・ログ | pytest・Vitest・Playwright。ログには目印の id・決まりのコード・付いた／消えたの別だけ | ✅ |

**違反なし**。Complexity Tracking は空。

### Phase 1 のあと（設計後の確認）

| 確認したこと | 結果 |
|---|---|
| 決まりの判断は記録の値だけを使う純粋な関数で、AI も文も読まない（[research.md R-01・R-02](./research.md)） | ✅ |
| 調べ直しは記録の保存と同じトランザクションで、関数の中で commit しない（[research.md R-03](./research.md)） | ✅ |
| 目印のテーブルは spec 001 の共通の関数（家族に出す道）から読まれず、家族の API・通知・AI のツールに目印を返すものがない（[contracts/api.md](./contracts/api.md)） | ✅ |
| 事務員は入居者一覧（職員の画面）を開けない（spec 001 の contracts。[contracts/api.md](./contracts/api.md#職員の入居者一覧ゆうの-api-に足す)） | ✅ |
| API は文言を返さずコードで返し、目印の文に医療の言葉が入らない（[research.md R-06](./research.md)） | ✅ |
| 新しいライブラリは増えていない | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/006-change-detection/
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

spec 001 の plan の構成に、変化の検知の分を足す（ほとんどみさき。記録の保存と入居者一覧に足す部分だけゆう）。

```text
backend/
├── app/
│   ├── models/change_flags.py           # change_rules・change_rule_histories・change_flags・change_flag_confirmations
│   ├── services/
│   │   ├── change_rules.py              # 決まりの関数（記録の並び → 当てはまるか・どの記録か）。DB に触らない
│   │   ├── change_detection.py          # evaluate_change_flags(session, resident_id)、get_flag_summary(session)、確かめる処理、決まりのオン／オフ
│   │   └── records.py                   # （spec 001・ゆう）保存・押し直し・取り消しのあとに evaluate_change_flags を呼ぶ
│   ├── api/
│   │   ├── staff/change_flags.py        # 入居者の目印と履歴、「確かめた」
│   │   ├── staff/residents.py           # （spec 001・ゆう）入居者一覧に目印と件数を足す
│   │   └── admin/change_rules.py        # 決まりの一覧・オン／オフ・変更履歴
│   └── seed/change_rules.py             # 決まり 3 つ（すべてオン）と、目印が付くデモ用の架空の記録
├── alembic/versions/                    # 変化の検知の 4 テーブル
└── tests/
    ├── unit/test_change_rules.py        # 決まりの関数（SC-002 の 20 件）
    └── api/test_change_flags.py         # 調べ直し・確かめる・役割・家族に出ない・事務員は 403

frontend/
└── src/
    ├── components/change-flags/
    │   ├── ChangeFlagPanel.tsx          # 入居者を開いた画面の目印の欄（当てはまった決まり・もとの記録・確かめた・履歴）
    │   └── UnconfirmedFlagFilter.tsx    # 入居者一覧の「気をつけたい人」の見出しの横の「確かめていない目印：◯件」と絞り込み
    ├── pages/staff/ResidentList.tsx     # （spec 001・ゆう）目印と上の部品を置く
    ├── pages/staff/RecordPage.tsx       # （spec 001・ゆう）ChangeFlagPanel を置く
    └── pages/admin/ChangeRules.tsx      # 「変化の目印」の設定（オン／オフ・変更履歴）
```

**Structure Decision**: 変化の検知はみさきがまとめて持つ（spec の Assumptions、PR #40 のレビュー）。ゆうのファイルに足すのは次の 3 か所だけで、どれも「みさきの関数・部品を呼ぶ・置く」だけにする。
1. 記録の保存・押し直し（`services/records.py`、001-T026）と取り消し（001-T034）：処理のあとに `evaluate_change_flags(session, resident_id)` を同じセッションで呼ぶ（spec 001 の `create_reply_notice` と同じ形）
2. 入居者一覧の API（`api/staff/residents.py`、001-T028）：`get_flag_summary(session)` を呼び、目印と件数を足す（一覧を開けるのは事務員以外の職員だけ。spec 001）
3. 入居者一覧（`ResidentList.tsx`、001-T031）と記録の画面（`RecordPage.tsx`、001-T032）：`UnconfirmedFlagFilter`・`ChangeFlagPanel` を置き、一覧の行に目印を出す。並べ方と置き場所は、ゆうが画面設計を作るときにまとめて決める

## 担当とつながり

| 担当 | この spec で作るもの | ほかの人から使うもの |
|---|---|---|
| みさき | 4 つのテーブル、決まりの関数、`evaluate_change_flags`・`get_flag_summary`・確かめる処理、職員と管理画面の API、目印の部品 2 つ、設定の画面、初期データ、テスト | ようこ：`CurrentUser`・`require_staff(roles)`。ゆう：`care_records`・記録の保存の処理・入居者一覧 |
| ゆう | 記録の保存・押し直し・取り消しから `evaluate_change_flags` を呼ぶ、入居者一覧の API に目印と件数を足す、一覧と記録の画面にみさきの部品を置く | みさき：`evaluate_change_flags`・`get_flag_summary`・部品 2 つ |
| みさき | 決まりの名前・目印・案内の辞書（日本語のふりがな・インドネシア語・英語） | — |

## 作る順番（すべて作り込み）

| 順 | 内容 | spec |
|---|---|---|
| 1 | 決まりの関数と単体テスト（SC-002 の 20 件）。DB なしで先に作れる | US1・FR-002 |
| 2 | 4 つのテーブル、`evaluate_change_flags`、決まりの初期データ。ゆうに記録の保存から呼んでもらう | US1・FR-001・FR-008 |
| 3 | 入居者の目印の API と `ChangeFlagPanel`（当てはまった決まり・もとの記録・案内）、`get_flag_summary` とゆうの入居者一覧への足し | US1・FR-003〜007 |
| 4 | 「確かめた」とひとこと、確かめ済みの表示、続いたときに戻す、過去の目印 | US2・FR-008〜010 |
| 5 | 決まりのオン／オフと変更履歴の画面 | US3・FR-011・FR-012 |

## 未決定のこと（plan では仮に置いた）

| 項目 | 仮に置いた内容 | 決める場 |
|---|---|---|
| 「食事なし」の扱い | 当てはまる値として数えず、未記録と同じ「すきま」として扱う（1 食までなら飛ばす。R-02） | この PR のレビュー |
| 「確かめていない目印：◯件」の数え方 | 入居者の人数で数える（1 人に決まりが 2 つ当てはまっても 1 件。spec の US2 シナリオ 1a） | この PR のレビュー |
| 「確かめた」の単位 | 入居者ごとに 1 回押すと、その入居者の確かめていない目印がまとめて確かめ済みになる（spec の Edge Cases「目印は 1 つにまとめる」） | この PR のレビュー |
| 決まりをオフにしたときの今の目印 | 消す（消えた理由を「決まりをオフにした」として履歴に残す）。オンに戻したら、全員を調べ直す（R-07） | この PR のレビュー |
| 入居者一覧での目印の並べ方・置き場所 | 一覧の上のほうに出す（spec の FR-003）。ほかの表示（未記録・返事待ち・メッセージ・承認待ち）との並べ方は、ゆうの画面設計で決める | ゆうの画面設計 |

## Complexity Tracking

> Constitution Check に違反はないため、記入なし。
