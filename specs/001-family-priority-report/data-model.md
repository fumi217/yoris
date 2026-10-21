# Data Model: spec 001

PostgreSQL のテーブルの形と、状態の動き。土台は [開発前MTG](../../docs/context/meeting/開発前MTG.md) の案と「コメントで決まったこと」で、
PR #17 のレビューを反映している。列の名前や型は、実装のときに変えてよい。
ただし **「記録を 1 つのテーブルにまとめる」「家族に出すものは共通の関数を通す」** は変えない。

- id はすべて `bigint`（自動の連番）。日時は `timestamptz`（UTC で保存し、日本時間で判断する。[research.md R-14](./research.md#r-14-時刻と当日)）。
- 「担当」はテーブルを作る人。「時期」は、Day 1〜3 のミニマム版で作るか、Day 4 以降の作り込みで作るか（PR #17 さとこ）。

## テーブルの一覧

| テーブル | 中身 | 担当 | 時期 | spec |
|---|---|---|---|---|
| `facilities` | 施設（1 つだけ） | ようこ | ミニマム | Assumptions |
| `users` | ログインの情報（職員は ID、家族はメールアドレス） | ようこ | ミニマム | R-01 |
| `residents` | 入居者 | ようこ | ミニマム | Key Entities |
| `family_accounts` | 家族アカウント（入居者に 1 つ） | ようこ | ミニマム | Key Entities |
| `staff` | 職員と役割 | ようこ | ミニマム | Key Entities |
| `invitations` | 家族の招待 | ようこ | 作り込み | Assumptions |
| `care_records` | 連絡帳の記録（食事量・機嫌・眠り） | ゆう | ミニマム | FR-001・FR-002・FR-022 |
| `care_record_histories` | 記録の修正の履歴 | ゆう | ミニマム | FR-005 |
| `themes` | 「知りたいこと」のテーマ | ゆう | ミニマム | FR-013 |
| `reply_templates` | テーマごとの定型文 | ゆう | ミニマム | FR-030 |
| `disclosure_settings` | 開示設定（記録項目・テーマごと） | ゆう | ミニマム | FR-009 |
| `disclosure_setting_histories` | 開示設定の変更履歴 | ゆう | 作り込み | FR-011 |
| `requests` | 家族のリクエスト | さとこ | ミニマム | FR-013・FR-014 |
| `replies` | 職員の返事 | ゆう | ミニマム | FR-030 |
| `notifications` | 家族のお知らせ一覧（アプリ内） | さとこ | ミニマム（返事のお知らせ） | FR-023・FR-034 |
| `email_outbox` | メールの送る予定 | さとこ | ミニマム（返事のメール） | FR-023（[research.md R-09](./research.md#r-09-メールとアプリ内のお知らせの送り方)） |
| `uploaded_files` | アップロードしたファイル（共通） | さとこ | ミニマム（ローカル保存、形式と大きさの確認だけ） | FR-004・FR-034（R-10） |
| `monthly_menus` | 月ごとの献立表 | さとこ | ミニマム | FR-004・FR-033 |
| `notification_settings` | 通知設定 | さとこ | 作り込み | FR-023 |
| `digest_runs` | まとめを作った記録（2 回送らないため） | さとこ | 作り込み | FR-023（R-13） |
| `facility_announcements` | 施設からのお知らせ | さとこ | 作り込み | FR-034 |

ミニマム版では、通知設定がない家族は「返事を通知する・頻度は 1 日 1 回」として扱う（FR-023 の初期値）。

## 共通の土台（ようこ）

ようこが Day 1 の午前に作る。`users` の細かい形はようこが決めて共有する（PR #17 ようこ）。

### `facilities`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| name | text | 施設名（架空） |

- J（決済、spec 002）で、Stripe の契約状態・顧客 ID の列を足す（ようこ）。

### `users`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| kind | text | `staff`／`family` |
| login_id | text | 職員がログインに使う ID（職員だけ）。一意 |
| email | text | 家族がログインと通知に使うメールアドレス（家族だけ。代表者）。一意 |
| password_hash | text | bcrypt |
| language | text | `ja`／`id`／`en`（初期値 `ja`） |
| created_at | timestamptz | |

### `residents`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | |
| name | text | 氏名（架空） |
| display_name | text | 表示用の呼び名（例：「佐藤さんの母」） |
| room | text | 居室 |

### `family_accounts`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| user_id | bigint → users | |
| resident_id | bigint → residents | **一意**（入居者に 1 つ。Session 2026-10-20） |

### `staff`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| user_id | bigint → users | |
| facility_id | bigint → facilities | |
| display_name | text | 返事に出す名前（FR-030） |
| role | text | `care_worker`（介護職員）／`leader`（リーダー）／`counselor`（生活相談員）／`clerk`（事務員）／`director`（施設長） |

- 職員のアカウントは、管理画面で作って初期パスワードを渡す（招待はしない。[research.md R-01](./research.md#r-01-職員のログインの仕方)）。

### `invitations`（家族だけ）
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| token_hash | text | 1 回だけ使えるトークンのハッシュ |
| family_account_id | bigint → family_accounts | |
| expires_at | timestamptz | 7 日後 |
| used_at | timestamptz | 使ったら入れる |

### ログイン中の人（各自の API が受け取る形）

仮のログインの時点で決め、Day 2 に本物のログインに差し替えても各自のコードを直さずに済むようにする（開発前MTG）。

```text
CurrentUser:
  user_id
  kind          staff／family
  role          職員の役割（家族は空）
  resident_id   家族なら、紐づいた入居者
  language
```

## 記録（ゆう）

### `care_records`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| resident_id | bigint → residents | |
| date | date | 連絡帳の日付（日本時間）。**眠りは記録した朝の日付**（[research.md R-05](./research.md#r-05-眠りの日付)） |
| item | text | `meal`（食事量）／`mood`（機嫌・様子）／`sleep`（眠り） |
| slot | text | 食事：`breakfast`／`lunch`／`dinner`／`snack`。機嫌・眠り：`day` |
| value | text | 下の表 |
| note | text | 備考（100 文字まで、任意）。食事のときだけ使う（代替メニューなど。FR-035）。辞書を通さずそのまま出す |
| recorded_by | bigint → staff | |
| recorded_at | timestamptz | |
| deleted_at | timestamptz | 当日中に取り消したら入れる |
| deleted_by | bigint → staff | |

| item | value |
|---|---|
| meal | `10`（全部）／`8`（ほぼ全部）／`5`（半分）／`2`（少し）／`0`（食べていない）／`none`（食事なし。外泊・入院など） |
| mood | `smile`（笑顔が多い）／`normal`（いつもどおり）／`low`（元気がない） |
| sleep | `good`（よく眠れた）／`normal`（いつもどおり）／`poor`（あまり眠れなかった） |

- **一意**：`(resident_id, date, item, slot) WHERE deleted_at IS NULL`（部分インデックス。取り消したあとに記録し直せる。[research.md R-04](./research.md#r-04-記録のテーブルを-1-つにまとめる)）
- 押し直したら `value`・`note` を上書きし、前の値を `care_record_histories` に残す（FR-005）。
- 取り消し・修正できるのは、`date` が今日（日本時間）の記録だけ（エッジケース）。
- 画面に出す文言は、`value` のコードから辞書で引く（[research.md R-11](./research.md#r-11-多言語とふりがな)）。

### `care_record_histories`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| care_record_id | bigint → care_records | |
| old_value / new_value | text | 取り消しは `new_value` を空にする |
| old_note / new_note | text | 備考の変更（食事のときだけ） |
| changed_by | bigint → staff | |
| changed_at | timestamptz | |

## 開示設定（ゆう）

### `themes`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| code | text | 一意。辞書のキー（例：`theme.daily_life`） |
| emoji | text | 例：👀 |
| sort_order | int | |

初期データは 8 個（FR-013）：普段の様子／楽しく過ごせているか／他の入居者との関わり／食事の様子／スタッフとの関わり／レクリエーションの様子／家族の話をしているか／足りないものがないか。

### `reply_templates`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| theme_id | bigint → themes | テーマごとに 3〜5 個（FR-030） |
| code | text | 一意。辞書のキー（例：`template.daily_life.smile`） |
| sort_order | int | |

### `disclosure_settings`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | |
| target_type | text | `item`（記録項目）／`theme`（テーマ） |
| target_code | text | `meal`・`mood`・`sleep`、またはテーマの code |
| visible | boolean | 初期値はすべて `true`（FR-009） |
| updated_by / updated_at | | |

- **一意**：`(facility_id, target_type, target_code)`
- 献立表は記録項目ではないので、ここには入れない（常に見せる。FR-009）。
- 共通の関数 3 つは、開示設定を Redis のキャッシュ（`cache:disclosure:<施設ID>`、期限 5 分）から読む。**開示設定を保存したら、そのキャッシュを必ず消す**。
  家族の連絡帳（組み立て結果）はキャッシュしない（[research.md R-12](./research.md#r-12-redis-の使い道課題要件のキャッシュサーバー)、開発前MTG の決定事項）。

### `disclosure_setting_histories`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| target_type / target_code | text | |
| old_visible / new_visible | boolean | |
| changed_by | bigint → staff | |
| changed_at | timestamptz | |

### 家族に出すときの共通の関数

置き場所：`backend/app/services/disclosure.py`。作る人：ゆう（[research.md R-06](./research.md#r-06-家族に出すときの共通の関数)）。

| 関数 | 返すもの | 使う人 |
|---|---|---|
| `get_disclosed_records(resident_id, date_from, date_to, items=None)` | 開示済みの、取り消していない記録。id・日付・項目・区分・値・記録した時刻・記録した職員の表示名。`items` で項目を絞れる | さとこ（連絡帳・20 時のまとめ）、みさき（F） |
| `get_disclosed_themes()` | 開示済みの「知りたいこと」のテーマ | さとこ（テーマのボタン） |
| `get_active_replies(resident_id, date_from, date_to)` | 保存された返事（返事は取り消せないため、すべて有効）。テーマ・定型文のコード・短い文・職員の表示名・時刻・既読か | さとこ（連絡帳）、みさき（F、読む場合） |

- **家族に出すもの（連絡帳・テーマのボタン・通知のまとめ・F の AI のツール）は、必ずこの 3 つを通す**。職員向け（記録画面・見返し・E）は、非開示の項目も含めて直接読んでよい。
- `resident_id` は、呼び出す側がログイン中の家族（`CurrentUser.resident_id`）から決める。家族が送ってきた値は使わない（FR-020）。

## リクエストと返事（さとこ・ゆう）

### `requests`（さとこ）
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| resident_id | bigint → residents | 家族アカウントは入居者に 1 つなので、家族はここから分かる |
| theme_id | bigint → themes | |
| status | text | `waiting`／`answered`／`cancelled` |
| created_at | timestamptz | 送った日時（送ってからの日数も、ここから出す） |
| cancelled_at | timestamptz | 家族が取り消したら入れる |

- **一意**：`(resident_id, theme_id) WHERE status = 'waiting'`（同じテーマは 1 件まで。FR-014。[research.md R-08](./research.md#r-08-返事待ちの上限3-件同じテーマ-1-件)）
- 返事待ちの 3 件の上限は、作るときに `family_accounts` の行を `FOR UPDATE` で押さえて数える。
- 送ってから 3 日（72 時間）たっても `waiting` なら、家族の画面に「お急ぎのときは、施設にお電話ください」を出す（FR-014）。

### 状態の動き

```text
             職員が返事（最初の 1 人だけ。R-07）
 waiting ───────────────────────────────→ answered（当日中なら返事を直せる。waiting には戻らない）
   │
   └── 家族が取り消す（返事の前だけ） ──→ cancelled
```

- 返事の取り消しはしない（FR-030。PR #17 ゆう）。`answered` から `waiting` に戻すと、家族がすでに同じテーマで新しく頼んでいた場合に、
  同じテーマの返事待ちが 2 件になって一意制約とぶつかり、返事待ちが 3 件を超えることもあるため。

### `replies`（ゆう）
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| request_id | bigint → requests | |
| template_ids | bigint[] | 選んだ定型文（1 つ以上） |
| note | text | 書き足した短い文（100 文字まで、任意）。辞書を通さずそのまま出す |
| replied_by | bigint → staff | |
| replied_at | timestamptz | |
| contact_book_date | date | 返事が入る連絡帳の日付（返事をした日、日本時間） |
| edited_at | timestamptz | 当日中に直したら入れる（未読には戻さない。再通知しない） |
| read_at | timestamptz | 家族が読んだ時刻（家族で共有。FR-015） |

- **一意**：`(request_id)`（1 つのリクエストへの返事は 1 つだけ。返事は取り消さない）
- 当日中に直すときは、`template_ids`・`note` を上書きし、`edited_at` を入れる（前の内容は残さない。FR-030 は履歴を求めていない）。
- 保存は `requests` の条件つきの更新と同じトランザクションで行う（[research.md R-07](./research.md#r-07-最初に保存された返事だけを有効にする)）。
- 保存するときに、同じ DB のセッションを渡して、さとこの `create_reply_notice(session, reply_id)` を呼ぶ（関数の中では commit しない。直すときは呼ばない。R-09）。

## 通知（さとこ）

### `notifications`（家族のお知らせ一覧）
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| family_account_id | bigint → family_accounts | |
| kind | text | `reply`／`daily_digest`／`weekly_digest`／`announcement` |
| reply_id | bigint → replies | kind が `reply` のとき |
| announcement_id | bigint → facility_announcements | kind が `announcement` のとき |
| period_start / period_end | timestamptz | まとめのとき（`digest_runs` と同じ型） |
| created_at | timestamptz | |
| read_at | timestamptz | |

- 施設からのお知らせは、家族の一覧を出すときに `facility_announcements`（取り消していないもの）も合わせて並べる。
  そのため、投稿したあとに招待された家族にも過去のお知らせが全件出る（FR-034）。`notifications` の `announcement` は既読を持つためのもの。

### `email_outbox`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| to_email | text | |
| template | text | `reply`／`daily_digest`／`weekly_digest`／`announcement`／`invitation`／`owner_account`（spec 002：施設長のログイン用の ID を知らせる。作り込み） |
| params | jsonb | **種類・お知らせのタイトル・リンクだけ**。記録・返事・本文は入れない（SC-010）。例外：`owner_account` だけは `login_id` を入れる（spec 002 の research.md R-08） |
| created_at | timestamptz | |
| sent_at | timestamptz | 送れたら入れる |
| attempts | int | 失敗した回数（5 回まで） |
| last_error | text | |

- worker は `sent_at IS NULL` の行を `FOR UPDATE SKIP LOCKED` で取り出す（同じメールを 2 回送らない。R-09）。

### `notification_settings`（作り込み）
| 列 | 型 | 説明 |
|---|---|---|
| family_account_id | bigint → family_accounts | 主キー |
| notify_reply | boolean | 知りたいことへの返事（初期値 `true`） |
| notify_items | text[] | 通知する記録項目（初期値 `{meal,mood,sleep}`）。非開示の項目は、まとめを作るときに除く |
| frequency | text | `daily`（初期値）／`weekly`／`none` |

### `digest_runs`（作り込み）
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| family_account_id | bigint → family_accounts | |
| kind | text | `daily`／`weekly` |
| period_end | timestamptz | まとめの終わりの時刻（その日の 20:00） |

- **一意**：`(family_account_id, kind, period_end)`（同じまとめを 2 回送らない。[research.md R-13](./research.md#r-13-1-日-1-回1-週間に-1-回のまとめ)）

## ファイル・献立表・施設からのお知らせ（さとこ）

### `uploaded_files`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| storage_key | text | 保存先の中の名前（推測できないランダムな文字列） |
| content_type | text | `application/pdf`／`image/jpeg`／`image/png`（先頭のバイトで確かめた形式） |
| size_bytes | int | 10MB まで |
| purpose | text | `menu`／`announcement`（あとで `album`） |
| uploaded_by | bigint → staff | |
| uploaded_at | timestamptz | |

### `monthly_menus`
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | |
| year_month | text | `2026-11` |
| file_id | bigint → uploaded_files | アップロードし直したら新しいファイルに置き換える |
| uploaded_by / uploaded_at | | |

- **一意**：`(facility_id, year_month)`

### `facility_announcements`（作り込み）
| 列 | 型 | 説明 |
|---|---|---|
| id | bigint | |
| facility_id | bigint → facilities | |
| title | varchar(40) | |
| body | varchar(1000) | 辞書を通さずそのまま出す |
| file_id | bigint → uploaded_files | 任意・1 つ |
| posted_by / posted_at | | |
| cancelled_by / cancelled_at | | 事務員・相談員・施設長なら誰でも取り消せる。取り消したら添付も開けなくする |

## ファイルを開ける人

| ファイル | 開ける人 |
|---|---|
| 献立表 | ログインした家族・職員（すべて） |
| お知らせの添付 | ログインした家族・職員。お知らせが取り消されていたら、誰も開けない |

## F（みさき）で足すテーブル

spec 001 の範囲外だが、つながりのために書いておく（開発前MTG）：`inquiries`（問い合わせの履歴と、使った記録の id）、`escalations`（相談員に回したもの）。F の spec で決める。
