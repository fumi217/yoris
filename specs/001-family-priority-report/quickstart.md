# Quickstart: spec 001 の動かし方と、通しの確認

spec 001 ができているかを、手で通して確かめる手順。Day 3 の通しのデモと、E2E テスト（Playwright）の元にする。
API の形は [contracts/api.md](./contracts/api.md)、テーブルは [data-model.md](./data-model.md) を見る。

## 用意するもの

- Docker Desktop（Docker Compose）
- `.env`（環境変数の見本をコピー。キーは Git に入れない。見本のファイル名は PR #14 の `env.example` に合わせる）

## 起動

```bash
cp env.example .env
docker compose up -d            # frontend・backend・worker・db・redis・mailpit
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed   # 入居者 30 人・職員・家族・テーマ 8 個・定型文・数日分の記録
```

| 開くところ | URL |
|---|---|
| アプリ（`/api` はバックエンドへ中継される） | http://localhost:5173 |
| API の一覧（OpenAPI） | http://localhost:8000/docs |
| 送ったメール（Mailpit） | http://localhost:8025 |

開発環境では、画面の上の「ユーザー切り替え」で、初期データの職員・家族に切り替えられる（[research.md R-02](./research.md#r-02-開発用のユーザー切り替え)）。

## E2E テスト（Playwright）

アプリを起動し、マイグレーションと初期データを入れたあとで、次のコマンドを動かす（開発の DB と、開発用のユーザー切り替えを使う。CI には入れない。T091）。

```bash
docker compose --profile e2e run --rm e2e                          # すべて動かす
docker compose --profile e2e run --rm e2e tests/e2e/foo.spec.ts   # 1 つだけ動かす
```

- 初回は Playwright のイメージ（約 1.5 GB）の取得と、依存の取得で数分かかる。
- 失敗すると、`frontend/playwright-report/` にレポート、`frontend/test-results/` に画面の写真とトレースが残る（どちらも Git に入れない）。
- テストは `frontend/tests/e2e/` に置く。ユーザー切り替えは `helpers.ts` の `loginAs()` を使う。
- イメージの版は、`docker-compose.yml` の `e2e` と `frontend/package.json` の `@playwright/test` をそろえる。
- `vite.config.ts` や `docker-compose.yml` を変えたあとは、すでに起動している frontend を起動し直す：`docker compose up -d --force-recreate frontend`（読み直さないと、E2E のコンテナから `frontend` の名前で呼べない）。
- `@playwright/test` の版を変えたら、依存を取り直すため、保存してある依存を消す：`docker compose down` のあと `docker volume rm section9_e2e_node_modules`（ボリューム名は `docker volume ls` で確かめる）。
- 手元の Node で動かしてもよい（任意）：`cd frontend && npm ci && npx playwright install chromium && E2E_BASE_URL=http://localhost:5173 npx playwright test`

## 通しの確認（Day 3 のデモの流れ）

| # | だれで | すること | こうなれば OK | spec |
|---|---|---|---|---|
| 1 | 介護職員（シティさん） | 入居者「佐藤さんの母」の昼食で「ほぼ全部（8割）」を押す | 3 タップ以内で保存され、記録者と時刻が残る | US1・SC-003 |
| 2 | 介護職員 | 同じ入居者の「機嫌・様子」で「笑顔が多い」、「眠り」で「よく眠れた」を押す | 文字の入力なしで保存される | US1・FR-022 |
| 3 | 生活相談員 | 開示設定で「眠り」を見せないにする | 変更履歴に、いつ・誰が・何を変えたかが出る | US2・FR-011 |
| 4 | 家族（佐藤さん） | 今日の連絡帳を開く | 食事量と機嫌・様子が出て、眠りはどこにも出ない。夜ごはんは「まだ記録されていません」 | US2・SC-006・FR-017 |
| 5 | 家族 | 「知りたいこと」から「👫 他の入居者との関わり」を送る | 「施設に届きました」と送った日時が出る | US3・FR-014 |
| 6 | 介護職員 | 入居者の一覧を見る | 佐藤さんの母に返事待ち 1 件が出る。通知・音は出ない | US3・SC-013 |
| 7 | 介護職員（表示言語：インドネシア語） | リクエストを開いて定型文を選んで保存する | 定型文がインドネシア語で出て、ふりがなは出ない。3 タップ以内で保存できる | US3・SC-007・SC-011 |
| 8 | （Mailpit） | 送ったメールを見る | 5 分以内に「知りたいことへの返事が届きました」が届き、返事の中身は書かれていない | SC-010 |
| 9 | 家族 | アプリを開き直す | ファーストビューの一番上に、職員の名前つきの返事が日本語で出る | US3・FR-015 |
| 10 | 施設長 | 「面会を一時中止します」を PDF を添付して投稿する（毎月の献立表も、同じ形で投稿する） | 全家族にタイトルだけのメールが届き、家族のお知らせ一覧から本文と PDF が見られる | US5・SC-016 |

## ぶつかる場面の確認

| すること | こうなれば OK | spec |
|---|---|---|
| 2 つのタブレットで、同じリクエストにほぼ同時に返事を保存する | 先に保存した方だけが残り、もう一方に「ほかの職員が返事をしました」 | Edge Cases・R-07 |
| 家族がリクエストを取り消したあとに、職員が返事を保存する | 「このリクエストは取り消されました」と出て、保存されない | Edge Cases |
| 返事待ちが 3 件あるときに、家族が 4 件目を送る | 送れず、「返事を待っているリクエストが 3 件あります。返事が届いてから、もう一度送ってください」 | Edge Cases |
| 家族アカウントで、職員の画面の URL を直接開く | 開けない | US1・FR-024 |
| 家族アカウントで、ほかの入居者の id を付けて API を呼ぶ | ほかの入居者の情報は返らない | FR-020 |
| 家族アカウントで、ほかの家族の返事・リクエストの id を指定して、既読にする・取り消す | どちらもできない（404） | FR-020・R-19 |
| 本番の設定（`APP_ENV` を付けない）で `POST /api/dev/switch-user` を呼ぶ | 404 になる | R-02 |
| お知らせの添付の PDF（献立表など）を、iPhone の Safari と Android の Chrome で、別タブと画面の中の両方で開く | どれでも表示される。表示されない環境があれば、PDF はダウンロードにする（作り込みで確認） | R-10 |
| 返事の文に `<script>alert(1)</script>` を入れて保存する | 家族・職員の画面で、文字として出るだけ | SC-009 |
| 10MB を超える PDF、または中身が PDF でないファイルをアップロードする | 受け付けられず、案内が出る（お知らせの添付） | SC-016 |

## まとめの通知の確認

`worker` が 1 分ごとに `run_jobs()` を呼び、20 時（日本時間）を過ぎて最初の呼び出しでまとめを作る（本番は外部のスケジューラーが API を呼ぶ。research.md R-09・R-13）。待たずに確かめるときは、時刻を指定してまとめを作るコマンドを使う。

```bash
docker compose exec worker python -m app.jobs.digest --at "2026-11-02T20:00:00+09:00"
```

| すること | こうなれば OK | spec |
|---|---|---|
| 頻度「1 日 1 回」の家族に、20 時までに記録が入った日でコマンドを 2 回動かす | 「今日の連絡帳がまとまりました」が 1 回だけ届く | SC-010・R-13 |
| worker が動いている間に、同じ時刻でコマンドも動かす | 同じメールが 2 回届かない | R-09・R-13 |
| 20 時台に `run_jobs()` が何度も呼ばれる（worker を動かしたまま 20:00〜20:05 を待つか、`--at` で 20:01・20:02 を続けて動かす） | まとめは 1 回だけ作られる | R-13 |
| 本番の設定で、合言葉なし・違う合言葉で `POST /api/internal/jobs/run` を呼ぶ | 401 になり、何も送られない。開発（`JOBS_TOKEN` が空）では 404 | contracts/api.md |
| 記録が 1 件もない日に動かす | 送られない | FR-023 |
| 日曜の 20 時で動かす | 頻度「1 週間に 1 回」の家族に「今週の連絡帳がまとまりました」が届く | FR-023 |

## テストを動かす

```bash
docker compose exec backend pytest
docker compose exec frontend npm run test       # Vitest（ふりがなの付け忘れのチェックを含む）
docker compose exec frontend npx playwright test
```
