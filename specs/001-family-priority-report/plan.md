# Implementation Plan: 家族の「知りたいこと」に職員が答える連絡帳（スプリント1: C→B→A）

**Branch**: `docs/spec-001-plan`（フォルダ名は `001-family-priority-report` のまま） | **Date**: 2026-10-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-family-priority-report/spec.md`

## Summary

介護職員がお世話の場でタブレットからボタンで記録した連絡帳（食事量・機嫌・様子・眠り）を、施設が開示設定で絞り込み、
家族がスマートフォンで見られるようにする。家族は「知りたいこと」をテーマのボタンで頼み、職員は定型文のボタンで返事をする。
返事と、1 日 1 回・週 1 回のまとめ、施設からのお知らせは、アプリ内のお知らせとメールで届ける。お知らせの添付は、
ファイルをアップロードして、ログインした人だけが開ける。

技術の進め方は、技術選定で決めた **FastAPI ＋ SQLAlchemy ＋ PostgreSQL ＋ Redis（バックエンド）**、
**React（Vite）＋ react-i18next（フロントエンド）** で作る。次の 3 つを設計の柱にする（詳しくは [research.md](./research.md)）。

1. **家族に出すものは、必ず共通の関数を通す**：連絡帳・テーマのボタン・通知のまとめ・AI（F）は、記録を直接読まず
   `get_disclosed_records`・`get_disclosed_themes`・`get_active_replies` から取る（Constitution 原則 IV を 1 か所で守る）
2. **メールは「送る予定」を DB に書いてから、別のプロセスが送る**（アウトボックス）：返事・お知らせは 5 分以内、まとめは 20 時に 1 回だけ、を同じ仕組みで守る
3. **ファイルは公開 URL を持たない**：お知らせの添付は、バックエンドがログインと役割を確かめてから返す

## Technical Context

**Language/Version**: Python 3.13（バックエンド）、TypeScript 6・Node 24（フロントエンド）。版を決めた理由は docs/技術選定.md の 7 章

**Primary Dependencies**:
- バックエンド：FastAPI、SQLAlchemy 2、Alembic（マイグレーション）、Pydantic 2、redis-py、Pillow（画像の Exif の削除）、structlog（ログ）
- フロントエンド：React 18（Vite）、React Router、TanStack Query、react-i18next、Tailwind CSS
- 型の共有：FastAPI が出す OpenAPI から、`openapi-typescript` でフロントの型を作る

**Storage**:
- PostgreSQL：記録・返事・開示設定・お知らせ・メールの送信予定など、すべての業務データ
- Redis：ログインのセッションと、開示設定のキャッシュ（期限 5 分）。家族の連絡帳はキャッシュしない（開発前MTG の決定事項）。作り込みで、ログインの試行回数の制限を足す（[research.md R-12](./research.md#r-12-redis-の使い道課題要件のキャッシュサーバー)）
- ファイル：開発はコンテナのボリューム、本番は S3 互換のオブジェクトストレージ（[research.md R-10](./research.md#r-10-ファイルの保存先と配り方)）

**Testing**: pytest ＋ httpx2（バックエンドの単体・API）、Vitest（フロントエンドの単体）、Playwright（E2E。受け入れシナリオから作る）

**Target Platform**: Docker Compose（開発：frontend・backend・worker・PostgreSQL・Redis・Mailpit）、Render（本番。コンテナのまま。無料のプランなので worker は置かず、決まった時刻の処理は外部のスケジューラーが API を呼ぶ。[research.md R-09](./research.md#r-09-メールとアプリ内のお知らせの送り方)）。
ブラウザからは `/api` をフロントと同じオリジンで呼び、バックエンドへ中継する（Cookie を確実に送るため。[research.md R-03](./research.md#r-03-ログインとセッション)）。
家族はスマートフォンのブラウザ、職員は施設のタブレットのブラウザ

**Project Type**: Web アプリケーション（`frontend/` と `backend/` を分ける。課題要件）

**Performance Goals**:
- 職員の記録と返事が、家族の連絡帳に 5 分以内に出る（SC-008。実際は画面を開いたときに最新を読むので、ほぼすぐ出る）
- 返事・施設からのお知らせのメールとアプリ内のお知らせが 5 分以内に届く（SC-010・SC-016）
- 1 食分の記録が 3 タップ以内・10 秒以内（SC-003）

**Constraints**:
- 家族に出す道（画面・通知・AI）に、非開示の記録を 1 件も出さない（SC-006）
- メール・アプリ内のお知らせに、記録や返事の中身を入れない（SC-010）
- 本番のログに、氏名・記録の中身・返事の中身を出さない（FR-027）
- 「当日」「20 時」「日曜」は日本時間（Asia/Tokyo）で数える

**Scale/Scope**: 施設 1 つ、入居者 30 人、職員 16 人、家族アカウント 30（入居者 1 人に 1 つ）。
画面は家族向け 約 6、職員向け 約 4、管理画面 約 5

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 の前

| 原則・制約 | 確認 | 結果 |
|---|---|---|
| I. 日々の様子と知りたいことを、聞かずに・遠慮せずに知れる | 頼まなくても開示した記録が連絡帳で見られる（US1・US2）。テーマのボタンで頼めて、届いたことが分かる（FR-013・FR-014）。返事が届いているときはファーストビューに出す（FR-015）。未記録は「まだ記録されていません」（FR-017） | ✅ |
| II. 職員の入力負担を増やさない | 記録も返事もボタンで 3 タップ以内（FR-006・FR-030）。自由記述は任意の書き足しだけ。リクエストは職員に通知・音を出さない（FR-029・SC-013）。家族のための追加入力は返事だけ（FR-016） | ✅ |
| III. AI は医療判断をせず、記録にないことは答えない | この spec では AI を使わない（F・D・E は別の spec）。ただし AI が読む道を `get_disclosed_records` に限ることで、F の土台を先に作る | ✅（対象外。土台のみ） |
| IV. 開示は施設が選ぶ | 記録項目とテーマを施設が項目単位で選ぶ（FR-009）。非開示は家族のどこにも出さない（FR-010）。変更履歴を残す（FR-011）。家族は自分の入居者だけ（FR-020） | ✅ |
| V. 10 日間で動くものを優先 | US1〜US5 はそれぞれ単独でデモできる。スコープ外の機能は入れていない。新しく足すライブラリは技術選定の表にあるもの＋Pillow・Alembic・openapi-typescript だけ（理由は research.md） | ✅ |
| UI 方針 | 固定の文言はやさしい日本語＋すべての漢字にふりがな、訳したときはふりがななし。家族の画面と施設の申し込みの画面は、ふりがなを付けない（constitution 3.2.0 の例外。#260）（FR-021、research.md R-11） | ✅ |
| 利用者と権限 | 家族・介護職員・リーダー・生活相談員・事務員・施設長を分け、API ごとに開ける役割を決める（[contracts/api.md](./contracts/api.md)） | ✅ |
| 個人情報 | 架空データだけを使う。通信は https。ファイルは公開 URL を持たない | ✅ |
| 課題要件：構成・コンテナ・キャッシュ | `frontend/`・`backend/` を分ける。Docker Compose。Redis をセッションと開示設定のキャッシュに使う（連絡帳はキャッシュしない） | ✅ |
| 課題要件：AI Agent・決済 | この spec の範囲外（F・J は別の spec。原則 V により 1 週目のうちに最小版を動かす） | ✅（別 spec） |
| 課題要件：セキュリティ | 自由に書かれた文は React の通常の表示（エスケープ）だけで出し、HTML として埋め込まない。SQL は ORM でパラメータ化。ファイルは中身の形式を確かめ、画面の一部として実行させない（FR-025・FR-026） | ✅ |
| 課題要件：テスト・ログ | pytest・Vitest・Playwright。structlog で開発は読みやすく、本番は JSON で個人情報を伏せる | ✅ |

**違反なし**。Complexity Tracking は空。

### Phase 1 のあと（設計後の確認）

| 確認したこと | 結果 |
|---|---|
| 家族向けの API（連絡帳・テーマ・通知のまとめ）は、すべて共通の関数 3 つを通る設計になっている（[data-model.md](./data-model.md#家族に出すときの共通の関数)） | ✅ |
| 開示設定のキャッシュは、設定を保存したときに必ず消し、期限（5 分）も付ける。家族の連絡帳はキャッシュしない（古いキャッシュで非開示が出ない。課題要件のキャッシュの注意。research.md R-12） | ✅ |
| 職員向けの API に、家族のロールでは入れない（[contracts/api.md](./contracts/api.md) の役割の列） | ✅ |
| メールの文面のテンプレートに、記録・返事・お知らせ本文の変数を渡さない設計になっている | ✅ |
| 増えたライブラリは Pillow・Alembic・openapi-typescript の 3 つだけで、10 日間で使える根拠を research.md に書いた | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/001-family-priority-report/
├── spec.md              # 仕様（/speckit-specify・clarify）
├── plan.md              # この文書
├── research.md          # 調べて決めたこと（Phase 0）
├── data-model.md        # テーブルの形・状態の動き（Phase 1）
├── quickstart.md        # 動かし方と、通しの確認手順（Phase 1）
├── contracts/
│   └── api.md           # API の一覧と決まりごと（Phase 1）
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks で作る（この plan では作らない）
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                 # FastAPI の入口、ルーターの登録
│   ├── config.py               # 環境変数（DB・Redis・メール・ファイルの保存先）
│   ├── db.py                   # SQLAlchemy のセッション
│   ├── auth/                   # ログイン・セッション・役割のチェック・招待（ようこ）
│   ├── models/                 # テーブルの定義（担当ごとにファイルを分ける）
│   ├── api/
│   │   ├── family/             # 家族向けの API（さとこ）
│   │   ├── staff/              # 職員向けの API（ゆう）
│   │   ├── admin/              # 管理画面の API（開示設定：ゆう、お知らせ：さとこ、アカウント：ようこ）
│   │   ├── files.py            # ファイルを返す API（ログインと役割を確かめる）
│   │   └── dev.py              # 開発環境だけのユーザー切り替え
│   ├── services/
│   │   ├── disclosure.py       # 家族に出すときの共通の関数 3 つ（ゆう）
│   │   ├── requests.py         # リクエストと返事の状態の動き
│   │   ├── notifications.py    # お知らせとメールの送信予定を作る
│   │   └── uploads.py          # ファイルの形式チェック・Exif の削除・保存（お知らせ・アルバムで共通）
│   ├── jobs/
│   │   ├── run.py              # run_jobs()：メールを送る・送り直す、20 時のまとめを作る（呼ばれたときに、やることを済ませる）
│   │   ├── worker.py           # 開発だけ：1 分ごとに run_jobs() を呼ぶ（本番は外部のスケジューラーが API を呼ぶ）
│   │   └── digest.py           # まとめ（1 日・1 週間）を作る
│   └── seed/                   # 初期データ（入居者・職員・テーマ・定型文・記録のサンプル）
├── alembic/                    # マイグレーション
└── tests/
    ├── unit/
    └── api/

frontend/
├── src/
│   ├── i18n/
│   │   ├── ja.json / id.json / en.json   # 文言の辞書（日本語にはふりがなの書き方を使う）
│   │   └── Ruby.tsx                      # ふりがなを付けて表示する部品（みさき）
│   ├── api/                    # OpenAPI から作った型と、API を呼ぶ関数
│   ├── pages/
│   │   ├── family/             # 連絡帳・知りたいこと・お知らせ・通知設定（さとこ）
│   │   ├── staff/              # 入居者一覧・記録・返事・その日の連絡帳（ゆう）
│   │   └── admin/              # 開示設定・お知らせ・アカウント（各担当）
│   └── components/
└── tests/
    ├── unit/
    └── e2e/                    # Playwright（ようこ）

docker-compose.yml              # frontend・backend・worker・db・redis・mailpit
```

