# CLAUDE.md

介護施設の家族連絡アプリ（連絡帳・知りたいことのリクエスト）のチーム開発リポジトリ。チーム全員の Claude Code が同じ前提で動くよう、作業前にこのファイルに従うこと。

## プロジェクトの前提

- 研修 SEC10・11 の 10 日間（平日）の最終課題。講師に「動くもの」を提出・発表する。
- いちばん大事にすること: 家族が施設に遠慮せず、聞かずに日々の様子と知りたいことを知れること。そのために職員の入力負担を増やさないこと。

## まず読むもの

- どの作業でも: `.specify/memory/constitution.md`（原則 I〜V・課題要件・記録のルール・体制）。このリポジトリのほかのどの文書より優先する。
- 作業内容に応じて読むもの:
  - 機能の仕様（何を・どう動くか）: `specs/<機能>/`（spec・plan・data-model・contracts・tasks）。機能単位の詳細はここが正
  - 全体像（企画・要件・一覧・図）: `docs/`（`docs/PRD.md`・`docs/要件定義.md`・各設計書）
  - その時点の議論・決定の経緯: `docs/context/`（議事録・デイリースクラム・スプリント）
- 機能は SpecKit の流れ（`/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`）で進める。plan では Constitution Check を必ず行う。
- 実装やテストを書く前に、対象の spec の User Story・要件（FR-）・受け入れシナリオを確認し、仕様どおりに作る。仕様にないことや食い違いを見つけたら、推測で実装せずユーザーに確認する。
- 仕様を変えるときは、コードより先に spec・ドキュメントを更新する。constitution の改定はチーム全員の合意が必要なので、Claude だけで決めない。
- 決まったことは、議事録（フロー）に書くだけでなく、該当するストック文書（README・`docs/`・`specs/`・constitution）にも反映する（constitution の「記録のルール」）。

## 技術の前提

`docs/技術選定.md` の要約。理由や比較はそちらを読む（技術選定が正。変えたらここも合わせる）。

| 領域 | 採用技術 |
| --- | --- |
| フロントエンド | Node 24、React（Vite）・TypeScript、React Router、Tailwind CSS、react-i18next（日本語・インドネシア語・英語）、TanStack Query。テストは Vitest、E2E は Playwright、lint は ESLint、整形は Prettier |
| バックエンド | Python 3.13 ＋ FastAPI、SQLAlchemy、Pydantic、structlog、pykakasi（職員のメッセージ画面の自由な文に読みを付ける。spec 004 の FR-028a）。テストは pytest、lint と整形は ruff |
| データ・キャッシュ | PostgreSQL、Redis（セッション・開示設定のキャッシュ・AI 問い合わせの回数制限。作り込みでログインの試行回数の制限） |
| 認証 | バックエンドが発行するセッション（Cookie、Redis に保存）。役割と権限は自前の DB で管理。パスワードは bcrypt（半角の英数字と記号で 8〜64 文字、よく使われるものは不可。spec 001 の research.md R-03） |
| AI | OpenRouter（学校配布のキー）＋ OpenAI Python SDK のツール呼び出し。モデル名は環境変数 |
| 決済 | Stripe Billing（テストモード。実課金はしない） |
| 通知 | アプリ内のお知らせ ＋ メール（開発・デモは Mailpit、本番は Resend の API。決まった時刻の処理は本番では外から API を呼ぶ。spec 001 の research.md R-09） |
| 開発環境・本番 | Docker / Docker Compose。本番は Render（https）。ブラウザからは `/api` をフロントと同じオリジンで呼んで中継し、CORS は開けない（開発は Vite の proxy。本番の具体的な構成はようこが決める。spec 001 の research.md R-03） |

実装で守ること（constitution と技術選定 4〜5 章）:

