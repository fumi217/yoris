# Data Model: spec 006（E：変化の検知）

spec 001 の [data-model.md](../001-family-priority-report/data-model.md) の `care_records`・`residents`・`staff` を読み、変化の検知のテーブルを 4 つ足す。担当はすべてみさき。
理由は [research.md](./research.md) を見る。id は `bigint`、日時は `timestamptz`（UTC で保存し、日本時間で判断する。001 の R-14）。

## テーブルの一覧

| テーブル | 中身 | 時期 | spec |
|---|---|---|---|
| `change_rules` | 変化の決まり（3 つ）とオン／オフ | 作り込み | FR-002・FR-011・FR-012 |
| `change_rule_histories` | 決まりのオン／オフの変更履歴 | 作り込み | FR-011 |
| `change_flags` | 変化の目印（入居者 × 決まりごとの、当てはまった期間） | 作り込み | FR-001・FR-003・FR-008・FR-010 |
| `change_flag_confirmations` | 目印を確かめた記録 | 作り込み | FR-009・FR-010 |

## 読むもの（spec 001。変えない）

- `care_records`：`resident_id`・`date`・`item`（`meal`／`mood`／`sleep`）・`slot`・`value`・`deleted_at`。取り消したもの（`deleted_at` あり）は読まない。
  職員向けなので、開示設定に関係なく読む（001 の R-06）。
- `staff`：`role` で見せる相手を決める（R-05）。確かめた職員の表示名に `display_name` を使う。

## `change_rules`

| 列 | 型 | 説明 |
|---|---|---|
| code | text | **主キー**。`meal_low`／`mood_low`／`sleep_poor`（[research.md R-01](./research.md)） |
| enabled | boolean | オン／オフ（初期値はすべて true） |
| updated_at | timestamptz | |
| updated_by | bigint → staff | 初期データは空 |

- 条件（対象の項目・当てはまる値・何回続けて）はコード（`services/change_rules.py`）に持ち、テーブルには持たない（この spec では変えられない。FR-012）。
- 表示名は辞書から引く（`change.rule.meal_low` など。R-06）。
- 初期データ（`seed/change_rules.py`）で 3 行を入れる。

## `change_rule_histories`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| rule_code | text → change_rules | |
| enabled_before | boolean | |
| enabled_after | boolean | |
| changed_by | bigint → staff | |
| changed_at | timestamptz | |

## `change_flags`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| resident_id | bigint → residents | |
| rule_code | text → change_rules | |
| started_at | timestamptz | 目印が付いた日時 |
| cleared_at | timestamptz | 目印が消えた日時。空なら今の目印 |
| cleared_reason | text | `not_matching`（当てはまらなくなった）／`rule_disabled`（決まりをオフにした）。消えたときだけ |
| streak | int | 続いた数（例：2 食） |
| evidence | jsonb | もとになった記録の一覧。`[{record_id, date, slot, value}]`（古い順）。押し直しで記録の値が変わっても、そのときの値が残るように写しを持つ |
| status | text | `unconfirmed`（まだ確かめていない）／`confirmed`（確かめ済み）／`cleared`（消えた。履歴） |
| updated_at | timestamptz | |

- **一意**：`(resident_id, rule_code) WHERE cleared_at IS NULL`（今の目印は、入居者 × 決まりごとに 1 つ。部分インデックス）。
- **状態と消えた日時をそろえる**：`CHECK ((status = 'cleared') = (cleared_at IS NOT NULL))`。消すときは `status = 'cleared'`・`cleared_at`・`cleared_reason` を 1 回の更新でまとめて入れる（消えた目印の `status` が `unconfirmed`・`confirmed` のまま残らないように）。消える前に確かめていたかは `change_flag_confirmations` に残る。
- **消えた理由は、消えたときだけ入れる**：`CHECK ((cleared_reason IS NOT NULL) = (cleared_at IS NOT NULL))`。`cleared_reason` だけ入って消えていない、消えたのに理由がない、を DB で防ぐ。
- 書き込むのは `evaluate_change_flags`（[research.md R-03](./research.md)）と、確かめる処理・決まりのオン／オフだけ。
- `evidence` には記録の値（コード）が入るが、ログには出さない（FR-014）。

### 状態の動き

```text
（決まりに当てはまった）            → 目印あり・まだ確かめていない（started_at）
まだ確かめていない ──「確かめた」──→ 確かめ済み
確かめ済み ──続いた数が確かめたときより増えた──→ まだ確かめていない
目印あり（どちらの状態でも） ──当てはまらなくなった──→ 消えた（status = cleared・cleared_at・cleared_reason = not_matching）
目印あり（どちらの状態でも） ──決まりをオフにした──→ 消えた（status = cleared・cleared_at・cleared_reason = rule_disabled）
消えた ──また当てはまった──→ 新しい行で目印あり（消えた行は履歴として残る）
```

## `change_flag_confirmations`

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| change_flag_id | bigint → change_flags | |
| confirmed_by | bigint → staff | |
| confirmed_at | timestamptz | |
| note | text | ひとこと（100 文字まで、任意）。そのまま文字として表示する（FR-013） |
| streak_at_confirmation | int | 確かめたときの続いた数。これより増えたら、まだ確かめていないに戻す（FR-010） |

- 「確かめた」は入居者ごとに 1 回押し、その入居者の今の目印のうち `unconfirmed` のものそれぞれに 1 行ずつ足す（同じ note・同じ日時。[research.md R-04](./research.md)）。
- 確かめ直したら行が増え、前の確かめた記録も残る。

## 入居者一覧に返すもの（`get_flag_summary` の形）

ゆうの入居者一覧（001-T028）が呼ぶ。入居者一覧を開けるのは事務員以外の職員だけなので、役割で分けずに呼ぶ（R-05）。

```text
get_flag_summary(session) ->
  residents: { resident_id: { has_flag: bool, has_unconfirmed: bool } }   # 今の目印がある入居者だけ
  unconfirmed_resident_count: int                                         # まだ確かめていない目印がある入居者の人数
```
