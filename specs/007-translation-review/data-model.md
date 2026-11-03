# Data Model: spec 007（D：翻訳・整文・訳し戻し・承認）

土台のテーブル（`staff`・`residents` など）と開示設定・通知は [spec 001 data-model.md](../001-family-priority-report/data-model.md) のとおり。担当はみさき（`backend/app/models/memos.py`）。

## テーブルの一覧

| テーブル | 中身 | 時期 | spec |
|---|---|---|---|
| `care_memos` | 様子のメモ | ミ | FR-001〜016 |
| `care_memo_revisions` | 「日本語にする」をやり直した履歴 | ミ（1 回目）／作（やり直し） | FR-004・FR-008 |

spec 001 のテーブルに足すもの（つなぎ目）：
- `disclosure_settings`：`target_type = 'item'`・`target_code = 'memo'` の行（初期値 `visible = true`）（ゆう）
- `notification_settings.notify_items`：選べる値に `memo`（初期値で選んだ状態）。すでにある行にも `memo` を足す（これまでの設定は meal・mood・sleep にしか選びようがなかったため）（ゆう。007-T027）
- `notifications.memo_dates`：`date[]`、初期値は空。まとめ（`daily_digest`・`weekly_digest`）に入ったメモの書いた日（日本時間。重ねない・古い順）。家族のお知らせが、書いた日の連絡帳へのリンクを出すために使う。メモの中身は持たない（ゆう。007-T027）

## `care_memos`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| resident_id | bigint → residents | |
| author_staff_id | bigint → staff | 書いた職員 |
| memo_date | date | 書いた日（日本時間）。家族の連絡帳はこの日に出す |
| written_at | timestamptz | 書いた時刻（家族の連絡帳の並び順） |
| source_lang | text | 原文の言語：`ja`／`id`／`en` |
| original_text | text | 原文（500 文字まで） |
| rewritten_text | text | 整えた日本語（職員が直したものを含む）。辞書を通さずそのまま出す |
| back_translation | text | 訳し戻し（職員の表示言語が日本語なら空） |
| warnings | text[] | 機械の目の印（`medical_added`・`medical_in_original`・`length_changed`・`other_name`・`urgent_words`。research.md R-03） |
| status | text | `draft`／`pending`／`approved`／`returned`／`withdrawn` |
| confirmed_at | timestamptz | 本人が「確かめました」を押した日時（経過時間はここから） |
| approved_by / approved_at | | 承認した職員・日時 |
| returned_by / returned_at / return_reason | | 戻した職員・日時・理由（200 文字まで） |
| unpublished_by / unpublished_at / unpublish_reason | | 公開を取り下げた職員・日時・理由（200 文字まで） |
| withdrawn_at | timestamptz | 取り下げた日時 |

- 1 日 3 件：`(author_staff_id, resident_id, memo_date)` で、`status <> 'withdrawn'` を数える（research.md R-06）。
- 承認できるのは `leader`・`director` で、`author_staff_id` 以外（FR-011a）。
- 戻し（`returned`）にしたときは、承認の列は消さずに残す（履歴として。最新の状態は `status` で見る）。

### 状態の動き

```text
draft    ──確かめました（本人）────────────────→ pending
pending  ──承認する（ほかのリーダー・施設長）──→ approved（家族に出る）
pending  ──戻す（理由）────────────────────────→ returned
approved ──公開を取り下げる（理由）────────────→ returned（家族から見えなくなる）
returned ──直して確かめました（本人）──────────→ pending
draft・pending・returned ──取り下げる（本人）──→ withdrawn
```

- どの矢印も、条件つきの 1 回の更新で進める（research.md R-05）。
- 直せる（原文・整えた日本語・やり直し）のは `draft`・`returned` のときだけ。

## `care_memo_revisions`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| memo_id | bigint → care_memos | |
| original_text | text | このときの原文 |
| rewritten_text | text | AI が整えた日本語（職員が直す前） |
| back_translation | text | 訳し戻し |
| model | text | 使ったモデル名 |
| latency_ms | int | 整える＋訳し戻すにかかった時間 |
| created_at | timestamptz | |

- 1 つのメモでやり直せるのは 5 回まで（この行の数で数える。research.md R-08）。
- 職員が整えた日本語を自分で直したときは、`care_memos.rewritten_text` だけが変わり、訳し戻しをもう一度作る（このときは新しい行を作り、`rewritten_text` に直したあとの文を入れる）。

## 家族に出すときの共通の関数（spec 001 の `services/disclosure.py` に足す）

```text
get_disclosed_memos(resident_id, date_from=None, date_to=None, *, approved_from=None, approved_to=None) -> list[DisclosedMemo]

DisclosedMemo:
  id, memo_date, written_at
  text               整えた日本語（rewritten_text）
  author_name        書いた職員の表示名
  author_occupation  書いた職員の職種のコード（Staff.occupation。空なら名前だけを出す。返事の replied_by_occupation と同じ）
  approved_at        承認した日時
```

- `status = 'approved'` で、開示設定の `memo` が見せる設定のものだけ。原文・訳し戻し・印は返さない。
- 絞り方は 2 つ。どちらか 1 つ以上を必ず渡す（何も渡さないと `ValueError`）。両方渡したら、両方に当てはまるもの。
  - `date_from`〜`date_to`：書いた日（`memo_date`。両端を含む）。家族の連絡帳（007-T026）が使う
  - `approved_from`〜`approved_to`：承認した日時（`approved_from` 以上、`approved_to` より前）。通知のまとめ（007-T027）が使う。昨日書いて今日承認したメモを、今日のまとめに入れるため（FR-012b）
- 作る人：みさき。開示の判断は、ゆうが 001-T038 で作る `is_item_disclosed(code)`（開示設定のキャッシュを読む。H の `is_feature_disclosed(code)` と同じ形）を `is_item_disclosed("memo")` で呼び、ゆうが確かめる。使う人：さとこ（連絡帳・通知のまとめ）。

## 承認待ちの件数（ゆうの画面から呼ぶ）

```text
count_pending_memos(user) -> int | None
```

- `user.role` が `leader`・`director` のときだけ、施設全体の `status = 'pending'` の数を返す（本人が書いたものも数える。承認はほかの人がするため）。それ以外の役割は `None`（件数を出さない。FR-015）。