- AI エージェントのフレームワーク（LangChain など）は使わず、ループを自前で書く。ループには上限回数を付け、超えたら職員に渡す
- AI は医療判断をしない。医療・服薬・体調の解釈・苦情・お金・緊急・記録にないことは `hand_off_to_staff` で質問の種類を付けて職員に渡し、推測で答えない（原則 III は例外なし。だれが対応するかは職員が決める。spec 004）
- 入居者 ID と開示の範囲は、AI に指定させず、サーバーがログイン中の家族から決める。AI のツールは `get_disclosed_records` を通して、その家族に開示された記録しか返さない（原則 IV・プロンプトインジェクション対策）
- 家族に出す記録・テーマ・返事は、必ず共通の関数 `get_disclosed_records`・`get_disclosed_themes`・`get_active_replies`（`backend/app/services/disclosure.py`）を通す。職員向けの画面は直接読んでよい（spec 001 の research.md R-06）
- 家族の連絡帳はキャッシュせず、毎回 DB から組み立てる。開示設定のキャッシュには期限を付け、開示設定を保存したら消す（取り消した記録や非開示の項目が、古いキャッシュから家族に見えないように。期限の長さなどは docs/context/meeting/開発前MTG.md の決定が正）
- OpenRouter の注意点（`tools` を毎回付ける、`provider: {"require_parameters": true}`、最初はストリーミングなし など）は技術選定 5 章に従う
- 業務処理と DB アクセスはバックエンドだけに置く。利用者の入力は表示時にエスケープし（React の自動エスケープを外さない）、DB への問い合わせは ORM でパラメータ化する
- 自動テストでは LLM・Stripe・メールをモックにし、学校配布の API キーを使わない
- 画面の固定の文言には、すべての漢字にふりがなを付ける。ただし、施設の申し込みの画面（申し込み・完了）と、家族の画面（`/family` の下のすべて）は付けない（constitution の UI 方針。辞書での書き方は spec 001 の research.md R-11）
- 開発と本番でログの出し方を分け、ログに個人情報（氏名・連絡先・記録の本文）を出さない
- 新しいライブラリを足すときは、チームに共有して技術選定に理由を追記する

## 秘密情報と個人情報

- `.env`・API キー・認証情報ファイルはコミットしない。中身を読まない・表示しない・チャットに貼らない。環境変数のキー名は `env.example`（先頭にドットなし）に足す。
- デモ・開発・テストでは、実在の人物のデータを使わず架空データを使う。実在の入居者・家族・職員の氏名・写真・記録を、Issue・PR・ログ・スクリーンショットに載せない。
- Claude が git を実行する直前に、hook（`.claude/hooks/guard-git.sh`）が次の2つを確認し、当てはまれば止める。止められたら、hook を回避せずに原因を取り除く（`git -C` やエイリアスでの回避もしない）。
  - `git commit`：`scripts/check-secrets.sh` で `.env`・認証情報ファイル・トークンらしき値がないか（未追跡のファイルも含む）
  - `git push`：main への push・強制 push（`--force`・`--force-with-lease`・`-f` など）でないか（ブランチ保護が使えないプランのため）
- 判定のルールは `scripts/check-secrets.sh` に置く（CI でも PR ごとに同じ確認をする）。秘密ファイルの種類を増やすときは、`.gitignore` と `.claude/settings.json` の Read の deny もそろえる。
- `.claude/settings.json` の deny は、`.env` を読むすべての方法を塞げるわけではない。deny にないコマンドでも、上のルールに従って `.env` の中身を読まない。

## テストと CI

- CI（`.github/workflows/ci.yml`）は PR ごとに、秘密情報の確認、`backend/` の `ruff check .`・`ruff format --check .`・`alembic heads`（1 つか）・`alembic upgrade head`・`python -m pytest`、`frontend/` の `npm run lint`・`npm run format:check`・`npm run test`・`npm run build` を動かす。
- CI は `backend/requirements-dev.txt`・`frontend/package-lock.json` があるときだけ動く。骨格を作るときは、この名前で依存を管理するか、CI もあわせて直す。
- 手元でも、push の前に同じコマンドを通す。pytest は DB と Redis がないと飛ばすので、`docker compose exec` で流し、skipped でなく通ったことを確かめる。
- CI が動かないとき（請求の問題など）は、手元の結果を PR に書けば、CI が緑の代わりにできる（github-workflow スキルの「CI が動かないとき」）。

## Git / GitHub

- コミット・Issue・PR は `.claude/skills/github-workflow/SKILL.md` に従う。
- 自分だけの設定は `.claude/settings.local.json` に書く（Git 管理外）。
