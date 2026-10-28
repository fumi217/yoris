# API Contract: spec 005（アルバム）

フロントエンドとバックエンドの間の API の一覧と決まりごと。共通の決まり（先頭は `/api`、Cookie のセッション、書き込みは `X-Requested-With: fetch`、
エラーの形 `{ "error": { "code", "message_key" } }`、文言はコードで返して画面で辞書から引く、日付は `YYYY-MM-DD`（日本時間）・日時は ISO 8601（UTC））は、
[spec 001 の contracts/api.md](../../001-family-priority-report/contracts/api.md) と同じ。正式な定義は FastAPI が出す OpenAPI とする。

- **家族の API では、入居者を指定させない**。ログイン中の家族の `CurrentUser.resident_id` から決める。
- 家族の API・ファイルの API は、ほかの入居者の写真・削除された写真・アルバムを見せない設定のとき、すべて **404 `not_found`**（存在するかどうかも知らせない）。
- 写真のファイルのアップロードだけ `multipart/form-data`。担当はすべてさとこ（開示設定の `feature` の部分だけゆう）。時期はすべて作り込み。

### 役割の略号

`F` 家族、`CW` 介護職員、`L` リーダー、`CO` 生活相談員、`CL` 事務員、`D` 施設長、`職員` は CW・L・CO・D（アルバムの載せる・削除には、事務員 CL を含めない）

### エラー（spec 001 の一覧をそのまま使う。足すものはない）

| HTTP | code | いつ | spec |
|---|---|---|---|
| 401 | `not_logged_in` | ログインしていない（ファイルの URL を直接開いたときも） | FR-007 |
| 403 | `forbidden` | 家族のロールで職員の API（載せる・削除）を呼んだ | FR-011 |
| 404 | `not_found` | ほかの入居者の写真、削除された写真、アルバムを見せない設定のときの家族の API・ファイル | FR-006・FR-014 |
| 422 | `invalid_file` | 形式が JPG・PNG でない（PDF も含む）、10MB を超える（先頭のバイトで確かめる） | FR-003 |
| 422 | `validation_error` | 一言コメントが 100 文字を超える | FR-023 |

## 家族

| メソッド・パス | 役割 | 中身 | spec |
|---|---|---|---|
| `GET /api/family/features` | F | 開示設定の `feature` の状態（例: `{ "album": true }`）。家族の画面の枠が、「☰ その他」にアルバムを出すかを決めるのに使う | FR-010・FR-014 |
| `GET /api/family/album?before=&limit=` | F | 自分の入居者の写真を、載せた日（日本時間）ごとに、新しい順に返す。1 回の既定は 12 枚（`limit` の上限は 30。Session 2026-10-28）。続きは、返り値の `next_before` を `before` に渡す。アルバムを見せない設定のときは 404 | FR-005・FR-006・FR-008 |

```json
// GET /api/family/album の返り値（例）
{
  "days": [
    {
      "date": "2026-11-05",
      "photos": [
        {
          "id": 31,
          "posted_at": "2026-11-05T05:12:00Z",
          "comment": "運動会で、玉入れを楽しみました",
          "url": "/api/files/500"
        },
        {
          "id": 30,
          "posted_at": "2026-11-05T03:40:00Z",
          "comment": null,
          "url": "/api/files/498"
        }
      ]
    }
  ],
  "next_before": null
}
```

- 写真が 1 枚もないときは `"days": []`（画面で「まだ写真はありません」を出す）。
- `comment` は職員が自由に書いた文なので、そのまま返す（画面では文字としてのみ表示する）。
- 通知の設定（`notify_album`）は、spec 001 の `GET/PUT /api/family/notification-settings` に項目を足す（下の表）。

## 職員

| メソッド・パス | 役割 | 中身 | spec |
|---|---|---|---|
| `POST /api/staff/residents/{id}/album` | 職員 | 写真を 1 枚載せる（`multipart/form-data`：`file`、任意で `comment`（100 文字まで））。入居者は URL で指定する。画面は最大 10 枚を 1 枚ずつ順に送る。422：`invalid_file`・`validation_error` | FR-001・FR-003・FR-023 |
| `GET /api/staff/residents/{id}/album` | 職員 | その入居者の載せた写真（削除されていないもの）の一覧。`family_visible`（いまアルバムが家族に見えているか）を含める。家族に見せていないときは、画面に「いま家族には見せていません」を出す | FR-016 |
| `DELETE /api/staff/album/{id}` | 職員 | 写真を削除する（写真のファイルも消す）。誰が消したかを残す。家族のロールは 403 | FR-011・FR-012 |

## 開示設定（ゆう）

| メソッド・パス | 役割 | 中身 | spec |
|---|---|---|---|
| `GET /api/admin/disclosure` | CO・D | 既存の返り値に、`feature` の行（`target_type: "feature"`、`target_code: "album"`、`visible`）を足す | FR-013 |
| `PUT /api/admin/disclosure` | CO・D | `feature` の行も変えられる。保存したら開示設定のキャッシュを必ず消す。変更は履歴に残る | FR-013・FR-015 |
| `GET /api/admin/disclosure/history` | CO・D | `feature` の変更も履歴に出る | FR-015 |

## ファイル（spec 001 の `GET /api/files/{id}` に条件を足す）

| メソッド・パス | 役割 | 中身 | spec |
|---|---|---|---|
| `GET /api/files/{id}` | ログイン中の家族・職員 | アルバムの写真のとき、職員（CW・L・CO・D）は削除されていないものを開ける。事務員は 404。家族は、自分の入居者の写真で、削除されておらず、アルバムが「見せる」のときだけ開ける。それ以外は 404。ログインしていなければ 401。`Content-Type` は保存した形式に固定し、`X-Content-Type-Options: nosniff` を付ける | FR-006・FR-007・FR-022 |

## 通知（spec 001 の API に足すもの）

| 対象 | 足すもの | spec |
|---|---|---|
| `GET /api/family/notification-settings` の返り値 | `notify_album`（アルバムの新しい写真を通知するか）。アルバムを見せない設定のときは、この項目を返さない | FR-017 |
| `PUT /api/family/notification-settings` | `notify_album` を変えられる | FR-017 |
| `GET /api/family/notifications` の返り値（まとめ） | `has_album`（まとめに写真が含まれるか）。画面は、文言を辞書から引く | FR-018 |

## メール（worker。spec 001 のメールの一覧に足すもの）

新しい種類は作らない。`daily_digest`・`weekly_digest` の文面を、`has_album` で出し分ける。

| 種類 | 件名の例 | テンプレートに渡すもの |
|---|---|---|
| `daily_digest`（記録だけ） | 今日の連絡帳がまとまりました | リンクだけ |
| `daily_digest`（写真だけ） | アルバムに新しい写真が載りました | リンクだけ |
| `daily_digest`（両方） | 今日の連絡帳がまとまりました（アルバムに新しい写真が載りました） | リンクだけ |
| `weekly_digest` | （同じ考え方で、「今週の」にする） | リンクだけ |

**写真・ファイル名・一言コメント・入居者名は、メールにも、アプリ内のお知らせにも渡さない**（FR-019・SC-007）。
