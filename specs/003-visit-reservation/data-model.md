# Data Model: spec 003（面会予約）

PostgreSQL のテーブルの形と、状態の動き。共通の土台（`facilities`・`residents`・`family_accounts`・`staff`・`notifications`・`email_outbox`）は
[spec 001 の data-model.md](../001-family-priority-report/data-model.md) のものを使う。列の名前や型は、実装のときに変えてよい。
ただし **「予約を作る道は 1 つ」「重なりと 1 家族 1 日 1 回は DB の決まりでも守る」**（[research.md R-01](./research.md#r-01-同時に予約されても重なり1-日-2-組1-家族-1-日-1-回を守る)）は変えない。

- id はすべて `bigint`（自動の連番）。日時は `timestamptz`（UTC で保存し、日本時間で判断する）。
- 担当はすべてゆう（G 全体）。`notifications` に列を足すのはさとこ。

## テーブルの一覧

| テーブル | 中身 | 担当 | 時期 | spec |
|---|---|---|---|---|
| `visit_settings` | 施設ごとの面会の設定（1 日に受け付ける組数） | ゆう | ミニマム版（初期データ） | FR-009 |
| `visit_start_times` | 開始時刻の候補 | ゆう | ミニマム版（初期データ） | FR-004・FR-009 |
| `visit_closed_days` | 休みの日 | ゆう | 作り込み | FR-010 |
| `visit_reservations` | 面会予約 | ゆう | ミニマム版 | FR-002・FR-003・FR-007・FR-008・FR-012 |
| `notifications`（列を足す） | `visit_reservation_id` と、種類 `visit_confirmed`・`visit_cancelled`・`visit_reminder` | さとこ | 作り込み | FR-013 |

## `visit_settings`

| 列 | 型 | 説明 |
|---|---|---|
| facility_id | bigint → facilities | 主キー（施設に 1 行） |
| daily_limit | int | 1 日に受け付ける組数。初期値 2（FR-009）。1 以上 |
| updated_by / updated_at | | |

## `visit_start_times`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | |
| start_time | time | 開始時刻（日本時間）。初期値は 10:00・10:30・13:00・13:30・14:00・14:30・15:00・15:30 |
| active | boolean | 候補から外したら `false`（すでに入っている予約はそのまま残す。FR-009） |

- **一意**：`(facility_id, start_time)`
- 終了時刻は、開始の 1 時間 30 分後（列には持たない）。開始時刻＋1 時間 30 分が 17:00 を超える候補は、設定の画面で受け付けない。

## `visit_closed_days`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | |
| closed_date | date | 休みの日（日本時間の日付） |
| created_by / created_at | | |

- **一意**：`(facility_id, closed_date)`
- 予約が入っている日を休みにするときは、その日の予約を先に職員の取り消しにする（[research.md R-08](./research.md#r-08-休みの日を予約が入っている日に設定するとき)）。

## `visit_reservations`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | |
| resident_id | bigint → residents | ログイン中の家族の `CurrentUser.resident_id` から決める（送られた値は使わない。R-05） |
| visit_date | date | 面会の日（日本時間） |
| start_time | time | 開始時刻（日本時間） |
| starts_at / ends_at | timestamptz | 面会の時間（UTC）。`ends_at = starts_at + 1 時間 30 分`（R-02） |
| party_size | int | 来る人数。1 以上、上限なし（FR-002） |
| status | text | `booked`（予約済み）／`cancelled_by_family`（家族が取り消し）／`cancelled_by_staff`（職員が取り消し） |
| created_at | timestamptz | 予約した日時 |
| cancelled_at | timestamptz | 取り消した日時 |
| cancelled_by_staff_id | bigint → staff | 職員が取り消したとき |
| cancel_reason | text | 職員が取り消したときは必須（FR-012）。画面では文字としてだけ出す（FR-016） |

決まり（[research.md R-01](./research.md#r-01-同時に予約されても重なり1-日-2-組1-家族-1-日-1-回を守る)）：

- **1 家族 1 日 1 回**：`UNIQUE (resident_id, visit_date) WHERE status = 'booked'`（部分インデックス）
- **時間の重なり**：`EXCLUDE USING gist (facility_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) WHERE (status = 'booked')`（`btree_gist` 拡張）
- **1 日に受け付ける組数**：DB の決まりでは表せないので、`book_visit` の中で、その日だけの順番待ち（`pg_advisory_xact_lock`）をしてから数える
- `CHECK (party_size >= 1)`
- `CHECK (status <> 'cancelled_by_staff' OR (cancel_reason IS NOT NULL AND cancelled_by_staff_id IS NOT NULL))`

### 状態の動き

```text
               家族が取り消す（前日 17 時まで）
 booked ───────────────────────────────→ cancelled_by_family
   │
   └── 職員が取り消す（締め切りなし、理由は必須） ──→ cancelled_by_staff
```

- 取り消した予約は、元に戻さない（予約し直す）。
- 取り消すと、その時間はまた選べるようになる（決まりは `status = 'booked'` だけを対象にしているため）。

## `notifications` に足すもの（さとこ・作り込み）

| 列 | 型 | 説明 |
|---|---|---|
| visit_reservation_id | bigint → visit_reservations | 種類が `visit_*` のとき |

- 種類（`kind`）に、`visit_confirmed`（予約が確定）・`visit_cancelled`（施設が取り消し）・`visit_reminder`（明日の面会）を足す。
- `visit_reminder` は、同じ予約に 2 回送らないよう `UNIQUE (visit_reservation_id, kind) WHERE kind = 'visit_reminder'`。
- `email_outbox` のテンプレートに `visit_confirmed`・`visit_cancelled`・`visit_reminder` を足す。渡すのは**日時・リンクだけ**（入居者名・理由は渡さない。FR-014）。

## 初期データ（ゆう・ミニマム版）

- `visit_settings`：施設に 1 行、`daily_limit = 2`
- `visit_start_times`：10:00・10:30・13:00・13:30・14:00・14:30・15:00・15:30（すべて `active = true`）
- `visit_reservations`：デモ用に、来週の平日に 1〜2 件（架空の家族）。置き場所は `backend/app/seed/visits.py`
