# API Contract: spec 003（面会予約）

フロントエンドとバックエンドの間の API の一覧と決まりごと。共通の決まり（先頭は `/api`、Cookie のセッション、書き込みは `X-Requested-With: fetch`、
エラーの形 `{ "error": { "code", "message_key" } }`、文言はコードで返して画面で辞書から引く、日付は `YYYY-MM-DD`（日本時間）・日時は ISO 8601（UTC））は、
[spec 001 の contracts/api.md](../../001-family-priority-report/contracts/api.md) と同じ。正式な定義は FastAPI が出す OpenAPI とする。

- **家族の API では、入居者を指定させない**。ログイン中の家族の `CurrentUser.resident_id` から決める（[research.md R-05](../research.md#r-05-家族の予約の入居者とほかの家族の予約)）。
- id で予約を指定する家族の API は、自分の入居者の予約でなければ **404**。
- 担当はすべてゆう。お知らせ（作り込み）を作る関数はさとこ（[research.md R-07](../research.md#r-07-お知らせ予約確定施設からの取り消し前日-20-時)）。

### 役割の略号

`F` 家族、`CW` 介護職員、`L` リーダー、`CO` 生活相談員、`CL` 事務員、`D` 施設長、`職員` は CW・L・CO・CL・D のすべて

### エラー（spec 001 の一覧に足すもの）

| HTTP | code | いつ | spec |
|---|---|---|---|
| 403 | `forbidden` | 家族のロールで職員・管理画面の API を呼んだ（spec 001 と同じ。家族に管理画面を見せないのは画面の側で守る） | FR-011 |
| 404 | `not_found` | ほかの家族の予約を指定した（存在するかどうかも知らせない。コードは 001-T012 でようこが足す） | FR-015 |
| 409 | `visit_overlap` | 面会の時間が、その日のほかの予約と重なった | FR-003 |
| 409 | `visit_day_full` | その日の予約が、1 日に受け付ける組数に達した | FR-003 |
| 409 | `visit_already_booked_day` | 同じ家族が、その日にすでに予約している | FR-008 |
| 409 | `visit_deadline_passed` | 前日の 17 時を過ぎて、予約・取り消しをしようとした | FR-007・FR-008 |
| 409 | `visit_closed_day` | 休みの日を予約しようとした | FR-010 |
| 409 | `visit_day_has_reservations` | 予約が入っている日を、確認なしで休みにしようとした（件数を返す） | FR-010 |
| 422 | `visit_out_of_range` | 予約できる期間（翌日から 4 週間先まで）の外 | FR-008 |
| 422 | `validation_error` | 開始時刻が候補にない、人数が 1 未満、職員の取り消しで理由がない、など | FR-002・FR-012 |

## 家族（ゆう）

| メソッド・パス | 役割 | 中身 | 時期 | spec |
|---|---|---|---|---|
| `GET /api/family/visits/availability?from=&to=` | F | 日付ごとに、開始時刻の候補と `selectable`（選べる／選べない）。その家族がその日に予約していれば `mine: true`。ほかの家族の情報や、選べない理由は返さない（[research.md R-03](../research.md#r-03-選べるかどうかの計算)） | ミニマム版 | FR-001・FR-004 |
| `POST /api/family/visits` | F | 予約する（`visit_date`・`start_time`・`party_size`）。入居者は送らない。409：`visit_overlap`・`visit_day_full`・`visit_already_booked_day`・`visit_deadline_passed`・`visit_closed_day`、422：`visit_out_of_range` | ミニマム版 | FR-002・FR-003・FR-005・FR-008 |
| `GET /api/family/visits` | F | 自分のこれからの予約（日時・人数・状態。職員が取り消したときは理由も） | 作り込み | FR-006 |
| `DELETE /api/family/visits/{id}` | F | 自分の予約を取り消す。前日 17 時を過ぎたら 409 `visit_deadline_passed`。ほかの家族の予約は 404 | 作り込み | FR-007・FR-015 |

```json
// GET /api/family/visits/availability?from=2026-10-26&to=2026-10-30 の返り値（例）
{
  "days": [
    {
      "date": "2026-10-26",
      "closed": false,
      "mine": false,
      "start_times": [
        { "start_time": "10:00", "selectable": false },
        { "start_time": "10:30", "selectable": false },
        { "start_time": "13:00", "selectable": true }
      ]
    }
  ]
}
```

## 職員の画面・管理画面（ゆう）

| メソッド・パス | 役割 | 中身 | 時期 | spec |
|---|---|---|---|---|
| `GET /api/staff/visits/today` | 職員 | 今日の面会予定（時刻・入居者名・人数）。今日（日本時間）の予約済みだけを時刻の順に。形は下の予約の一覧と同じ | 作り込み | FR-011 |
| `GET /api/admin/visits?from=&to=` | 職員 | 予約の一覧（日付・時刻・入居者名・人数・予約した日時・状態）。`[{id, visit_date, start_time, resident_id, resident_name, room, party_size, status, created_at, cancel_reason}]`。取り消したものも状態つきで返す。期間は 31 日まで | 作り込み | FR-011 |
| `POST /api/admin/visits/{id}/cancel` | 職員 | 予約を取り消す（`reason` は必須）。締め切りなし。作り込みで、さとこの `create_visit_notice(session, id, "visit_cancelled")` を同じトランザクションで呼ぶ | 作り込み | FR-012・FR-013 |
| `GET /api/admin/visit-settings` | CL・CO・D | 開始時刻の候補と、1 日に受け付ける組数。`{daily_limit, start_times}`（今の候補を早い順に） | 作り込み | FR-009 |
| `PUT /api/admin/visit-settings` | CL・CO・D | 変える（本文は GET と同じ形）。候補は 30 分刻み・10:00 から・開始時刻＋1 時間 30 分が 17:00 まで、組数は 1 以上、候補は 1 つ以上（ほかは 422。何も変えない）。外した候補は `active = false` にするだけで、すでに入っている予約はそのまま | 作り込み | FR-009 |
| `GET /api/admin/visit-closed-days?from=&to=` | CL・CO・D | 休みの日の一覧 | 作り込み | FR-010 |
| `POST /api/admin/visit-closed-days` | CL・CO・D | 休みにする（`date`）。今日より前は 422、もう休みならそのまま返す（201。`{id, closed_date, cancelled}`）。予約があれば 409 `visit_day_has_reservations`（`details.count` に件数）。理由は 200 文字まで。予約と同じ、その日だけの順番待ちの中で行う。`confirm_cancel: true` と `reason` を付けると、その日の予約を職員の取り消しにしてから休みにする（[research.md R-08](../research.md#r-08-休みの日を予約が入っている日に設定するとき)） | 作り込み | FR-010 |
| `DELETE /api/admin/visit-closed-days/{id}` | CL・CO・D | 休みを取り消す（204。休みにするときに取り消した予約は戻さない） | 作り込み | FR-010 |

## お知らせ（さとこ・作り込み）

API ではないが、ゆうの処理から呼ぶ関数と、送るメールを決めておく（spec 001 の通知の仕組みを使う）。

| いつ | だれが呼ぶ | 関数・処理 | メールの件名の例 | テンプレートに渡すもの |
|---|---|---|---|---|
| 予約が確定したとき | ゆう（`book_visit` の中） | `create_visit_notice(session, reservation_id, "visit_confirmed")` | 面会の予約が確定しました | 日時・リンクだけ |
| 職員が取り消したとき | ゆう（取り消しの処理の中） | `create_visit_notice(session, reservation_id, "visit_cancelled")` | 面会の予約が取り消されました | 日時・リンクだけ（理由は渡さない） |
| 前日の 20 時 | さとこ（`run_jobs()`。20:00 を過ぎて最初に呼ばれたとき） | 翌日の `booked` を探して `visit_reminder` を作る（同じ予約に 1 回だけ） | 明日は面会の予定があります（本文に「変更・取り消しは、施設にお電話ください」） | 日時・リンクだけ |

- どれも、家族の通知の頻度の設定には関係なく送り、家族が設定でオフにすることもできない（FR-013）。家族が自分で取り消したときは送らない。
- 日時をメールに渡すため、spec 001 の research.md R-09（テンプレートに渡すもの）に「日時」を足す（さとこ。PR #18）。
- 関数の中では commit しない（spec 001 の `create_reply_notice` と同じ）。
