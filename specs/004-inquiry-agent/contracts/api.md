# API Contract: spec 004（F：問い合わせ AI エージェント）

共通の決まり（`/api`、Cookie のセッション、`X-Requested-With: fetch`、エラーの形、日付と日時、コードで返す）は
[spec 001 contracts/api.md](../../001-family-priority-report/contracts/api.md) と同じ。正式な定義は FastAPI の OpenAPI。担当はすべてみさき。

### 役割の略号

`F` 家族、`S` 施設の職員（介護職員・リーダー・生活相談員・事務員・施設長）、`CO` 生活相談員、`D` 施設長

### 時期の略号

`ミ` ミニマム版（Day 2〜4）、`作` 作り込み（Day 5〜）

### エラー（spec 001 の表に足すもの）

| HTTP | code | いつ | spec |
|---|---|---|---|
| 409 | `already_assigned` | ほかの職員が先に「自分が対応する」を押した | FR-012b |
| 409 | `already_answered` | ほかの職員が先に返事をした | FR-017 |
| 429 | `inquiry_limit` | 家族の 1 日 10 回、または施設全体の 1 日の上限を超えた | FR-024・FR-027 |
| 503 | `ai_unavailable` | AI のサービスに接続できない・30 秒を超えた（回数に数えない） | FR-026 |
| 404 | `not_found` | 見られないメッセージ（生活相談員・施設長以外で苦情）を id で指定した | FR-018 |
| 403 | `forbidden` | 家族が職員の API を呼んだ | FR-018 |

## 家族の「質問する」

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/family/inquiry/messages?before=<id>&limit=30` | F | ミ | 会話の発言を新しい順に。AI の発言には「もとにした記録」（日付・項目／テーマ）、職員の発言には返事をした職員の表示名と定型文のコード・書き足した文、職員に渡した発言には状態（対応待ち／対応済み）と「3 日たったか」 | FR-004・FR-005・FR-008・FR-016b |
| `POST /api/family/inquiry/messages` | F | ミ | 質問を送る（`body`：1〜500 文字）。AI の答え（または「職員にお伝えしました」）が決まってから、家族の発言と AI の発言を返す。429：`inquiry_limit`、503：`ai_unavailable`、422：`validation_error` | FR-001〜003・FR-009・FR-024・FR-026 |
| `POST /api/family/inquiry/messages/{id}/read` | F | 作 | 職員の返事の発言が画面に出たとき、その発言のお知らせを読んだことにする（204。何度呼んでも同じ）。ほかの家族の発言・職員の返事でない発言（AI・家族・電話で対応した発言）は 404 | FR-014 |

- 入居者は `CurrentUser.resident_id` から決める（FR-020）。返す値に、AI への指示の文・ツールの中身は入れない（FR-021）。
- 職員の発言（`sender = staff`）は、`body` は空で、返した職員の**表示名**（`staff_name`）と職種のコード（`staff_occupation`。職員の `occupation`。空なら null で、画面は名前だけを出す（役割では補わない）。画面が辞書の `occupation.*` で引き、「表示名（職種）からの返事」と出す。#263）、選んだ定型文のコード（`template_codes`。選んだ順。画面が辞書で引く）、書き足した文（`note`。文字としてだけ出す）、返し方（`response_type`：`app`／`phone`）を持つ。ほかの発言では、この 5 つは null。
- 職員に渡した AI の発言（`ai_result = handed_off`）には `handoff` を付ける：`status`（`waiting`／`answered`）、`urgent`（種類が緊急なら true。画面は「お急ぎのときは、施設にお電話ください」も出す）、
  `already`（同じ内容の対応待ちにつないだなら true。画面は「施設の職員にお伝えしました」の代わりに「すでに施設の職員にお伝えしています」を出す）。
  質問の種類そのものは家族に返さない。ほかの発言では `handoff` は空（FR-009〜011・FR-016・Edge Cases）。
- AI の発言の `body` は、答えたとき（`ai_result = answered`）だけ文が入る。`handed_off`・`no_record` のときは空で、画面が辞書の決まった文を出す（data-model.md）。
- 根拠のうち 1 つでも、いま非開示になった答えは `hidden: true` で、`body` は空・`sources` は空にする。画面は `inquiry.answer_hidden` を出す（data-model.md）。
- 503 `ai_unavailable` のときは、家族の発言も保存しない（送り直せる。data-model.md）。
- 職員の返事のお知らせ（`kind = staff_message_reply`）は、返事の発言が画面に出たときに読んだことにする（連絡帳の返事と同じ決まり。spec 001 R-15）。
  読んだことにするのは、その発言と同じ `staff_message_id` で、その発言の日時までに作られた、同じ家族の未読のお知らせ。
  返事の発言とお知らせは同じトランザクションで作る（`reply_in_app`）ので、時刻が同じになる。列は足さない。
  同じメッセージに返事が 2 回付いたときは、後の返事を見れば前の分も、前の返事だけなら前の分だけが、読んだことになる
- 電話で対応した発言（`response_type = phone`）には、お知らせがないので、画面からこの API を呼ばない

## 職員の「家族からのメッセージ」

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/staff/messages?status=waiting&resident_id=` | S（苦情は CO・D だけに出る） | ミ | 一覧：入居者の名前（`resident_display_name`。職員の表示言語に合わせる。spec 001 の data-model.md「入居者の名前の出し方」）・家族の続柄（`family_relationship`。`daughter` などのコード。家族アカウントがなければ null。#389）・種類・担当・要約（`summary`。読みを付けた `summary_ruby` も返す）・受け付けた日時・経過日数・「1 日以上待っています」・状態。対応待ち → 担当が自分か空 → 古い順 | FR-012・FR-016b・FR-028a |
| `GET /api/staff/messages/count?resident_id=` | S | ミ | 対応待ちの件数（ゆうの入居者一覧から呼ぶ。苦情は CO・D にだけ数える） | FR-013 |
| `GET /api/staff/messages/{id}` | S（苦情は CO・D） | ミ | 詳細：一覧の 1 件の項目（入居者の名前・家族の続柄を含む）・原文（`origin`。読みを付けた `origin_ruby` も返す）・要約（`summary`・`summary_ruby`）・種類・担当・状態・直前の 3 往復・追加された家族の書き込み・その種類の定型文の一覧。見られなければ 404。`*_ruby` は表示用で、`{漢字\|かんじ}` の書き方。保存している原文・要約は変えない | FR-011・FR-012・FR-028a |
| `POST /api/staff/messages/{id}/assign` | S（苦情は CO・D） | ミ | 「自分が対応する」。409：`already_assigned` | FR-012b |
| `DELETE /api/staff/messages/{id}/assign` | S（苦情は CO・D） | 作 | 担当を外す | FR-012b |
| `PUT /api/staff/messages/{id}/assignee` | S（苦情は CO・D） | 作 | 担当をほかの職員に変える（`staff_id`） | FR-012b |
| `PATCH /api/staff/messages/{id}/category` | S（苦情から変えるのは CO・D だけ） | 作 | 種類を付け替える（`category`） | FR-015 |
| `POST /api/staff/messages/{id}/reply` | S（苦情は CO・D） | ミ | アプリで返事（`template_ids`：1 つ以上、`note`：100 文字まで・任意）。家族の会話に返事を足し、家族へのお知らせとメールを作り、対応済みにする。409：`already_answered` | FR-014・FR-017 |
| `POST /api/staff/messages/{id}/phone` | S（苦情は CO・D） | 作 | 電話で対応した。家族の会話に「施設の職員がお電話で対応しました」を足し、対応済みにする（お知らせ・メールは送らない）。409：`already_answered` | FR-014 |