**Structure Decision**: 課題要件どおり `frontend/` と `backend/` を分けたWeb アプリにする。
担当は README の「体制」と [作業分担MTG](../../docs/context/meeting/作業分担MTG.md) に合わせ、
フォルダを担当ごとに分けて、同じファイルを同時に触らないようにする。
メールの送信と 20 時のまとめは `run_jobs()` にまとめる。開発は `worker` プロセス（同じ backend のイメージを別のコマンドで起動）が 1 分ごとに呼び、
本番は外部のスケジューラー（cron-job.org）が 1 分ごとに `POST /api/internal/jobs/run` を呼ぶ（Render の無料のプランには worker がないため。[research.md R-09](./research.md#r-09-メールとアプリ内のお知らせの送り方)）。

## 担当とつながり（作業分担MTG・開発前MTG の案より）

| 担当 | この spec で作るもの | ほかの人に渡すもの |
|---|---|---|
| ようこ | 環境構築（Docker Compose に `worker`・Mailpit も足す、CI に PostgreSQL と `alembic heads` の確認）、`/api` の中継、ログインと役割、家族の招待、職員のアカウント、開発用のユーザー切り替え、共通のテーブル（施設・`users`・入居者・職員・家族アカウント） | ログイン中の人（`CurrentUser`）を取る依存関数（FastAPI の `Depends`） |
| ゆう | 記録（US1）、開示設定と変更履歴（US2）、職員の返事（US3 の職員側）、その日の連絡帳の見返し | **`get_disclosed_records`・`get_disclosed_themes`・`get_active_replies`**（さとこ・みさきが使う） |
| さとこ | 家族の連絡帳、知りたいこと（US3 の家族側）、通知（お知らせ・メール・まとめ・通知設定）、`worker` の中身（`app/jobs/`）、施設からのお知らせ（US5。毎月の献立表も、この添付で出す） | `create_reply_notice(session, reply_id)`（返事の保存のときにゆうが呼ぶ）、メールを送る部品（招待でようこが使う） |
| みさき | 多言語の辞書とふりがなの部品（全画面で使う）、テーマ・定型文のインドネシア語・英語の訳 | `Ruby` の部品と辞書の書き方 |

## ミニマム版と作り込み

Day 1〜3 のミニマム版で作るものと、Day 4 以降の作り込みで作るもの（PR #17 さとこ）。tasks.md と issue はこの区別で分ける。
ミニマム版の共通ルール（見た目・ふりがな・多言語は後回し、管理画面の代わりに初期データ、正常に動く道だけ、ただし権限のチェックは最初から）は [作業分担MTG](../../docs/context/meeting/作業分担MTG.md) のとおり。

| 担当 | ミニマム版（Day 1〜3） | 作り込み（Day 4〜） |
|---|---|---|
| ようこ | Docker Compose（全コンテナ）、`/api` の中継、共通のテーブル、開発用のユーザー切り替え、本物のログインと Redis のセッション（Day 2） | 職員の自動ログアウト（30 分）、ログインの試行回数の制限、職員のアカウントの管理画面、家族の招待（メール）、パスワードを忘れたとき、CI の `alembic heads` の確認、本番デプロイ |
| ゆう | `care_records`（記録・押し直し・履歴）、テーマ・定型文の初期データ、開示設定の切り替えと共通の関数 3 つ（開示設定のキャッシュを含む）、返事（定型文・最初の 1 人だけ）、入居者一覧（未記録・返事待ちの件数）、その日の連絡帳の見返し | 当日中の記録の取り消し、返事の修正（返事の取り消しはしない）、開示設定の変更履歴、関係しそうな組み合わせの注意書き |
| さとこ | `requests`（送る・取り消す・上限）、家族の連絡帳（返事を一番上に、既読）、返事のお知らせ（`notifications` の `reply` と `email_outbox`、`worker` で Mailpit に送る）、`uploaded_files`（ローカル保存、形式と大きさの確認だけ。作り込み）、ファイルを返す API | `notification_settings`、`digest_runs` と毎日・毎週のまとめ、Exif の削除（Pillow）、オブジェクトストレージ、施設からのお知らせ（添付つき） |
| みさき | 辞書の仕組み（日本語だけ、文言を辞書から引く形）、`Ruby` の部品の土台 | インドネシア語・英語の訳、全画面のふりがな、表示言語の切り替え、ふりがなの付け忘れのテスト（SC-011） |

さとこの作る量が多いため、作り込みは「返事のお知らせ → 通知設定とまとめ → ファイルの共通の処理 → 施設からのお知らせ」の順で進め、遅れそうなときは早めに共有する（PR #17 さとこ）。

## 未決定のこと（plan では仮に置いた）

| 項目 | 仮に置いた内容 | 決める場 |
|---|---|---|
| 開発前MTG の「打ち合わせで決めること」 | 「コメントで決まったこと」（職員は ID でログイン、眠りは記録した朝の日付、時刻は UTC、メール送信の部品はさとこ）と、PR #19 の決定事項（連絡帳はキャッシュせず、開示設定をキャッシュする）に合わせた。残り（F が返事を読むか、Day 1 の issue の立て方、spec がない J・G の扱い、PR の行数のルール）は打ち合わせで決める | 開発前MTG |
| `users` テーブルの細かい形 | 職員は `login_id`、家族は `email` で 1 つのテーブルにまとめる形で書いた（[data-model.md](./data-model.md#users)） | ようこ |
| `/api` の中継の構成 | （決定）開発は Vite の proxy、本番はフロントを Render の Static Site に置き、書き換えのルールで `/api/*` をバックエンドの公開 URL に中継する。無料の Web Service はバックエンドの 1 つだけ（[research.md R-03](./research.md#r-03-ログインとセッション)、PR #34） | ようこ |
| 家族がパスワードを忘れたとき | ミニマム版は施設がもう一度招待する。再設定の画面は作り込みで検討 | ようこ |
| PDF の表示 | `sandbox` は付けず、Day 3 に iPhone の Safari と Android の Chrome で確かめる。表示できなければダウンロードにする（[research.md R-10](./research.md#r-10-ファイルの保存先と配り方)） | さとこ（Day 3） |
| 返事のお知らせの呼び方 | 開発前MTG の案（保存を確定したあとに呼ぶ）ではなく、PR #17 のさとこの提案（同じセッションを渡して呼び、中では commit しない）を採った（[research.md R-09](./research.md#r-09-メールとアプリ内のお知らせの送り方)） | ゆう・さとこ |
| 本番のメール送信サービス・ファイルの保存先 | （決定）メールは本番は Resend の API、開発は Mailpit に SMTP（[PRD](../../docs/PRD.md) 9 章の案 A、PR #28。[research.md R-09](./research.md#r-09-メールとアプリ内のお知らせの送り方)）。ファイルは S3 互換（Cloudflare R2 など） | ようこ（本番デプロイのとき） |

## Complexity Tracking

> Constitution Check に違反はないため、記入なし。
