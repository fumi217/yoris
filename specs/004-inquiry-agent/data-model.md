# Data Model: spec 004（F：問い合わせ AI エージェント）

PostgreSQL のテーブルの形と、状態の動き。土台の `users`・`family_accounts`・`staff`・`residents` と、
記録・返事・通知のテーブルは [spec 001 data-model.md](../001-family-priority-report/data-model.md) のとおり。
開発前MTG で `inquiries`（問い合わせの履歴）・`escalations`（相談員に回したもの）と仮に呼んでいたものは、会話の形になったので次の名前にする。

- id はすべて `bigint`。日時は `timestamptz`（UTC で保存、日付の判断は日本時間）。
- 担当はすべてみさき（`backend/app/models/inquiry.py`）。

## テーブルの一覧

| テーブル | 中身 | 時期 | spec |
|---|---|---|---|
| `inquiry_conversations` | 会話（家族アカウントに 1 本） | ミ | FR-008 |
| `inquiry_messages` | 会話の中の発言（家族・AI・職員） | ミ | FR-001・FR-004・FR-008 |
| `staff_messages` | AI が職員に渡したメッセージ | ミ | FR-009〜018 |
| `staff_message_events` | 担当・種類・状態の変わった履歴 | ミ（担当を決めた）／作（それ以外） | FR-012b・FR-015 |
| `staff_message_templates` | 職員の返事の定型文 | ミ | FR-014 |