- どの API も `visible_staff_messages(user)` を通す（[research.md R-12](../research.md#r-12-苦情の見え方)）。家族が呼んだら 403、見られないメッセージは 404。
- 職員の返事・AI の要約は、文字としてのみ表示する（FR-028）。
- **assign**（204、本文なし）：最初の 1 人だけが担当になる。もう自分が担当なら、何度押しても 204（履歴は足さない）。ほかの職員が担当なら 409。担当になったことを `staff_message_events` に残す（`assigned`）。
- **reply**（201）：本文は `template_ids`（その種類の定型文だけ。1 つ以上）と `note`（任意）。余分な項目は 422。返す値は `{id, staff_message_id, status}`（`id` は家族の会話に足した職員の発言）。
  - 見られないメッセージ（ほかの役割の苦情）は 404。**苦情には定型文を用意しない**（電話で対応する。FR-014）ので、生活相談員・施設長でも、アプリの返事は 422（選べる定型文がない）。苦情は電話で対応する（`phone`、作り込み）
  - 返した職員が担当になる。担当が空だったときは `assigned`、ほかの職員が担当だったときは `reassigned`（前の担当 → 返した職員）を履歴に残し、そのあと `answered` を残す。もう自分が担当なら `answered` だけ
  - 家族の会話に、職員の発言（`sender = staff`、`body` は空、定型文・書き足し・返した職員）を足し、家族へのお知らせとメールの送る予定を同じトランザクションで作る。メールは commit のあとにその場で送る（送れなくても送る予定が残る。R-09）
  - どちらも、職員への通知・音は出さない（SC-008）

## メール（spec 001 の仕組みに足すもの）

| 種類 | 件名の例 | テンプレートに渡すもの | 作る人 |
|---|---|---|---|
| `staff_message_reply` | 施設からメッセージの返事が届きました | リンクだけ（返事の中身は渡さない） | さとこ（`create_staff_message_reply_notice(session, staff_message_id)`。R-09） |
