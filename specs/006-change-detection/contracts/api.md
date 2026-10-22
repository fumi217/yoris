# API Contract: spec 006（E：変化の検知）

spec 001 の [contracts/api.md](../../001-family-priority-report/contracts/api.md) の「共通の決まり」（先頭は `/api`、書き込みは `X-Requested-With: fetch`、エラーの形、文言はコードで返す）に従う。
ここでは、変化の検知で足す API と、ゆうの入居者一覧に足す項目だけを書く。役割の略号（`CW` 介護職員、`L` リーダー、`CO` 生活相談員、`CL` 事務員、`D` 施設長、`F` 家族）も spec 001 と同じ。
時期はすべて `作`（作り込み）。

## 使うエラー

spec 001 の表にあるもの（`forbidden`・`not_found`・`validation_error`）は同じコードを使い、1 つだけ足す。

| HTTP | code | いつ | spec |
|---|---|---|---|
| 403 | `forbidden` | 役割がない（事務員・家族が目印や決まりの API を呼んだ、など） | FR-006・FR-011 |
| 404 | `not_found` | ない入居者・ない決まりを指定した | |
| 409 | `already_confirmed` | 確かめていない目印がない（ほかの職員が先に確かめた、など） | FR-009・Edge Cases |
| 422 | `validation_error` | ひとことが 100 文字を超える | FR-009 |

## 職員の入居者一覧（ゆうの API に足す）

`GET /api/staff/residents?date=`（spec 001、001-T028）の応答に、次の項目を足す。ゆうが、みさきの `get_flag_summary(session)` を呼んで入れる（[data-model.md](../data-model.md#入居者一覧に返すものget_flag_summary-の形)）。

| 足す項目 | 中身 | spec |
|---|---|---|
| `residents[].change_flag` | `{ "has_flag": true, "has_unconfirmed": true }`。今の目印がない入居者は `null` | FR-003 |
| `unconfirmed_flag_count` | まだ確かめていない目印がある入居者の人数 | FR-003・US2 シナリオ 1a |

- 入居者一覧を開けるのは、spec 001 のとおり `CW`・`L`・`CO`・`D` だけ（事務員 `CL` は 403）。そのため、この 2 つの項目は役割で分けずにいつも足す（FR-006、PR #45 ゆう）。
- 目印のある入居者を一覧の上のほうに出すか、ほかの表示とどう並べるかは、ゆうの画面設計で決める。

## 目印（みさき）

| メソッド・パス | 役割 | 中身 | spec |
|---|---|---|---|
| `GET /api/staff/residents/{id}/change-flags` | CW・L・CO・D | その入居者の今の目印と、過去の目印（新しい順） | FR-003・FR-008・FR-010 |
| `POST /api/staff/residents/{id}/change-flags/confirm` | CW・L・CO・D | 本文 `{note}`（100 文字まで・任意）。その入居者の、まだ確かめていない目印をまとめて確かめ済みにする | FR-009 |

`GET /api/staff/residents/{id}/change-flags` の形：

```json
{
  "current": [
    {
      "id": 12,
      "rule_code": "meal_low",
      "started_at": "2026-10-21T00:10:00Z",
      "streak": 2,
      "evidence": [
        { "record_id": 301, "date": "2026-10-20", "slot": "dinner", "value": "2" },
        { "record_id": 305, "date": "2026-10-21", "slot": "breakfast", "value": "0" }
      ],
      "status": "unconfirmed",
      "confirmations": []
    }
  ],
  "history": [
    {
      "id": 7, "rule_code": "mood_low", "status": "cleared", "started_at": "...", "cleared_at": "...", "cleared_reason": "not_matching",
      "streak": 2, "evidence": [ ... ],
      "confirmations": [ { "staff_display_name": "田中", "confirmed_at": "...", "note": "本人は元気。様子見" } ]
    }
  ]
}
```

- 文言は返さない。`rule_code`・`slot`・`value` は画面が辞書から引いて、「食事量：昨日の夜ごはんから 2 食続けて、少し以下」のように組み立てる（R-06）。
- `note` は職員が書いたまま返し、画面は文字としてだけ出す（FR-013）。
- 確かめた職員は `display_name` だけを返す。
- 決まりがオフでも、過去の目印は `history` に出す。

## 変化の目印の設定（管理画面、みさき）

| メソッド・パス | 役割 | 中身 | spec |
|---|---|---|---|
| `GET /api/admin/change-rules` | CO・D | 決まりの一覧 `[{code, enabled}]` | FR-011・US3 シナリオ 1 |
| `PUT /api/admin/change-rules/{code}` | CO・D | 本文 `{enabled}`。オフにしたらその決まりの今の目印を消し、オンにしたら全員を調べ直す（R-07） | FR-011 |
| `GET /api/admin/change-rules/history` | CO・D | 変更履歴（いつ・誰が・どの決まりを・どう変えたか。新しい順） | FR-011・US3 シナリオ 3 |

## 家族・通知・問い合わせ AI

- 目印を返す家族の API は作らない。家族向けの共通の関数（spec 001 の `disclosure.py`）・通知のまとめ・問い合わせ AI（spec 004）のツールは、目印のテーブルを読まない（FR-007・SC-005）。
- 家族が職員・管理画面の目印の API を直接呼んだときは 403（`forbidden`）、画面は「ページが見つかりません」（spec 001・spec 004 と同じ）。

## 画面（フロントエンド）

| 画面・部品 | 置き場所 | 誰が | 作る人 |
|---|---|---|---|
| 入居者一覧の目印と「確かめていない目印：◯件」（`UnconfirmedFlagFilter`） | 職員の入居者一覧（`ResidentList.tsx`） | CW・L・CO・D | 部品はみさき、置くのはゆう |
| 目印の欄（`ChangeFlagPanel`：当てはまった決まり・もとの記録・案内・確かめた・過去の目印） | 入居者を開いた画面（`RecordPage.tsx`） | CW・L・CO・D | 部品はみさき、置くのはゆう |
| 変化の目印の設定 | 管理画面 `/admin/change-rules` | CO・D | みさき |