回数の制限は Redis（[research.md R-07](./research.md#r-07-1-日の回数の制限)）。

## `inquiry_conversations`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| family_account_id | bigint → family_accounts | **一意**（家族アカウントに 1 本） |
| resident_id | bigint → residents | 家族アカウントの入居者（探しやすくするため） |
| created_at | timestamptz | |

- 家族が初めて送ったときに作る。

## `inquiry_messages`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| conversation_id | bigint → inquiry_conversations | |
| sender | text | `family`／`ai`／`staff` |
| body | text | 発言の文。家族は 500 文字まで。辞書を通さずそのまま出す（職員の定型文は下の `template_ids` から引く） |
| created_at | timestamptz | |
| ai_result | text | AI の発言だけ：`answered`（答えた）／`handed_off`（職員に渡した）／`no_record`（答えられる記録がない） |
| source_ids | text[] | AI の発言だけ：確かめたあとの根拠（`record:<id>`・`reply:<id>`。[research.md R-03](./research.md#r-03-根拠の確かめ答えは答えるツールで返させる)） |
| model | text | AI の発言だけ：使ったモデル名 |
| tool_calls | int | AI の発言だけ：ツールを呼んだ回数（上限 5） |
| latency_ms | int | AI の発言だけ：かかった時間 |
| staff_message_id | bigint → staff_messages | 職員に渡したもの・職員の返事・家族の続きの書き込みのとき、どのメッセージか |
| staff_id | bigint → staff | 職員の発言だけ：返事をした職員 |
| template_ids | bigint[] | 職員の発言だけ：選んだ定型文（1 つ以上） |
| note | text | 職員の発言だけ：書き足した短い文（100 文字まで、任意） |
| response_type | text | 職員の発言だけ：`app`（アプリで返事）／`phone`（電話で対応した） |

- 家族の画面には、時刻の順にすべて出す（FR-008）。AI の発言には `source_ids` から「もとにした記録」（日付・項目／テーマ）を組み立てて出す。
  組み立てるときも `get_disclosed_records`・`get_active_replies` を通す（いま非開示になった記録は出さない）。
- 根拠（`source_ids`）のうち 1 つでも、いま家族に見せられなくなった AI の答え（`answered`）は、本文も根拠も出さない（`body` を空にし、画面は辞書の `inquiry.answer_hidden` を出す）。
  AI に渡す直近のやりとりにも入れない（非開示になった中身を、AI が新しい答えに書かないため。原則 IV）。DB の本文は消さないので、開示に戻せばまた出る（PR #205 ようこ）。
- AI への指示の文は保存しない（家族の画面に出すものだけを保存する）。
- AI が答えなかった発言（`ai_result` が `handed_off`・`no_record`）は、`body` を空にする。画面は `ai_result` から辞書の決まった文（`inquiry.handed_off`・`inquiry.no_record`）を、家族の表示言語で出す。
- AI のサービスにつながらなかったとき（503 `ai_unavailable`）は、家族の発言も保存しない（会話に答えのない発言を残さない。画面は入力した文を消さず、送り直せる。FR-026）。

## `staff_messages`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| conversation_id | bigint → inquiry_conversations | |
| resident_id | bigint → residents | |
| origin_message_id | bigint → inquiry_messages | 渡すきっかけになった家族の発言 |
| category | text | `medical`（医療・体調）／`complaint`（苦情）／`money`（お金・書類）／`care_request`（お世話の頼みごと）／`urgent`（緊急）／`other`（そのほか） |
| summary | text | AI がまとめた要約（日本語。500 文字まで）。開示されていない記録の内容は入れない |
| status | text | `waiting`（対応待ち）／`answered`（対応済み） |
| assignee_id | bigint → staff | 担当（1 人）。渡した時点では空 |
| handed_at | timestamptz | 最初に渡した日時（経過日数・24 時間・3 日はここから。家族の続きで対応待ちに戻ったときは `reopened_at`） |
| reopened_at | timestamptz | 家族の続きの書き込みで、対応待ちに戻った日時 |
| responded_by / responded_at | | 最後に対応した職員・日時 |

- **苦情**（`category = 'complaint'`）は、生活相談員・施設長だけが読める。読むところはすべて `visible_staff_messages(user)` を通す（[research.md R-12](./research.md#r-12-苦情の見え方)）。
- 同じ家族の同じ内容の対応待ちは、AI が `existing_message_id` で同じメッセージにつなぐ（FR-016）。
- 直前の 3 往復は、`origin_message_id` より前の、同じ会話の発言を 6 件（家族 3・AI／職員 3）まで取り出して見せる。それより前は職員に見せない（FR-012）。

### 状態の動き

```text
（AI が渡す）→ waiting ──職員がアプリで返事・電話で対応した──→ answered
                  ↑                                                │
                  └─── 家族の続きの書き込み（職員への続きが要る）───┘

担当：空 ──「自分が対応する」（最初の 1 人だけ）──→ 職員 A ──外す──→ 空
                                                    └──ほかの職員に変える──→ 職員 B
```

- 「自分が対応する」と返事は、条件つきの 1 回の更新で最初の 1 人だけにする（[research.md R-08](./research.md#r-08-職員へのメッセージの最初の-1-人)）。
- 24 時間・3 日は、開いたときに `COALESCE(reopened_at, handed_at)` からの経過で決める（状態は変えない。R-13）。

## `staff_message_events`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| staff_message_id | bigint → staff_messages | |
| type | text | `assigned`（担当になった）／`unassigned`（外した）／`reassigned`（変えた）／`category_changed`（種類を変えた）／`reopened`（対応待ちに戻った）／`answered`（対応した） |
| staff_id | bigint → staff | 操作した職員（家族の続きのときは空） |
| from_value / to_value | text | 変わる前と後（担当の id・種類のコードなど） |
| created_at | timestamptz | |

## `staff_message_templates`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| category | text | 質問の種類（苦情には用意しない） |
| code | text | 一意。辞書のキー（例：`staff_template.care_request.next_visit`） |
| sort_order | int | |

- 質問の種類ごとに 3〜5 個。文言は辞書（日本語・インドネシア語・英語）に置く（spec 001 research.md R-11）。初期データはみさき。

## 件数を数える関数（ゆうの画面から呼ぶ）

```text
count_waiting_staff_messages(session, user, resident_id=None) -> int
count_waiting_staff_messages_by_resident(session, user) -> dict[int, int]
```

- `session` は呼ぶ側の DB のセッション（中では commit しない。spec 001 の `create_reply_notice(session, ...)` と同じ形）。
- `visible_staff_messages(user)` を通して、`status='waiting'` を数える（苦情は生活相談員・施設長にだけ数える。FR-013）。
- `count_waiting_staff_messages`：`resident_id` を渡すとその入居者の分だけ、渡さないと施設全体を数える。
- `count_waiting_staff_messages_by_resident`：入居者ごとの件数を 1 回の問い合わせ（`GROUP BY resident_id`）で返す（入居者 id → 件数。0 件の入居者は入れない）。入居者一覧で 1 人ずつ呼ぶと問い合わせが人数分になるため（PR #42 のゆうのコメント）。

## spec 001 の `notifications` に足す列

| 列 | 型 | 説明 |
|---|---|---|
| staff_message_id | bigint → staff_messages | `kind = 'staff_message_reply'` のとき、どのメッセージの返事か（ほかの種類では空）。作る人：さとこ（T028。research.md R-09） |
- 置き場所：`backend/app/inquiry/visibility.py`。使う人：ゆう（職員の入居者一覧、spec 001 T028・T053）。
