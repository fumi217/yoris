# API Contract: spec 001

フロントエンドとバックエンドの間の API の一覧と決まりごと。正式な定義は、FastAPI が出す OpenAPI（`/openapi.json`）とし、
フロントの型はそこから作る（[research.md R-16](../research.md#r-16-api-の型の共有)）。この文書は、作り始める前に分担と形をそろえるためのもの。
担当は [plan.md](../plan.md#担当とつながり作業分担mtg開発前mtg-の案より) と開発前MTG の案に合わせている。

## 共通の決まり

- 先頭は `/api`。JSON でやりとりする（ファイルのアップロードだけ `multipart/form-data`）。
- ログインはセッションの Cookie（[research.md R-03](../research.md#r-03-ログインとセッション)）。書き込み（POST・PUT・PATCH・DELETE）は `X-Requested-With: fetch` ヘッダーを付ける。
- **入居者は、家族の API では指定させない**。ログイン中の家族アカウントから決める（FR-020）。
- 家族に出す記録・テーマ・返事は、すべて共通の関数（`get_disclosed_records`・`get_disclosed_themes`・`get_active_replies`）を通す（[data-model.md](../data-model.md#家族に出すときの共通の関数)）。
- 文言は返さず、**コード**で返す（`value: "smile"`、`theme_code: "theme.daily_life"` など）。画面で辞書から引く（R-11）。
  職員が書いた `note`、お知らせの `title`・`body` は、そのまま返す。
- 日付は `YYYY-MM-DD`（日本時間の日付）、日時は ISO 8601（UTC）。

### エラーの形

```json
{ "error": { "code": "request_limit", "message_key": "error.request_limit" } }
```

| HTTP | code | いつ | spec |
|---|---|---|---|
| 401 | `not_logged_in` | ログインしていない（ファイルの URL を直接開いたときも） | FR-034 |
| 429 | `too_many_attempts` | ログインの試行回数が多すぎる（作り込み） | research.md R-03 |
| 403 | `forbidden` | 役割がない（家族が職員・管理画面の API を呼んだ、など） | FR-024 |
| 404 | `not_found` | ほかの家族のもの・ないものを id で指定した（存在するかどうかも知らせない。下の「家族の画面」の決まり） | FR-020 |
| 409 | `request_limit` | 返事待ちが 3 件ある | FR-014 |
| 409 | `theme_waiting` | 同じテーマの返事待ちがある | FR-014 |
| 409 | `already_replied` | ほかの職員が先に返事した | FR-030 |
| 409 | `request_cancelled` | 家族がリクエストを取り消していた | Edge Cases |
| 409 | `not_today` | 当日ではない記録・返事を直そうとした | FR-030・Edge Cases |
| 422 | `invalid_file` | 形式が PDF・JPG・PNG でない、10MB を超える | FR-034 |
| 422 | `validation_error` | 文字数（返事 100、タイトル 40、本文 1,000）など | FR-030・FR-034 |

### 役割の略号

`F` 家族、`CW` 介護職員、`L` リーダー、`CO` 生活相談員、`CL` 事務員、`D` 施設長

### 時期の略号

`ミ` ミニマム版（Day 1〜3）、`作` 作り込み（Day 4〜）。[data-model.md](../data-model.md#テーブルの一覧) の時期と合わせている。

## ログイン・アカウント（ようこ）

ブラウザからは、フロントと同じオリジンの `/api` を呼ぶ（開発は Vite の proxy、本番は中継。CORS は開けない。[research.md R-03](../research.md#r-03-ログインとセッション)）。

| メソッド・パス | 役割 | 時期 | 中身 |
|---|---|---|---|
| `POST /api/auth/login` | だれでも | ミ | 職員は ID、家族はメールアドレスと、パスワードでログイン |
| `POST /api/auth/logout` | ログイン中 | ミ | ログアウト（セッションをすぐ消す） |
| `GET /api/me` | ログイン中 | ミ | 自分の種類（家族／職員）・役割・表示名・表示言語 |
| `PUT /api/me/language` | ログイン中 | 作 | 表示言語を変える（`ja`／`id`／`en`。FR-021） |
| `POST /api/admin/staff` | CO・D | 作 | 職員のアカウントを作る（ID と初期パスワード。ミニマム版は初期データ） |
| `POST /api/admin/invitations` | CO・D | 作 | 家族を招待する（招待のメールを送る） |
| `POST /api/invitations/accept` | だれでも | 作 | 招待を受けてパスワードを決める。トークンは本文で送る（メールのリンクは `#token=` の形） |
| `POST /api/dev/switch-user` | 開発環境だけ | ミ | 初期データの人としてログインする（本番では存在しない。`APP_ENV` がなければ本番扱い。R-02） |

- 職員は操作がないまま 30 分で自動ログアウト、家族は 30 日（R-01。作り込み）。

## 職員の画面（ゆう）

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/staff/residents?date=` | CW・L・CO・D | ミ | 入居者の一覧。食事区分ごとの記録済み／未記録、返事待ちのリクエストの件数 | FR-008・FR-029 |
| `GET /api/staff/residents/{id}/contact-book?date=` | CW・L・CO・D | ミ | その日の記録と返事を時刻順に（非開示も含む。職員向け） | FR-024 |
| `PUT /api/staff/residents/{id}/records` | CW・L・CO・D | ミ | 記録する・押し直す（`date`・`item`・`slot`・`value`）。`date` は今日から 3 日前まで（範囲外は 422 `validation_error`）。押し直しは今日の記録だけ（409 `not_today`） | FR-001・FR-002・FR-005・FR-022 |
| `DELETE /api/staff/records/{record_id}` | CW・L・CO・D | 作 | 当日中に取り消す | Edge Cases |
| `GET /api/staff/residents/{id}/requests` | CW・L・CO・D | ミ | 返事待ちのリクエスト（テーマ・送られた日・日数・定型文の一覧） | FR-029 |
| `POST /api/staff/requests/{id}/reply` | CW・L・CO・D | ミ | 返事をする（`template_ids`・`note`）。409：`already_replied`・`request_cancelled` | FR-030 |
| `PATCH /api/staff/replies/{reply_id}` | CW・L・CO・D | 作 | 当日中に直す（再通知しない） | FR-030 |

## 開示設定（ゆう）

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/admin/disclosure` | CO・D | ミ | 記録項目とテーマの、見せる／見せない。関係しそうな組み合わせの注意書きのコード（作り込み） | FR-009 |
| `PUT /api/admin/disclosure` | CO・D | ミ | 変える | FR-009・FR-012 |
| `GET /api/admin/disclosure/history` | CO・D | 作 | 変更履歴（いつ・誰が・何を） | FR-011 |

## 家族の画面（さとこ）

API の名前は開発前MTG に合わせて `contact-book`（連絡帳）にする。

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/family/contact-book?date=` | F | ミ | その日の連絡帳。まだ読んでいない返事を（日付に関わらず）先頭に、開示済みの記録（食事 → 機嫌・様子 → 眠り）、未記録の欄 | FR-015・FR-017・FR-019 |
| `GET /api/family/themes` | F | ミ | 頼めるテーマ（`get_disclosed_themes` を通す） | FR-013 |
| `GET /api/family/requests` | F | ミ | 送ったリクエスト（状態・送った日時・日数・3 日たったか） | FR-014 |
| `POST /api/family/requests` | F | ミ | テーマを選んで送る（`theme_id`）。409：`request_limit`・`theme_waiting` | FR-013・FR-014 |
| `DELETE /api/family/requests/{id}` | F | ミ | 返事の前に取り消す | FR-014 |
| `POST /api/family/replies/{reply_id}/read` | F | ミ | 返事を読んだ（家族で共有）。返事のカードが画面に出たら、フロントが自動で呼ぶ（R-15） | FR-015 |
| `GET /api/family/notifications` | F | ミ | お知らせの一覧（返事・まとめ・施設からのお知らせ） | FR-023・FR-034 |
| `POST /api/family/notifications/{id}/read` | F | 作 | お知らせを読んだ | FR-023 |
| `GET /api/family/notification-settings` | F | 作 | 通知設定と送り先のメールアドレス | FR-023 |
| `PUT /api/family/notification-settings` | F | 作 | 通知設定を変える（`notify_reply`・`notify_items`・`frequency`） | FR-023 |
| `GET /api/family/announcements/{id}` | F | 作 | 施設からのお知らせの本文と添付 | FR-034 |

- id で指定する API（`requests/{id}`・`replies/{id}`・`notifications/{id}`・`announcements/{id}`）は、ログイン中の家族のものかを必ず確かめる（id は連番で推測できるため。ほかの家族のものは 404）。

## 施設からのお知らせ（さとこ。毎月の献立表も、お知らせの添付で出す）

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/admin/announcements` | CL・CO・D | 作 | 投稿したお知らせの一覧 | FR-034 |
| `POST /api/admin/announcements` | CL・CO・D | 作 | 投稿する（`title`・`body`・ファイル 1 つまで）。全家族にお知らせとメールの送る予定を作る | FR-034 |
| `DELETE /api/admin/announcements/{id}` | CL・CO・D | 作 | 取り消す（だれが投稿したものでも） | FR-034 |

## ファイル（さとこ。役割のチェックはようこの仕組みを使う）

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/files/{id}` | ログイン中の家族・職員 | 作 | ファイルを返す。ログインしていなければ 401、取り消したお知らせの添付は 404。`Content-Type` 固定、`X-Content-Type-Options: nosniff`。PDF は Day 3 の確認しだいで `Content-Disposition: attachment`（R-10） | FR-025・FR-034 |

## 決まった時刻の処理

本番で、外部のスケジューラー（cron-job.org）が 1 分ごとに呼ぶ（[research.md R-09](../research.md#r-09-メールとアプリ内のお知らせの送り方)）。開発では `worker` が同じ `run_jobs()` を直接呼ぶので、この API は使わない。

| メソッド・パス | 呼ぶもの | 時期 | 中身 |
|---|---|---|---|
| `POST /api/internal/jobs/run` | 外部のスケジューラー（ログインなし） | ミ（本番デプロイのとき） | `run_jobs()` を 1 回動かす。返すのは `204` だけ（何を送ったかは返さない） |

- `Authorization: Bearer <JOBS_TOKEN>` がないか違えば **401**。比べるときは `hmac.compare_digest` を使う。環境変数 `JOBS_TOKEN` が空のとき（開発など）は、ルーターを登録せず **404**。
- `JOBS_TOKEN` は 32 バイト以上のランダムな値にし、Render と cron-job.org の設定にだけ置く。ログ・応答に出さない。
- ブラウザから呼ぶ API ではないので、書き込みの確認（`X-Requested-With`、T014）の対象から外す（合言葉で確かめる）。
- 1 回の処理は 30 秒以内に終える（送るメールは 1 回に数十件まで）。

## メール

API ではないが、送るメールの種類と、テンプレートに渡すものを決めておく（[research.md R-09](../research.md#r-09-メールとアプリ内のお知らせの送り方)）。

| 種類 | 件名の例 | テンプレートに渡すもの |
|---|---|---|
| `reply` | 知りたいことへの返事が届きました | リンクだけ |
| `daily_digest` | 今日の連絡帳がまとまりました | リンクだけ |
| `weekly_digest` | 今週の連絡帳がまとまりました | リンクだけ |
| `announcement` | 施設からのお知らせ：（タイトル） | タイトル・リンク（本文・添付は渡さない） |
| `invitation` | 連絡帳アプリへの招待 | 招待のリンク |
