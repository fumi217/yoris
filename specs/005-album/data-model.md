# Data Model: spec 005（アルバム）

PostgreSQL のテーブルの形と、状態の動き。土台は [spec 001 の data-model.md](../001-family-priority-report/data-model.md)。
列の名前や型は、実装のときに変えてよい。ただし **「家族に写真を出す道は `get_visible_album_photos` の 1 つだけ」** は変えない。

- id はすべて `bigint`（自動の連番）。日時は `timestamptz`（UTC で保存し、日本時間で判断する。spec 001 の R-14）。
- 担当はすべてさとこ（開示設定の `feature` の行だけゆう）。時期はすべて作り込み。

## テーブルの一覧

| テーブル | 中身 | 担当 | 時期 | spec |
|---|---|---|---|---|
| `album_photos`（新規） | 載せた写真（入居者ごと） | さとこ | 作り込み | FR-001・FR-023 |
| `uploaded_files`（既存に足す） | `purpose` に `album` を足す | さとこ | 作り込み | FR-004 |
| `disclosure_settings`（既存に足す） | `target_type` に `feature` を足し、`album` の行を持つ | ゆう | 作り込み | FR-013 |
| `notifications`（既存に足す） | `has_album` を足す | さとこ | 作り込み | FR-017・FR-018 |
| `notification_settings`（既存に足す） | `notify_album` を足す | さとこ | 作り込み | FR-017 |

## `album_photos`（新規）

| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| resident_id | bigint → residents | 載せた入居者。家族には、この入居者の家族アカウントだけが見える |
| file_id | bigint → uploaded_files | 元の写真（Exif を消し、向きを直したもの）。削除したら空にする |
| thumb_file_id | bigint → uploaded_files | 一覧用のサムネイル（長い辺 480px）。削除したら空にする |
| comment | varchar(100) | 一言コメント（任意）。職員が自由に書いた文。辞書を通さずそのまま出す。削除したら空にする |
| posted_by | bigint → staff | 載せた職員 |
| posted_at | timestamptz | 載せた日時 |
| deleted_by | bigint → staff | 削除した職員 |
| deleted_at | timestamptz | 削除した日時。入っていれば削除済み |

- **索引**：`(resident_id, posted_at DESC, id DESC)`（家族の一覧と、まとめで使う）
- **状態の動き**：載せた（`deleted_at` が空）→ 削除した（`deleted_at` あり）。元に戻せない。
- **削除したときの行**：行は「誰がいつ削除したか」の記録として残す。`file_id`・`thumb_file_id`・`comment` は空にし、`uploaded_files` の 2 行と保存先のファイルは消す（[research.md R-05](./research.md#r-05-写真の削除)）。
- コメントは載せたあとに直せない（FR-023）。直したいときは削除して載せ直す。
- 家族アカウントがない入居者の写真も保存する。家族アカウントができたら、過去の写真も含めて見られる（Edge Cases）。

## `uploaded_files`（既存に足す）

| 列 | 変更 |
|---|---|
| purpose | `menu`／`announcement` に **`album`** を足す。アルバムの写真の元とサムネイルは、どちらも `album` |
| content_type | アルバムでは `image/jpeg`／`image/png` のみ（PDF は受け付けない） |

## `disclosure_settings`（既存に足す・ゆう）

| 列 | 変更 |
|---|---|
| target_type | `item`／`theme` に **`feature`** を足す |
| target_code | `feature` のとき `album` |

- 初期値は `(facility_id, 'feature', 'album', visible = true)` の 1 行（FR-013）。
- 一意 `(facility_id, target_type, target_code)` と、変更履歴 `disclosure_setting_histories` は、そのまま使う（FR-015）。
- `get_disclosed_records` や通知の項目の選択肢は `item` の行だけを見るので、`feature` の行は混ざらない。

## 家族に出すときの共通の関数（さとこ）

置き場所：`backend/app/services/album.py`（[research.md R-03](./research.md#r-03-家族に出す道は-1-つだけ)）。

| 関数 | 返すもの | 使う人 |
|---|---|---|
| `get_visible_album_photos(resident_id, before=None, limit=30)` | アルバムが「見せる」のときだけ、その入居者の削除されていない写真（id・サムネイル・元の写真・コメント・載せた日時）を新しい順に返す。「見せない」のときは空にせず、呼び出し側が 404 にする | 家族のアルバムの API |
| `can_family_view_photo(photo, resident_id)` | その写真を、その入居者の家族が見てよいか（自分の入居者の写真・削除されていない・アルバムが「見せる」） | `GET /api/files/{id}` |
| `count_new_photos(resident_id, since, until)` | まとめ用。期間内に載せられ、削除されていない写真の数 | `digest.py` |

## `notifications`（既存に足す）

| 列 | 変更 |
|---|---|
| has_album | boolean、初期値 `false`。まとめ（`daily_digest`・`weekly_digest`）に、載せた写真が含まれるとき `true` |

## `notification_settings`（既存に足す）

| 列 | 変更 |
|---|---|
| notify_album | boolean、初期値 `true`。「アルバムの新しい写真」を通知するか。アルバムを見せない設定のときは選択肢に出さず、通知も止める |

## ファイルを開ける人

| ファイル | 開ける人 |
|---|---|
| アルバムの写真（元・サムネイル） | ログインした職員（削除されていないもの）と、その入居者の家族（アルバムが「見せる」のとき）。そのほかは 404（ログインしていなければ 401） |
